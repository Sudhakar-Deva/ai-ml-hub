"""The claims agent — a hand-built tool loop with all four budgets enforced.

    python -m app.agents.agent --claim CLM-2026-10002
    python -m app.agents.agent --all
    python -m app.agents.agent --claim CLM-2026-10007 --max-iters 2 \\
        --log week7/budget_termination.log          # the clean budget stop

The model picks the next step. Every lap is booked against the Budget BEFORE the
call (can we afford another lap?) and AFTER it (did that lap break tokens, cost
or time?). A breached budget ends the run with an UNDETERMINED contract object
that names the budget — it never raises out, and it never spins.
"""
import argparse
import json
import re
import time


from . import contract, llm
from .. import llm as provider
from ..llm import LLMTimeout
from .budget import Budget, BudgetExceeded
from .runlog import NULL, RunLog, default_path
from .tools import load_claims, load_specs, run_tool

SYSTEM = contract.RULES + """

You have three tools: get_claim, search_policy and compute_payout. Pull the claim
file, read the adjuster notes, look up the wording the notes make relevant (search
again if the first results do not contain the clause you need), then compute the
payable amount. When you have decided, reply with the contract object only.

""" + contract.CONTRACT

TASK = "Adjust claim {claim_number}."

# Week 8 mitigation (the only one): RE-PLANNING on the top failure mode,
# missing_step. The before run returned 7 of 10 decisions without ever calling
# compute_payout, so the payable amount was the model's own arithmetic. When
# the agent tries to finish a decided claim and compute_payout is not on its
# path, it is sent back ONCE with the rule it skipped. It is not re-prompted a
# second time, and it is given no answer: the budgets still bound the extra lap.
REPLAN = """You returned a {decision} decision without calling compute_payout.
Rule 5: payable_amount comes from compute_payout, for every COVERED, PARTIAL or
DENIED decision, a DENIED 0 included. Re-plan: call compute_payout with the
decision you reached and the excess / special limit from the wording you read,
then return the contract object with the amount it returns."""


def run(claim_number: str, budget: Budget | None = None, log: RunLog = NULL,
        tools_version: str = "v2", mitigation: str | None = None) -> dict:
    budget = budget or Budget()
    tools = load_specs(tools_version)
    messages = [{"role": "user", "content": TASK.format(claim_number=claim_number)}]
    path, output, status, fired = [], None, "ok", None
    replans = 0
    # Week 8: the trajectory, not just the tool names — what each call was given
    # and what it saw. Scored offline by app.agents.trajectory_eval.
    steps = []
    wait0 = provider.rate_limit_wait_s()

    log("START", system="agent", claim=claim_number, budgets=budget.limits(), tools=tools_version)
    t0 = time.perf_counter()
    try:
        while True:
            try:
                resp, usage = llm.call(budget, system=SYSTEM, messages=messages, tools=tools)
            except LLMTimeout:
                # The per-request timeout IS the remaining wall-clock budget.
                raise BudgetExceeded("wall_clock", f"request timed out at {budget.elapsed():.1f}s")
            messages.append({"role": "assistant", "content": [llm.to_param(b) for b in resp.content]})
            calls = [b for b in resp.content if b.type == "tool_use"]
            log(f"LAP {budget.iters}", stop=resp.stop_reason, lap_in=usage["input_tokens"],
                lap_out=usage["output_tokens"], **{f"sum_{k}": v for k, v in budget.snapshot().items()})

            if resp.stop_reason != "tool_use" or not calls:
                output = contract.parse(llm.text_of(resp))
                decision = str((output or {}).get("decision", "")).upper()
                if (mitigation == "replan" and not replans and "compute_payout" not in path
                        and decision in ("COVERED", "PARTIAL", "DENIED")):
                    replans += 1
                    log("REPLAN", reason="decided without compute_payout", decision=decision)
                    messages.append({"role": "user", "content": REPLAN.format(decision=decision)})
                    continue
                if output is None:
                    status = "no_contract"
                    log("NO CONTRACT", text=llm.text_of(resp)[:300])
                break

            results = []
            for c in calls:
                out = run_tool(c.name, c.input)
                path.append(c.name)
                steps.append(_step(budget.iters, c.name, c.input, out))
                log("  TOOL", name=c.name, args=c.input,
                    result=("error: " + out["error"]) if "error" in out else f"{len(json.dumps(out))} chars")
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": json.dumps(out),
                                **({"is_error": True} if "error" in out else {})})
            messages.append({"role": "user", "content": results})
    except BudgetExceeded as e:
        status, fired = "budget_exhausted", e.which
        output = contract.undetermined(claim_number, f"terminated: {e.which} budget exceeded ({e.detail})")
        log("BUDGET EXCEEDED", budget=e.which, detail=e.detail, **budget.snapshot())
        log("TERMINATED", status=status, returned=output)

    latency_ms = (time.perf_counter() - t0) * 1000
    rate_wait_ms = (provider.rate_limit_wait_s() - wait0) * 1000
    log("END", status=status, latency_ms=round(latency_ms), path=path, output=output)
    return {
        "system": "agent",
        "claim_number": claim_number,
        "output": output,
        "status": status,
        "budget_fired": fired,
        "path": path,
        "steps": steps,
        "replans": replans,
        "latency_ms": round(latency_ms, 1),
        "rate_wait_ms": round(rate_wait_ms, 1),
        **budget.snapshot(),
    }


_AMOUNT = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)")


def _step(lap: int, name: str, args: dict, out: dict) -> dict:
    """One tool call as the trajectory eval needs it: the arguments as sent, and
    for a search the clauses (form + heading) and dollar amounts it returned —
    what the agent could have read, so a cited code or an excess can be checked
    against it."""
    step = {"lap": lap, "tool": name, "args": args, "error": out.get("error")}
    if name == "search_policy" and "results" in out:
        step["clauses"] = [f"{r['form_number'].split()[0]} | {r['clause']}" for r in out["results"]]
        step["chunk_ids"] = [r["chunk_id"] for r in out["results"]]
        step["amounts"] = sorted({float(a.replace(",", "")) for r in out["results"]
                                  for a in _AMOUNT.findall(r["text"])})
    return step


def _cli(system: str, runner) -> None:
    from .. import config

    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--claim")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--max-iters", type=int, default=config.MAX_ITERS)
    ap.add_argument("--max-tokens", type=int, default=config.MAX_TOKENS)
    ap.add_argument("--max-cost", type=float, default=config.MAX_COST_USD)
    ap.add_argument("--wall-clock", type=float, default=config.WALL_CLOCK_S)
    ap.add_argument("--log", help="log file (default week7/logs/<system>_<ts>.log)")
    a = ap.parse_args()

    from pathlib import Path

    log = RunLog(Path(a.log) if a.log else default_path(system))
    claims = [c["claim_number"] for c in load_claims()] if a.all else [a.claim]
    for cn in claims:
        b = Budget(a.max_iters, a.max_tokens, a.max_cost, a.wall_clock)
        r = runner(cn, b, log)
        print(json.dumps(r["output"], indent=2))
    print(f"\nlog -> {log.path}")


if __name__ == "__main__":
    _cli("agent", run)
