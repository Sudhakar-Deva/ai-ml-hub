# Week 10 · Task Set D: race the claims squad against the single agent

| deliverable | file | headline |
|---|---|---|
| race table (4 metrics × 2 arms, 10 cases named) | [race_table.md](race_table.md) | pass **90% vs 70%** · p50 **4.1 s vs 7.8 s** · p99 **6.2 s vs 10.1 s** · tokens **56,240 vs 55,897** · cost/claim **$0.00096 vs $0.00120** |
| hand-off log, every call with its tokens | [handoffs.log](handoffs.log) | 38 single-agent laps + 52 squad hand-offs |
| multiplier + attributed hand-off | [multiplier.md](multiplier.md) | **1.0**; largest share **orchestrator → exclusions worker, 58%** (lap 2 alone 29%) |
| injected worker failure | [failure_case.md](failure_case.md) | **retried once, then degraded** to UNDETERMINED; did not lie |
| verdict (≤10 lines, sunk cost named) | [verdict.md](verdict.md) | **kill the squad, keep the single agent** |
| bonus: AgentCard + A2A lifecycle | [agent_card.json](agent_card.json) · [a2a.md](a2a.md) | the failed case should end `input-required`, not `completed` |

## Run it (from `backend/`)

```bash
../.venv/bin/python -m app.squad.race run       # both arms, same 10 claims, interleaved (paid)
../.venv/bin/python -m app.squad.race fail      # 500 from the exclusions worker on CLM-2026-10002 (paid)
../.venv/bin/python -m app.squad.race report    # offline: regenerates race_table.md, handoffs.log, multiplier.md
../.venv/bin/python -m pytest tests/test_squad.py   # 10 tests: squad mechanics + deliverables vs raw runs
```

Raw records: `evals/w10/runs/race.jsonl` (20 runs) and `failure.jsonl`. Every number above is computed from them.

## The eval set: read this first

The brief says to race on "the same 10 Week-6 eval cases". **That file (`evals/w6/eval_set.jsonl`) was never committed
to this repo and doesn't exist on disk.** Only the Week-6 judge prompts were committed. Rather than write new cases (which
the brief says voids the comparison), both arms ran on **the 10 fixed cases in `evals/w7/claims.jsonl`**: the set the
single agent was already raced on in Week 7 and trajectory-evaluated on in Week 8, unchanged. Both arms are graded by the
same judge, `contract.grade` (decision, exclusion codes, payable within $1). That judge is deterministic, so no judge
variance enters the comparison.

## What the squad is

`backend/app/squad/orchestrator.py`, using the same model, rules text and output contract as the single agent.

The flow:
1. `get_claim` (code)
2. **plan** (LLM)
3. **notes worker** (LLM, no tools): claim file in, facts out
4. **exclusions worker** (LLM, **one tool**, `search_policy`, at most 3 laps): facts in, governing clause out
5. **synthesis** (LLM)
6. `compute_payout` (code)

Context strategy: raw adjuster notes go **only** to the notes worker. The exclusions worker sees facts, and synthesis sees
both workers' structured outputs, never the policy chunks. That's why the multiplier is 1.0 and not the "9× bill" the
brief warns about. The re-send that remains lives inside the exclusions worker's own laps (58%).

## Why the squad lost: three named hand-off failures

| claim | what the exclusions worker did | what went wrong |
|---|---|---|
| 10001 clean | found E-17 "does NOT apply, covered" | reported the deductible as prose; **synthesis** refused to use the claim's $1,000 excess and returned UNDETERMINED |
| 10006 assoc. deductible | retrieved E-31 on lap 1 | then emitted its answer as a call to a **nonexistent tool** (twice), hit the 3-lap cap with no answer |
| 10008 jewelry | retrieved HO-0521 B ($2,500) on laps 2 and 3 | kept searching, never answered within 3 laps |

The single agent's one failure (10008) was arithmetic: $4,500 instead of $2,500.

## Caveats

- **Single sample per claim per arm**, on Groq's free tier (`openai/gpt-oss-120b`). A 2-claim pass-rate difference is
  within noise. The direction holds on latency and cost.
- **p99 with n = 10 is the slowest claim** (nearest rank). Latency is reported **net of 429 rate-limit sleeps**, which
  otherwise dominate (raw p99: 117 s single, 73 s squad, both mostly waiting on the rate limit).
- **Some calls weren't billed by the provider.** Groq reports no token usage for generations it rejects (calls to a tool
  that doesn't exist): 6 such calls in the single arm and 3 in the squad arm are booked at 0 tokens. Both totals are
  slightly understated.
- **Cost ×1.3 with tokens ×1.0:** the squad writes 3.3× more output tokens (8,146 vs 2,504; the plan and notes worker each
  generate a JSON document), and output is priced 4× input.
