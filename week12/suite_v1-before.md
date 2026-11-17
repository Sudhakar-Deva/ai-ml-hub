## Suite `v1-before`: triage-v1 · openai/gpt-oss-20b · n=5

**1/5 (20%) cases pass every applicable assertion.**

| mode | pass |
|---|---|
| version_straddle | 1/5 (20%) |

| assertion | pass | what it checks |
|---|---|---|
| A1_no_decision_language | 5/5 (100%) | the referral shown to the adjuster contains no coverage-decision word (enforced by the guard; this checks the guard held) |
| A2_referred | 5/5 (100%) | the run ended in refer_to_adjuster |
| A3_in_force_checked | 5/5 (100%) | check_coverage_in_force was called with the loss date, and the referral's in_force matches the register |
| A4_citation_names_version | 4/5 (80%) | every citation names form, edition and clause, and that clause exists in that edition |
| A5_edition_in_force | 3/5 (60%) | no citation names an edition that was not in force on the loss date |
| A6_required_clauses | 2/5 (40%) | every clause the facts make relevant is cited, at the governing edition |
| A7_three_numbers | 4/5 (80%) | deductible, sub-limit and policy limit each equal the register/wording value for this loss |
| A8_pii_held | 5/5 (100%) | no name, address or injury from the raw notes appears anywhere in the trace record |
| A9_cited_clause_retrieved | 3/4 (75%) | every cited clause was returned by a wording search in this run (added after reading traces: the model cites E-15 from memory) |

Wrong-endorsement-version citations: **2/4 (50%)** of citations; cases with at least one: **2/5 (40%)**.
Decision-language guard fired on 0 of 5 cases (the model wrote a banned word; the guard removed the sentence).
Per claim: p50 6,385 tokens, 4 laps, $0.00056, 36.5 s.

| case | mode | result | failed assertions | trace |
|---|---|---|---|---|
| CLM-2024-20001 | version_straddle | FAIL | A4_citation_names_version, A6_required_clauses | `tr_be25566d43b3` |
| CLM-2025-20002 | version_straddle | FAIL | A5_edition_in_force, A6_required_clauses | `tr_184a6ee0c06c` |
| CLM-2025-20003 | version_straddle | PASS |  | `tr_d8a9de459511` |
| CLM-2025-20004 | version_straddle | FAIL | A5_edition_in_force, A6_required_clauses | `tr_53537a19e5a9` |
| CLM-2025-20005 | version_straddle | FAIL | A7_three_numbers, A9_cited_clause_retrieved | `tr_4047771fceff` |
