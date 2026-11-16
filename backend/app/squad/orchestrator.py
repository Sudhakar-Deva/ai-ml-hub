"""The claims squad: an orchestrator that decomposes, two workers, one synthesis.

    python -m app.squad.orchestrator --claim CLM-2026-10002
    python -m app.squad.orchestrator --claim CLM-2026-10002 --fail-worker exclusions

Same model, same output contract and same rules text as the single agent
(app/agents/agent.py), so the race measures the pattern, not a prompt change.

    1. get_claim                                     code, no model
    2. orchestrator.plan                             LLM: split the claim question in two
    3. orchestrator -> notes worker                  LLM, NO tools: claim file in, facts out
    4. orchestrator -> exclusions worker (lap n)     LLM, ONE tool (search_policy), <= 3 laps
    5. workers -> orchestrator.synthesis             LLM: facts + finding in, decision out
    6. compute_payout                                code, the same arithmetic tool

Context strategy (the thing that decides the bill): the exclusions worker gets the
notes worker's FACTS (a few hundred characters), never the raw adjuster notes, and
the synthesis step gets both workers' structured outputs, never the policy chunks.
Only the exclusions worker reads policy text, and only its own laps re-send it.

Every model call is booked to the hand-off that caused it (HANDOFF log lines), with
its input and output tokens and the size of the payload handed over. That log is the
evidence for the context re-send multiplier.

A worker sits behind call_worker(), the boundary a REST or A2A call would cross.
A 5xx from it is retried ONCE, then the orchestrator carries on with an error object
in place of that worker's output. What synthesis does with that object is recorded,
not designed: see week10/failure_case.md.
"""
import argparse
import json
import time

from .. import llm as provider
from ..agents import contract, llm
from ..agents.budget import Budget, BudgetExceeded
from ..agents.runlog import NULL, RunLog
from ..agents.tools import compute_payout, get_claim, load_specs, search_policy
from ..llm import LLMTimeout

EXCLUSIONS_LAPS = 3
RETRIES_ON_5XX = 1

PLAN = """You are the orchestrator of a claims squad. Split this claim into two
sub-questions, one per worker:
  notes worker:      reads the adjuster notes; returns the facts of the loss
  exclusions worker: searches the policy wording of ONE policy line; returns the
                     clause that governs coverage, any exclusion, deductible or limit

Claim metadata (from get_claim): {meta}

Return ONE JSON object and nothing else:
{{"notes_question": "...", "exclusions_question": "...", "need_exclusions": true|false}}
need_exclusions is false only when there are no adjuster notes to check against."""

NOTES_SYSTEM = """You summarise adjuster notes into facts. You have no tools and you
do not decide coverage. Report only what the notes state."""

NOTES_TASK = """{question}

Claim file:
{claim}

Return ONE JSON object and nothing else:
{{"notes_present": true|false, "cause_of_loss": "...", "sudden_or_gradual": "sudden|gradual|unknown",
 "duration": "...", "occupancy": "...", "items_or_property": "...",
 "amounts": {{"claimed": 0, "breakdown": "..."}}, "other_relevant_facts": "..."}}"""

EXCLUSIONS_SYSTEM = """You are the coverage/exclusions worker. Your one tool is
search_policy. Find the policy wording that governs this loss on the given policy
line ONLY: an exclusion that removes coverage, a grant that confirms it, the
deductible the wording sets, and any special limit. Search again with policy words
if the first results do not contain the clause you need. Never use another line's
wording or general insurance knowledge. You do not decide the final claim outcome."""

EXCLUSIONS_TASK = """{question}

policy_line: {policy_line}
Facts of the loss (from the notes worker): {facts}

When done, reply with ONE JSON object and nothing else:
{{"effect": "excluded|covered|limited|not_found", "exclusion_codes": ["E-.."],
 "governing_clause": "form + clause heading", "deductible": null, "special_limit": null,
 "chunk_ids": ["..."], "quote": "the deciding sentence, verbatim"}}"""

