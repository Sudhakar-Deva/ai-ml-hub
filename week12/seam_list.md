# Seam list (written before integration, unedited)

Written **Monday 2026-11-16**, before any integrated run. The brief asks for it on Tuesday; it was written the day the
work started, and the date says so. The list below is the original text. Status is added only in the final section, and
nothing above that section is changed after a run.

| # | seam | where the parts meet |
|---|---|---|
| S1 | The claims-system MCP server returns adjuster notes verbatim, with names, addresses and injuries. Whatever the agent receives goes to the model provider, into logs, and possibly back out through our own MCP server. | claims-system (vendored) → agent |
| S2 | `policy-docs.search_policy` takes no loss date. With more than one edition of a form indexed, it returns whichever edition ranks best. | agent → our MCP server → Week 4 retriever |
| S3 | The Week 9 server keys forms by form number alone (`FORMS["HO-0304"]`), so two editions of one form overwrite each other in `get_clause`. | our MCP server ← corpus |
| S4 | The attached `policy://exclusions/<line>` resources list every row of every edition, undated. That puts mixed-edition context in front of the model before it has called a tool. | MCP resources → agent system prompt |
| S5 | No trace id crosses the MCP hop. Week 9 traces are per host process, and the Week 11 log covers only the summary path. | agent ↔ MCP servers ↔ logs |
| S6 | The Week 7 contract makes the agent state COVERED / DENIED / PARTIAL. Compliance forbids any automated coverage decision. | agent output contract |
| S7 | The Week 6 judge grades "the coverage position". A referral has no coverage position, so the judge's criterion has to be restated for referral outputs and re-validated. | judge ← integrated output |
| S8 | `policy_excess` from the claims system is the policy-level deductible. For a condo loss assessment the applicable deductible is the $250 in CO-0715. Two systems, two numbers. | claims-system ↔ wording |
| S9 | The Week 6 eval-set file was never committed (as in Weeks 10 and 11). The "Week 6 suite" has to be rebuilt in its format. | evals |
| S10 | Groq free tier: about 200k tokens/day and 8k tokens/min on `openai/gpt-oss-120b`. An agent run re-sends the whole conversation on every lap. | everything → provider |
| S11 | Coverage in force is not in any part built so far: no policy register, no term dates. | agent tools ← (nothing) |
| S12 | The corpus has one edition per form, so "the wording in force on the loss date" cannot even be expressed yet. | corpus |

---

## Status (added after the integrated runs; nothing above this line was changed)

| # | status | what happened |
|---|---|---|
| S1 | **fixed** | Notes are redacted at intake, before the model, any log, or our MCP server can see them. A8: 26/26 traces hold no name, address or injury from the raw notes. |
| S2 | **fixed** | `triage-v2`: `search_policy` requires `loss_date`, enforced in the Chroma query. Wrong-edition citations went from 2/4 to 0/11 on the same 5 cases, and 0/41 across the suite. |
| S3 | **fixed** | The server keys editions per form; `get_clause` resolves the edition by `loss_date` and refuses an undated call on a multi-edition form. |
| S4 | **fixed** | The capstone MCP config attaches no resources. |
| S5 | **fixed / accepted** | Fixed for our server: the trace id rides in `_meta`, and the server writes its own span (24/24 server spans joined their host trace). Accepted for the vendored claims-system: we can't change its code, so its calls have host-side spans only. |
| S6 | **fixed** | No decision field; the run can only end through `refer_to_adjuster`. The guard removes decision-word sentences in code: fired on 3/26, 0 reached the adjuster. |
| S7 | **ran out of time** | Judge v3 written and run: 80.8% agreement, which **does not clear 85%**. Its fix needs a fresh labelled set. |
| S8 | **fixed** | `lookup_policy` returns the peril deductible separately; all 3 condo cases report $250, not $1,000. |
| S9 | **accepted** | The suite was rebuilt in the Week 6 format (26 cases); the original file doesn't exist. |
| S10 | **accepted** | The agent moved to `gpt-oss-20b` to fit one suite run in a day. This limit is what breaks first at 10× (cost_and_10x.md). |
| S11 | **fixed** | Synthetic policy register + `check_coverage_in_force`; A3 26/26. |
| S12 | **fixed (synthetic)** | HO-0304 ed. 01-23 and ed. 04-25 added, both written for Week 12. |
| — | **found, not on the list: ran out of time** | **M1 sub-limit leak (8/26)** and **M2 ungrounded citations (13/26)**: seams between the register tools and the agent that no single part shows. See taxonomy.md. |
