# Cost per claim triaged, and what breaks first at catastrophe volume

## Cost per claim triaged (measured, `triage-v2`, n=26)

| | value | source |
|---|---|---|
| cost per claim | **$0.000579 mean**, $0.000566 p50, $0.001173 max | spans in `evals/w12/runs/v2-after` |
| tokens per claim | **6,287 mean**, 6,328 p50, 10,996 max | same |
| model calls per claim | 4 laps p50 (2 when the policy was not in force) | same |
| latency, real work | **3.6 s p50** | span latency minus the measured rate-limit sleep |
| latency, as experienced | 41 s p50, of which 37 s is waiting on the 8k tokens/min limit | `rate_limit_wait_ms` |

Every dollar is model tokens. Intake, redaction, the register tools, the guard and retrieval (local Chroma + BM25,
**243 ms p50** inside the MCP server) cost $0. Price used: Groq's listed $0.075 / $0.30 per 1M tokens for
`gpt-oss-20b` (`config.PRICING`; check groq.com/pricing before quoting it).

## The 10× plan: a hailstorm week is 18,000 FNOLs

18,000 / 7 = **2,571 claims/day**, × 6,287 tokens = **16.2M tokens/day**.

| limit | what it allows | needed in a hailstorm week | breaks? |
|---|---|---|---|
| **tokens per day** (Groq free tier, ~200k per model; published figure, the API doesn't report it) | **31 claims/day** | 2,571/day | **YES, first: 81× over.** It already breaks at *normal* volume: 1,800 FNOLs/month ≈ 60/day needs 377k tokens/day, 1.9× the cap. |
| requests per day (1,000, from the `x-ratelimit-limit-requests` header) | 250 claims/day at 4 calls each | 10,284 requests/day | yes, 10× over |
| tokens per minute (8,000, from the `x-ratelimit-limit-tokens` header) | 1.27 claims/min = 1,832/day even with no daily cap | 1.79/min on average, more at peak | yes, 1.4× over |
| money | none | 18,000 × $0.000579 = **$10.42 for the week** | no |
| retrieval / MCP servers / register | local, 243 ms p50 | | not the bottleneck at this scale |

**What breaks first is the provider's daily token cap, at 31 claims a day.** That's 81× short of a hailstorm week, and
already short of a normal day. It isn't cost: the catastrophe week costs about ten dollars.

## What I'd do, ranked

1. **Buy capacity, sized by the number above.** The paid tier must carry ≥16.2M tokens/day and ≥11.2k tokens/min
   *on average* (16.2M / 1,440), with headroom for the afternoon peak. One change, no code.
2. **Stop re-sending the prefix.** Each of the 4 laps re-sends system prompt + tool schemas + FNOL (~1,000 tokens
   before any tool result). `check_coverage_in_force` and `lookup_policy` take only fields already in the FNOL, so
   intake could run them in code and hand the agent their results. That's 2 laps, about −40% tokens per claim (a
   lap-sum estimate, not measured), at the cost of the agent no longer *choosing* those two calls.
3. **Queue, don't fail.** At 8k tokens/min the system works, slowly (41 s per claim). A hailstorm backlog should queue
   FNOLs by loss date and severity rather than dropping them at the cap. `DailyLimit` already stops cleanly and
   resumes.
