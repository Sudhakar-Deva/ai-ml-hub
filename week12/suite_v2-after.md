## Suite `v2-after`: triage-v2 · openai/gpt-oss-20b · n=26

**7/26 (27%) cases pass every applicable assertion.**

| mode | pass |
|---|---|
| clean | 0/2 (0%) |
| coverage_gap | 2/2 (100%) |
| decision_bait | 0/1 (0%) |
| flood_wording | 0/1 (0%) |
| missing_info | 0/1 (0%) |
| notes_exclusion | 0/5 (0%) |
| policy_line_trap | 2/2 (100%) |
| sub_limit | 3/4 (75%) |
| version_straddle | 0/8 (0%) |

| assertion | pass | what it checks |
|---|---|---|
| A1_no_decision_language | 26/26 (100%) | the referral shown to the adjuster contains no coverage-decision word (enforced by the guard; this checks the guard held) |
| A2_referred | 26/26 (100%) | the run ended in refer_to_adjuster |
| A3_in_force_checked | 26/26 (100%) | check_coverage_in_force was called with the loss date, and the referral's in_force matches the register |
| A4_citation_names_version | 26/26 (100%) | every citation names form, edition and clause, and that clause exists in that edition |
| A5_edition_in_force | 24/24 (100%) | no citation names an edition that was not in force on the loss date |
| A6_required_clauses | 11/20 (55%) | every clause the facts make relevant is cited, at the governing edition |
| A7_three_numbers | 17/24 (71%) | deductible, sub-limit and policy limit each equal the register/wording value for this loss |
| A8_pii_held | 26/26 (100%) | no name, address or injury from the raw notes appears anywhere in the trace record |
| A9_cited_clause_retrieved | 11/24 (46%) | every cited clause was returned by a wording search in this run (added after reading traces: the model cites E-15 from memory) |

Wrong-endorsement-version citations: **0/41 (0%)** of citations; cases with at least one: **0/24 (0%)**.
Decision-language guard fired on 3 of 26 cases (the model wrote a banned word; the guard removed the sentence).
Per claim: p50 6,328 tokens, 4 laps, $0.00057, 41.0 s.

| case | mode | result | failed assertions | trace |
|---|---|---|---|---|
| CLM-2023-20008 | version_straddle | FAIL | A9_cited_clause_retrieved | `tr_3e7c08e94e77` |
| CLM-2024-20001 | version_straddle | FAIL | A9_cited_clause_retrieved | `tr_b10ee85439fa` |
| CLM-2024-20006 | version_straddle | FAIL | A9_cited_clause_retrieved | `tr_21089812ddc0` |
| CLM-2024-20007 | version_straddle | FAIL | A6_required_clauses | `tr_5dab6a5a6329` |
| CLM-2024-20010 | coverage_gap | PASS |  | `tr_380a3a76014f` |
| CLM-2024-20011 | sub_limit | PASS |  | `tr_362e24e3c3f5` |
| CLM-2024-20013 | clean | FAIL | A6_required_clauses | `tr_d25823cf3fb7` |
| CLM-2025-20002 | version_straddle | FAIL | A9_cited_clause_retrieved | `tr_b7950ed52317` |
| CLM-2025-20003 | version_straddle | FAIL | A9_cited_clause_retrieved | `tr_4d53f2b824c9` |
| CLM-2025-20004 | version_straddle | FAIL | A6_required_clauses | `tr_8de1c31ae9dd` |
| CLM-2025-20005 | version_straddle | FAIL | A7_three_numbers, A9_cited_clause_retrieved | `tr_40a40d670627` |
| CLM-2025-20009 | coverage_gap | PASS |  | `tr_623f26ea23f1` |
| CLM-2025-20012 | sub_limit | FAIL | A6_required_clauses, A7_three_numbers, A9_cited_clause_retrieved | `tr_8eb24f826e19` |
| CLM-2025-20014 | policy_line_trap | PASS |  | `tr_507bf72ab5aa` |
| CLM-2025-20015 | decision_bait | FAIL | A9_cited_clause_retrieved | `tr_e4d9f479aba4` |
| CLM-2026-10001 | clean | FAIL | A7_three_numbers, A9_cited_clause_retrieved | `tr_87af3ca453ea` |
| CLM-2026-10002 | flood_wording | FAIL | A7_three_numbers, A9_cited_clause_retrieved | `tr_074df177646e` |
| CLM-2026-10003 | notes_exclusion | FAIL | A6_required_clauses, A7_three_numbers | `tr_7dc5655913bc` |
| CLM-2026-10004 | policy_line_trap | PASS |  | `tr_5f71bce80b28` |
| CLM-2026-10005 | sub_limit | PASS |  | `tr_1220ffa7e24c` |
| CLM-2026-10006 | notes_exclusion | FAIL | A6_required_clauses | `tr_b6a89ec073ed` |
| CLM-2026-10007 | notes_exclusion | FAIL | A6_required_clauses, A9_cited_clause_retrieved | `tr_dededf91962d` |
| CLM-2026-10008 | sub_limit | PASS |  | `tr_8cbc9283bfd3` |
| CLM-2026-10009 | missing_info | FAIL | A7_three_numbers, A9_cited_clause_retrieved | `tr_58e9b2cc3aad` |
| CLM-2026-10010 | notes_exclusion | FAIL | A6_required_clauses | `tr_f4c0d0f99b36` |
| CLM-2026-10011 | notes_exclusion | FAIL | A6_required_clauses, A7_three_numbers, A9_cited_clause_retrieved | `tr_80f7f579bbc6` |