SYNTH = """You are the orchestrator. Your workers have reported. Decide the claim.

Claim file fields: {core}
Notes worker (facts): {facts}
Exclusions worker (governing wording): {finding}

Return ONE JSON object and nothing else:
{{"decision": "COVERED|PARTIAL|DENIED|UNDETERMINED", "exclusion_codes": ["E-.."],
 "covered_amount": 0, "excess": 0, "special_limit": null,
 "reason": "one or two sentences citing the chunk_ids the exclusions worker gave"}}
covered_amount is the part of the claimed amount the policy covers before the
deductible; excess is the deductible to apply; special_limit caps the loss after the
deductible, or null. compute_payout will be run on these numbers."""


class WorkerHTTPError(Exception):
    def __init__(self, status: int, worker: str):
        super().__init__(f"{status} from {worker} worker")
        self.status, self.worker = status, worker


class Squad:
    def __init__(self, claim_number: str, budget: Budget, log: RunLog, fail_worker: str | None = None):
        self.cn, self.budget, self.log, self.fail_worker = claim_number, budget, log, fail_worker
        self.handoffs: list[dict] = []
        self.events: list[dict] = []

    # --- one model call, booked to a named hand-off ---------------------------
    def _call(self, handoff: str, system: str, messages: list[dict], tools=None, payload_chars: int = 0):
        try:
            resp, usage = llm.call(self.budget, system=system, messages=messages, tools=tools)
        except LLMTimeout:
            raise BudgetExceeded("wall_clock", f"request timed out at {self.budget.elapsed():.1f}s")
        h = {"claim": self.cn, "handoff": handoff, "in": usage["input_tokens"], "out": usage["output_tokens"],
             "payload_chars": payload_chars}
        self.handoffs.append(h)
        self.log("HANDOFF", **h)
        return resp

    # --- the worker boundary ---------------------------------------------------
    def call_worker(self, name: str, fn, *args):
        for attempt in range(RETRIES_ON_5XX + 1):
            try:
                if self.fail_worker == name:              # injected: the worker answers HTTP 500
                    raise WorkerHTTPError(500, name)
                return fn(*args)
            except WorkerHTTPError as e:
                self.events.append({"event": "worker_error", "worker": name, "status": e.status,
                                    "attempt": attempt + 1})
                self.log("WORKER 500", worker=name, attempt=attempt + 1,
                         action="retry" if attempt < RETRIES_ON_5XX else "give up, continue without it")
        return {"error": f"{name} worker unavailable: HTTP 500 after {RETRIES_ON_5XX + 1} attempts"}

    # --- workers ---------------------------------------------------------------
    def notes_worker(self, question: str, claim: dict) -> dict:
        task = NOTES_TASK.format(question=question, claim=json.dumps(claim, indent=1))
        resp = self._call("orchestrator -> notes worker", NOTES_SYSTEM,
                          [{"role": "user", "content": task}], payload_chars=len(task))
        return contract.parse(llm.text_of(resp)) or {"error": "notes worker returned no JSON"}

    def exclusions_worker(self, question: str, policy_line: str, facts: dict) -> dict:
        tools = [t for t in load_specs("v2") if t["name"] == "search_policy"]    # ONE tool, narrow
        task = EXCLUSIONS_TASK.format(question=question, policy_line=policy_line, facts=json.dumps(facts))
        messages = [{"role": "user", "content": task}]
        for lap in range(1, EXCLUSIONS_LAPS + 1):
            resp = self._call(f"orchestrator -> exclusions worker (lap {lap})", EXCLUSIONS_SYSTEM, messages,
                              tools=tools, payload_chars=sum(len(json.dumps(m["content"])) for m in messages))
            messages.append({"role": "assistant", "content": [llm.to_param(b) for b in resp.content]})
            calls = [b for b in resp.content if b.type == "tool_use"]
            if not calls:
                return contract.parse(llm.text_of(resp)) or {"error": "exclusions worker returned no JSON"}
            results = []
            for c in calls:
                args = c.input if c.name == "search_policy" else {}
                out = search_policy(**args) if c.name == "search_policy" else {"error": f"unknown tool {c.name}"}
                self.events.append({"event": "search", "args": args,
                                    "clauses": [r["clause"] for r in out.get("results", [])]})
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": json.dumps(out)})
            messages.append({"role": "user", "content": results})
        return {"effect": "not_found", "error": f"no answer within {EXCLUSIONS_LAPS} laps"}

    # --- the run ----------------------------------------------------------------
    def run(self) -> dict:
        claim = get_claim(self.cn)
        meta = {k: claim.get(k) for k in ("claim_number", "policy_line", "loss_type_reported", "claimed_amount")}
        meta["adjuster_notes_present"] = bool(claim.get("adjuster_notes"))

        plan_msg = PLAN.format(meta=json.dumps(meta))
        plan = contract.parse(llm.text_of(self._call("orchestrator.plan", contract.RULES,
                                                      [{"role": "user", "content": plan_msg}],
                                                      payload_chars=len(plan_msg)))) or {}

        facts = self.call_worker("notes", self.notes_worker,
                                 plan.get("notes_question", "Summarise the facts of this loss."), claim)
        if plan.get("need_exclusions", True):
            finding = self.call_worker("exclusions", self.exclusions_worker,
                                       plan.get("exclusions_question", "Find the governing wording."),
                                       claim["policy_line"], facts)
        else:
            finding = {"skipped": "orchestrator plan: no adjuster notes to check against"}

        core = {k: claim.get(k) for k in ("claim_number", "policy_line", "claimed_amount", "policy_excess")}
        synth_msg = SYNTH.format(core=json.dumps(core), facts=json.dumps(facts), finding=json.dumps(finding))
        d = contract.parse(llm.text_of(self._call("workers -> orchestrator.synthesis", contract.RULES,
                                                   [{"role": "user", "content": synth_msg}],
                                                   payload_chars=len(synth_msg))))
        if d is None:
            return {"output": None, "status": "no_contract", "facts": facts, "finding": finding, "plan": plan}
        decision = str(d.get("decision", "")).upper()
        status = decision.lower() if decision.lower() in ("covered", "partial", "denied", "undetermined") \
            else "undetermined"
        payout = compute_payout(status, float(d.get("covered_amount") or 0), float(d.get("excess") or 0),
                                d.get("special_limit"))
        output = {"claim_number": self.cn, "decision": decision, "exclusion_codes": d.get("exclusion_codes") or [],
                  "payable_amount": payout["payable_amount"], "reason": d.get("reason", "")}
        return {"output": output, "status": "ok", "facts": facts, "finding": finding, "plan": plan}


