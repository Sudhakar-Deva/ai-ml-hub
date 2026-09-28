"""The same task as a FIXED workflow — hard-coded steps, no loop.

    python -m app.agents.workflow --claim CLM-2026-10002
    python -m app.agents.workflow --all

Same model, same three tools (the functions in app/agents/tools.py), same rules
text, same output contract. What is gone is the model choosing the next step:

    1. get_claim(claim_number)
    2. read the adjuster notes off the claim file
    3. search_policy(query = the notes, policy_line = the claim's)   — once
    4. ONE model call: decide coverage from the claim file + those clauses
    5. compute_payout(the decision's numbers)
    6. assemble the contract object

Every claim takes exactly these six steps. There is no `while`, no retry and no
second search — if step 3 does not surface the clause, step 4 decides without it.
The same Budget guards the one call, so a hung request cannot hide either.
"""
import json
import time


from ..llm import LLMTimeout
from . import contract, llm
from .budget import Budget, BudgetExceeded
from .runlog import NULL, RunLog
from .tools import compute_payout, get_claim, search_policy

SYSTEM = contract.RULES

DECIDE = """Claim file (from get_claim):
{claim}

Policy wording (from search_policy, policy_line={policy_line}):
{policy}

Decide coverage for this claim from the claim file and the wording above only.
Return ONE JSON object and nothing else:
{{"decision": "COVERED|PARTIAL|DENIED|UNDETERMINED", "exclusion_codes": ["E-.."],
 "covered_amount": 0, "excess": 0, "special_limit": null,
 "reason": "one or two sentences citing chunk_ids"}}
covered_amount is the part of the claimed amount the policy covers before the
deductible; excess is the deductible to apply; special_limit caps the loss after
the deductible, or null. compute_payout will be run on these numbers."""


def run(claim_number: str, budget: Budget | None = None, log: RunLog = NULL) -> dict:
    budget = budget or Budget()
    path, status, fired = [], "ok", None
    log("START", system="workflow", claim=claim_number, budgets=budget.limits())
    t0 = time.perf_counter()
    try:
        # 1-2. the claim file and its notes
        claim = get_claim(claim_number)
        path.append("get_claim")
        log("  STEP 1 get_claim", notes="present" if claim.get("adjuster_notes") else "MISSING")

        # 3. one policy search, query = the notes (the reported loss type if there are none)
        query = claim.get("adjuster_notes") or claim.get("loss_type_reported") or ""
        policy = search_policy(query, claim["policy_line"], 5)
        path.append("search_policy")
        log("  STEP 3 search_policy", hits=[r["clause"] for r in policy.get("results", [])])

        # 4. one decision call
        try:
            resp, usage = llm.call(budget, system=SYSTEM, messages=[{"role": "user", "content": DECIDE.format(
                claim=json.dumps(claim, indent=2),
                policy_line=claim["policy_line"],
                policy=json.dumps(policy, indent=2),
            )}])
        except LLMTimeout:
            raise BudgetExceeded("wall_clock", f"request timed out at {budget.elapsed():.1f}s")
        log("  STEP 4 decide", lap_in=usage["input_tokens"], lap_out=usage["output_tokens"])
        d = contract.parse(llm.text_of(resp))

        if d is None:
            status, output = "no_contract", None
            log("NO CONTRACT", text=llm.text_of(resp)[:300])
        else:
            # 5. the same arithmetic tool the agent calls
            decision = str(d.get("decision", "")).upper()
            payout = compute_payout(
                decision.lower() if decision.lower() in ("covered", "partial", "denied", "undetermined") else "undetermined",
                float(d.get("covered_amount") or 0),
                float(d.get("excess") or 0),
                d.get("special_limit"),
            )
            path.append("compute_payout")
            log("  STEP 5 compute_payout", **payout)
            # 6. the contract
            output = {
                "claim_number": claim_number,
                "decision": decision,
                "exclusion_codes": d.get("exclusion_codes") or [],
                "payable_amount": payout["payable_amount"],
                "reason": d.get("reason", ""),
            }
    except BudgetExceeded as e:
        status, fired = "budget_exhausted", e.which
        output = contract.undetermined(claim_number, f"terminated: {e.which} budget exceeded ({e.detail})")
        log("BUDGET EXCEEDED", budget=e.which, detail=e.detail, **budget.snapshot())

    latency_ms = (time.perf_counter() - t0) * 1000
    log("END", status=status, latency_ms=round(latency_ms), path=path, output=output)
    return {
        "system": "workflow",
        "claim_number": claim_number,
        "output": output,
        "status": status,
        "budget_fired": fired,
        "path": path,
        "latency_ms": round(latency_ms, 1),
        **budget.snapshot(),
    }


if __name__ == "__main__":
    from .agent import _cli

    _cli("workflow", run)
