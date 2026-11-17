# Error taxonomy, re-scored on the integrated system

Scored by reading every trace of the integrated system: `triage-v2` on the full suite (n=26, `evals/w12/runs/v2-after`)
and `triage-v1` on the 5 straddle cases (n=5, `evals/w12/runs/v1-before`). Model `openai/gpt-oss-20b`, temperature 0.
A case can show more than one mode, so the frequencies don't sum to 100%. The counts come from code over the saved
traces (`app.triage.suite.retrieved_clauses`, the assertion results), not from memory.

| # | mode | freq (v2, n=26) | severity | origin | one trace |
|---|---|---|---|---|---|
| **M1** | **Sub-limit row leaks into the referral.** `lookup_policy` lists the $15,000 surface-water sub-limit (HO-0304 ed. 04-25 E-15) for every homeowners loss on or after 2025-04-01. The model applies it to *any* water loss (burst pipe, river flood, sewer backup, slow leak, rain through a self-made opening) and cites "E-15" from the sub-limit's `source` string, not from wording it read. Twice it then states river overflow is "not excluded", which is false under ed. 04-25. | **8/26 (31%)**: 8 of the 9 homeowners water losses dated after 2025-04-01 | **High**: a wrong number, and a false statement about the wording, go to the adjuster | **NEW, created by integration**: only exists once the date-aware register (Week 12) meets the Week 7 agent | `tr_074df177646e` (CLM-2026-10002) |
| **M2** | **Ungrounded citation.** A clause is cited that no search returned. The edition is taken from `check_coverage_in_force` and the clause from the model's memory of standard wording. E-15 was returned by search in **0 of 26** v2 runs, yet cited in 12. | **13/26 (50%)** (A9 fails) | **High**: looks exactly like a good citation. A1–A8 and the judge passed some of these. | **NEW, created by integration**: the in-force tool names the right edition and the search misses the clause; together they give a well-formed citation with nothing under it | `tr_b10ee85439fa` (CLM-2024-20001) |
| M3 | **Governing clause never retrieved.** The agent's query paraphrases the notes ("water damage basement"), and the short exclusion row loses to longer neighbours. | **10/26 (38%)**: 10 of the 20 cases that need a clause | High | Inherited (Week 4 retriever, k=5). Predicted as weakness 1 | `tr_8de1c31ae9dd` (CLM-2025-20004, brook overflow, E-15 absent) |
| M4 | **Retrieved but not cited / mislabelled.** The right row is in context and the model cites a neighbour, or describes E-17 under E-22's code. | **5/26 (19%)** | High | Inherited (Week 5's citation-mismatch mode) | `tr_7dc5655913bc` (CLM-2026-10003, E-19 retrieved, E-20/21/22 cited) |
| **M5** | **Wrong endorsement edition cited.** The undated search returns all three HO-0304 editions mixed, and the model cites the newest, even though the in-force tool named the older one. | v1: **2/5 cases (40%), 2/4 citations**. v2: **0/26 cases, 0/41 citations** | **Critical** (the brief's live wound) | **NEW, created by integration**: versioned corpus + Week 9 MCP search with no loss date | `tr_184a6ee0c06c` (v1, CLM-2025-20002, ed. 04-25 cited for a 2025-03-31 loss) |
| M6 | **Decision language written.** The model wrote "covered" in a free-text field. The code guard removed the sentence, so 0 reached the adjuster. | **3/26 (12%)** written, **0/26** shown | Critical if it leaked; contained | Inherited (Week 7's contract made it decide) | `tr_8eb24f826e19` (CLM-2025-20012, 3 sentences removed) |

## The modes integration created

**M5** is the one the brief predicted: it only exists because the versioned corpus and the undated MCP search met. It
was fixed in code (loss-date filter in the store query) and is **0/26** after.

**M1 and M2** were not predicted (weakness 3 came close for M1) and are the more important finding. Each part is right
on its own. `lookup_policy` returns the right sub-limits for the date, `check_coverage_in_force` names the right edition,
and `search_policy` returns only in-force wording. Joined in one agent, they let the model produce a correctly dated,
well-formed, wrong referral. The date fix made M2 *look* better: before it, an ungrounded citation also carried the
wrong edition and got caught by A5.

## What the assertions missed, and what changed

A1–A8 passed CLM-2024-20001 on v2 and the judge passed it too, although its only flood citation was never retrieved.
Reading that trace led to **A9_cited_clause_retrieved**, added to the suite and applied to every run identically. It
moved the v2 pass rate from 13/26 to **7/26**. That's the honest number.