def run(claim_number: str, budget: Budget | None = None, log: RunLog = NULL,
        fail_worker: str | None = None) -> dict:
    budget = budget or Budget()
    squad = Squad(claim_number, budget, log, fail_worker)
    wait0 = provider.rate_limit_wait_s()
    t0 = time.perf_counter()
    log("START", system="squad", claim=claim_number, fail_worker=fail_worker)
    fired = None
    try:
        r = squad.run()
    except BudgetExceeded as e:
        fired = e.which
        r = {"output": contract.undetermined(claim_number, f"terminated: {e.which} budget exceeded"),
             "status": "budget_exhausted"}
    latency_ms = (time.perf_counter() - t0) * 1000
    log("END", status=r["status"], latency_ms=round(latency_ms), output=r["output"])
    return {"system": "squad", "claim_number": claim_number, **r, "budget_fired": fired,
            "handoffs": squad.handoffs, "events": squad.events, "fail_worker": fail_worker,
            "latency_ms": round(latency_ms, 1),
            "rate_wait_ms": round((provider.rate_limit_wait_s() - wait0) * 1000, 1), **budget.snapshot()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--claim", required=True)
    ap.add_argument("--fail-worker", choices=["notes", "exclusions"])
    a = ap.parse_args()
    r = run(a.claim, Budget(wall_clock_s=400), RunLog(None), a.fail_worker)
    print(json.dumps({k: r[k] for k in ("output", "status", "handoffs", "events", "tokens", "cost_usd")}, indent=1))
