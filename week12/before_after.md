## v1-before → v2-after, on the same 5 cases

| metric | before | after |
|---|---|---|
| wrong-endorsement-version citation rate (citations) | 2/4 (50%) | 0/11 (0%) |
| cases citing a wrong edition | 2/5 (40%) | 0/5 (0%) |
| cases passing every assertion | 1/5 (20%) | 0/5 (0%) |

| case | before | after |
|---|---|---|
| CLM-2024-20001 | FAIL A4_citation_names_version, A6_required_clauses | FAIL A9_cited_clause_retrieved |
| CLM-2025-20002 | FAIL A5_edition_in_force, A6_required_clauses | FAIL A9_cited_clause_retrieved |
| CLM-2025-20003 | PASS | FAIL A9_cited_clause_retrieved |
| CLM-2025-20004 | FAIL A5_edition_in_force, A6_required_clauses | FAIL A6_required_clauses |
| CLM-2025-20005 | FAIL A7_three_numbers, A9_cited_clause_retrieved | FAIL A7_three_numbers, A9_cited_clause_retrieved |
