# Week 11 · Task Set D: find the coverage answer that ignored an exclusion

| deliverable | file | result |
|---|---|---|
| drill: time-to-find + slice | [drill.md](drill.md) | **00:09**, slice **time + output** (`--day … --position COVERED`), then input fingerprint |
| the found trace | [trace.json](trace.json) | per-span latency/tokens/cost, `claims-summary-v1`, 5 context ids (3 condo chunks, no E-22) |
| the new eval case | [evals/w11/coverage_suite.jsonl](../evals/w11/coverage_suite.jsonl), `w11-011` | regression case built from the logged request |
| suite RED → GREEN | [suite_red.txt](suite_red.txt) → [suite_green.txt](suite_green.txt) | **10/11 → 11/11**, whole suite both times |
| fix + version bump + canary/rollback | [canary_rollback.md](canary_rollback.md) | retrieval-layer fix, `claims-summary-v1` → **`v2`** |
| cost by stage | [cost_by_stage.md](cost_by_stage.md) | retrieval $0 · **generation $0.000498 (100%)** · tools $0 |
| 10× | [tenx.md](tenx.md) | **a rate limit breaks first:** ≈833k tokens/day needed vs a 200k/day cap |

## The loop, end to end

1. **Logs.** `backend/app/obs/app.py` wraps the claim-summary path. One JSON line per request holds retrieval,
   generation and tools spans (latency, tokens, cost each), user, input type, prompt version, the retrieved context ids,
   and the output's coverage position indexed. It's redacted on write (claim numbers and names never reach disk).
2. **Traffic.** `python -m app.obs.traffic --day 2026-11-15` sends 20 real requests (the 10 fixed claims, each opened by
   two adjusters), with `ts` set to yesterday's business hours. `ran_at` keeps the real clock.
3. **Plant.** A subagent squadmate wrote a new claim, ran it through the real app until the app genuinely said COVERED,
   then sealed the answer. I saw only the complaint.
4. **Find.** `python -m app.obs.find --day 2026-11-15 --position COVERED` gave 5 of 22 requests. One had an unknown
   `notes_sha`, so the answer was `req_e9fffc122627`, found in 00:09.
5. **Diagnose (one hop).** Its context ids showed retrieval missed: HO-0304 E-22 was never retrieved, and 3 of 5 chunks
   were condo wording on a homeowners claim.
6. **RED.** I added the case `w11-011` and ran the whole suite on v1: **10/11**. The new case failed exactly as in
   production (COVERED, NONE).
7. **Fix.** `retrieve()` now searches only the notes' declared policy line and attaches that line's full exclusions
   schedule. I bumped the version to `claims-summary-v2`.
8. **GREEN.** The whole suite on v2: **11/11**. No base case regressed. The price: +79% tokens, +51% cost per request.

## Run it (from `backend/`)

```bash
../.venv/bin/python -m app.obs.find --day 2026-11-15 --position COVERED     # the drill slice
../.venv/bin/python -m app.obs.find --show req_e9fffc122627                 # the full trace
../.venv/bin/python -m app.obs.suite run --tag <tag>                        # whole suite, paid (~11 calls)
../.venv/bin/python -m pytest tests/test_obs.py                             # 13 tests, no LLM
```

## Notes

- **The Week-6 suite file was never committed** (same as Week 10), so the "Week-6 suite" here is the 10 fixed claims in
  the Week-6 case format plus the new regression case, gated by coverage position, exclusions and Week 6's assertion A4.
- **The squadmate was a Claude subagent**, not a person. It planted blind and sealed its answer; see drill.md.
- **Simulated day:** the 20 traffic requests are real model calls; only their `ts` is set to yesterday.
- **A latent risk the fix also closes:** on v1, the flood case (w11-002) was answered DENIED E-15 although E-15 was never
  retrieved, which means the model relied on general knowledge. On v2 the schedule puts E-15 in the context.
- **Bonus not done.** Once v2 is live, a second *genuine* bad answer is hard to produce. A fabricated log line would test
  only the search tool, not the app. The field I'd add is in drill.md.
- Model `openai/gpt-oss-120b` on Groq's free tier. The suite runs are single samples at temperature 0.
