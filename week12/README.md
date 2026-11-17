# Week 12 capstone (Variant D): claims triage & coverage assistant

RAG (Weeks 3–4) + the hand-built agent loop (Week 7) + MCP consumed *and* exposed (Week 9) + evals (Weeks 6, 8) +
per-request tracing (Week 11), behind **one entry point**: `backend/app/triage/run.py`.

## Run it (a stranger's path)

```bash
./run.sh setup                    # venv (Python 3.12), dependencies, both indexes; creates .env
# put LLM_API_KEY=<groq key> in .env
./run.sh triage CLM-2024-20001    # one claim: FNOL in -> referral out, span table, trace id
./run.sh eval my-run              # the whole suite against the integrated system + trajectory eval
./run.sh test                     # offline tests, no model calls
```

The 26 claim numbers are in `evals/w12/suite.jsonl`. `./run.sh triage --list-tools` shows what MCP discovery found.

## Deliverables

| checklist item | file |
|---|---|
| one command + README | `../run.sh`, this file |
| seam list, unedited, each marked fixed / accepted / ran-out-of-time | [seam_list.md](seam_list.md) |
| one-page architecture sketch | [architecture.md](architecture.md) |
| full suite output: pass rate per mode, n, judge agreement | [eval_report.md](eval_report.md), [suite_v2-after.md](suite_v2-after.md) |
| re-scored taxonomy, integration-created modes called out | [taxonomy.md](taxonomy.md) |
| trajectory eval + outcome-vs-trajectory gap | [trajectory.md](trajectory.md) |
| one end-to-end trace, cost + latency per span, trace id across agent + MCP hops | [trace.json](trace.json) (+ [trace_v1_wrong_edition.json](trace_v1_wrong_edition.json), [trace_v2_ungrounded_e15.json](trace_v2_ungrounded_e15.json)) |
| top 3 weaknesses, dated, before anyone asked | [weaknesses.md](weaknesses.md) |
| cost per claim + 10× plan | [cost_and_10x.md](cost_and_10x.md) |
| fresh-eyes note | [fresh_eyes.md](fresh_eyes.md): **not yet done**, needs a person from another squad |
| 10-minute demo script | [demo_script.md](demo_script.md) |
| before → after | [before_after.md](before_after.md) |
| the production log | `obs/traces.jsonl` (one redacted record per request), `obs/mcp_server_spans.jsonl` (our server's spans) |

## Headline numbers

- **Wrong-endorsement-version citations: 2/4 → 0/11** on the same 5 straddle cases (n=5); 0/41 across the suite.
- **Suite: 7/26 (27%)** pass all 9 assertions. Right edition 24/24; governing clause cited 11/20; cited clause
  actually retrieved 11/24; three money numbers right 17/24; no decision word shown 26/26; PII held 26/26.
- **Judge agreement: 21/26 = 80.8%: does not clear 85%.** Not used as a gate.
- **Trajectory: tool-choice accuracy 100%, outcome 27%, gap −73 points.**
- **Cost per claim $0.00058.** At 18,000 FNOLs/week, the daily token cap breaks first: 31 claims/day allowed,
  2,571 needed.

## How the weaknesses written before any run turned out

1. *The flood row retrieves badly:* **confirmed, and worse than predicted.** E-15 was returned in 0 of 26 runs.
2. *The model carries the edition from the wrong tool:* **confirmed on v1** (2/5 cases cited the search's edition over
   the in-force tool's). On v2 it inverted: the edition now comes from the in-force tool and the clause from memory (M2).
3. *Three money numbers, two sources:* **half right.** The condo $250 vs $1,000 trap held (3/3 right). The surface-water
   sub-limit failed, and not as predicted: it was applied after April 2025 to losses it doesn't cover (8/26), not
   before April 2025.

## Read before relying on any of this

- **Synthetic data.** The brief's corpus (motor wordings, 500 claim files, 2023/2025 endorsement sets) was never in
  this repo. HO-0304 ed. 01-23 and ed. 04-25, the policy register and the 26 claims were written for this week.
  See `data/policies/README.md`.
- **Model.** The agent runs on `openai/gpt-oss-20b`, not Weeks 7–11's `gpt-oss-120b`. On Groq's free tier, one
  26-case run of a 4-call agent needs about 165k tokens, against a ~200k/day cap per model. `120b` ran the judge.
  Switch back with `TRIAGE_MODEL=openai/gpt-oss-120b`.
- **The first two v1 runs** were on `120b` before the switch. They're kept in `evals/w12/runs/_pilot-120b` and not
  counted. Both showed the same wrong-edition failure.
- **Labels and the "squad".** The hand labels were written by the assistant that built the system, not by an adjuster.
  The seam list and weaknesses are dated Monday 2026-11-16, the real day they were written, not Tuesday/Wednesday.
- **Not done:** the fresh-eyes session, the live demo, and a second fix-and-rerun for M1/M2. A rerun needs another
  ~165k tokens, a full free-tier day.
