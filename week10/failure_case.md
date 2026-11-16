# Injected worker failure: exclusions worker returns HTTP 500

**What the orchestrator did: it retried once, then degraded to UNDETERMINED / $0 with no exclusion codes, naming the
unavailable worker as the reason. It did not lie: it never declared the claim covered without an exclusions check.**

| | |
|---|---|
| case | **CLM-2026-10002**: river overtopped its bank; the gold answer is DENIED on HO-0304 **E-15** (flood). Chosen because the exclusions check *is* the answer here, so a lie would show up as COVERED $22,000. |
| injection | `python -m app.squad.race fail` → `call_worker("exclusions", …)` raises `WorkerHTTPError(500)` on every attempt (`orchestrator.py`, the REST/A2A boundary) |
| orchestrator policy (written before the run) | retry a 5xx once (`RETRIES_ON_5XX = 1`), then continue with an error object in place of that worker's output |
| raw record | `evals/w10/runs/failure.jsonl` · log `week10/logs/failure_*.log` |

## What happened, from the log

```
15:13:17  START       system=squad  claim=CLM-2026-10002  fail_worker=exclusions
15:13:18  HANDOFF     orchestrator.plan                    in=516  out=163
15:13:19  HANDOFF     orchestrator -> notes worker          in=425  out=369
15:13:19  WORKER 500  worker=exclusions  attempt=1  action=retry
15:13:19  WORKER 500  worker=exclusions  attempt=2  action=give up, continue without it
15:13:20  HANDOFF     workers -> orchestrator.synthesis     in=729  out=91
15:13:20  END         status=ok  output={"decision": "UNDETERMINED", "exclusion_codes": [], "payable_amount": 0.0,
                      "reason": "Exclusions worker unavailable; without exclusion or coverage wording the claim
                                 cannot be determined."}
```

Synthesis received `{"error": "exclusions worker unavailable: HTTP 500 after 2 attempts"}` as the exclusions finding,
plus the notes worker's facts. The facts said "river overtopped its bank … water entered … 18 inches", which is enough for
general knowledge to guess "flood → denied". Synthesis applied contract rule 4 ("if the wording you have does not settle
coverage, the decision is UNDETERMINED") and did not guess.

## Verdict on the behaviour

- **Retry:** yes, once. It was useless against a hard 500 and cost no tokens (the worker never ran).
- **Degrade:** yes. It gave a safe UNDETERMINED, with the reason naming the failed dependency.
- **Lie:** no. It made no coverage statement and cited no exclusion it hadn't checked.
- **Graded:** FAIL (gold is DENIED). That's correct grading of a correct refusal: the claim wasn't adjudicated.
- **What it should have done instead:** UNDETERMINED is right for the decision, but the run ended `status=ok`. A downstream
  queue can't tell "undetermined because the wording is silent" from "undetermined because a dependency was down". The
  second case should surface as a failed or paused task, not a finished one (see `a2a.md`).
- **Price of the failure path:** 2,293 tokens, 2.5 s, versus 5,710 tokens and 8.3 s for the healthy run on the same claim.
