# Regression check: `before` -> `after`

| mode | before | after | Δ | verdict |
|---|---|---|---|---|
| hallucinated_tool | 3 | 2 | -1 | better |
| skipped_evidence | 0 | 0 | +0 | unchanged |
| missing_step | 7 | 0 | -7 | **TOP MODE, targeted** better |
| extra_steps | 1 | 1 | +0 | unchanged |
| out_of_order | 0 | 0 | +0 | unchanged |
| invalid_argument | 3 | 3 | +0 | unchanged |
| fabricated_citation | 0 | 0 | +0 | unchanged |
| contradicts_tool | 0 | 1 | +1 | **NEW (created)** |
| budget_exhausted | 0 | 0 | +0 | unchanged |
| no_contract | 0 | 0 | +0 | unchanged |

| metric | before | after | Δ |
|---|---|---|---|
| outcome pass rate | 100% | 90% | -10.0 pts |
| trajectory pass rate | 20% | 70% | +50.0 pts |
| tool-choice accuracy | 68.8% | 88.2% | +19.5 pts |
| argument validity | 94.0% | 93.7% | -0.3 pts |
| step efficiency | 0.96 | 1.21 | 0.25 |
| cost / claim p50 | $0.00093 | $0.00174 | $0.00081 |
| cost / claim max | $0.00234 | $0.00232 | $-0.00001 |
| cost / claim mean | $0.00113 | $0.00173 | $0.00059 |
| tokens / claim p50 | 5,238 | 10,207 | 4,969 |
| tokens / claim max | 14,452 | 14,395 | -57 |
| laps / claim p50 | 3.5 | 5.0 | 1.5 |
| latency p50 (net) | 3,645 ms | 5,672 ms | 2,026 ms |
| latency max (net) | 5,539 ms | 14,467 ms | 8,929 ms |

Gap (outcome − trajectory): +80 pts -> +20 pts
Top mode `missing_step`: 7 -> 0

| claim | before path | before modes | after path | after modes |
|---|---|---|---|---|
| 10001 | `get_claim>search_policy>search_policy>compute_payout` | — | `get_claim>search_policy>search_policy>compute_payout` | — |
| 10002 | `get_claim>search_policy` | missing_step | `get_claim>search_policy>compute_payout` | — |
| 10003 | `get_claim>search_policy>json` | hallucinated_tool, invalid_argument, missing_step | `get_claim>search_policy>compute_payout` | — |
| 10004 | `get_claim>search_policy` | missing_step | `get_claim>search_policy>commentary>compute_payout` | hallucinated_tool, invalid_argument |
| 10005 | `get_claim>search_policy>compute_payout` | — | `get_claim>search_policy>compute_payout` | — |
| 10006 | `get_claim>search_policy` | missing_step | `get_claim>search_policy>compute_payout` | — |
| 10007 | `get_claim>search_policy>json` | hallucinated_tool, invalid_argument, missing_step | `get_claim>search_policy>compute_payout` | — |
| 10008 | `get_claim>search_policy` | missing_step | `get_claim>search_policy>compute_payout` | invalid_argument |
| 10009 | `get_claim>JSON>search_policy>search_policy` | extra_steps, hallucinated_tool, invalid_argument | `get_claim>JSON>search_policy>JSON>compute_payout` | contradicts_tool, extra_steps, hallucinated_tool, invalid_argument |
| 10010 | `get_claim>search_policy` | missing_step | `get_claim>search_policy>compute_payout` | — |
