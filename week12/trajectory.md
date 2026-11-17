## Trajectory eval on `v2-after` (n=26)

- **Tool-choice accuracy: 101/101 = 100.0%** of tool calls were the right tool with the right arguments
- Trajectory pass (whole expected path held): **26/26 = 100.0%**
- Outcome pass (every suite assertion): **7/26 = 26.9%**
- **Outcome-vs-trajectory gap: -73.1 points**
- Right outcome, wrong path: 0 · wrong outcome, right path: 19

| case | mode | path | tool choices | trajectory | outcome | notes |
|---|---|---|---|---|---|---|
| CLM-2023-20008 | version_straddle | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2024-20001 | version_straddle | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2024-20006 | version_straddle | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2024-20007 | version_straddle | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2024-20010 | coverage_gap | inforce → refer | 2/2 | ok | ok |  |
| CLM-2024-20011 | sub_limit | inforce → lookup → search → refer | 4/4 | ok | ok |  |
| CLM-2024-20013 | clean | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2025-20002 | version_straddle | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2025-20003 | version_straddle | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2025-20004 | version_straddle | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2025-20005 | version_straddle | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2025-20009 | coverage_gap | inforce → lookup → refer | 3/3 | ok | ok |  |
| CLM-2025-20012 | sub_limit | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2025-20014 | policy_line_trap | inforce → lookup → search → refer | 4/4 | ok | ok |  |
| CLM-2025-20015 | decision_bait | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2026-10001 | clean | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2026-10002 | flood_wording | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2026-10003 | notes_exclusion | lookup → inforce → search → refer | 4/4 | ok | FAIL |  |
| CLM-2026-10004 | policy_line_trap | inforce → lookup → search → refer | 4/4 | ok | ok |  |
| CLM-2026-10005 | sub_limit | inforce → lookup → search → refer | 4/4 | ok | ok |  |
| CLM-2026-10006 | notes_exclusion | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2026-10007 | notes_exclusion | inforce → search → lookup → refer | 4/4 | ok | FAIL |  |
| CLM-2026-10008 | sub_limit | inforce → lookup → search → refer | 4/4 | ok | ok |  |
| CLM-2026-10009 | missing_info | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2026-10010 | notes_exclusion | inforce → lookup → search → refer | 4/4 | ok | FAIL |  |
| CLM-2026-10011 | notes_exclusion | inforce → search → lookup → refer | 4/4 | ok | FAIL |  |
