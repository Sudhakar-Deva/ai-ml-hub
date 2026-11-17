# Demo script: 10 minutes, four parts

Have two terminals open at the repo root, and `week12/` open in the editor. Every number below comes from a file in
this folder; say which file when you quote it.

## Part 1: a real run (0:00–3:00)

```bash
./run.sh triage CLM-2024-20001      # the live wound: a surface-water loss dated 11 August 2024
```

Point at, in order:
1. **Coverage in force, as a visible tool call**: `tool.check_coverage_in_force` in the span table. The referral's
   first line says *In force on the loss date: YES*.
2. **The exclusion by clause and edition**: `HO-0304 ed. 03-24 · E-15`, a clickable link to the line in the file,
   "resolved against loss date 2024-08-11". Say: *ed. 04-25 exists, reads better for this loss, and was in force
   from 1 April 2025. It is filtered out in the store query, not by a prompt.*
3. **Three numbers**: deductible $1,000, sub-limit *none* (the $15,000 surface-water sub-limit didn't exist yet),
   policy limit $400,000.
4. **Referral, not a decision**: the first line of the output. There is no decision field to fill.
5. **One trace id**: the last span is `mcp.policy-docs.search_policy  server`, written by our MCP server process
   under the same id. Open `week12/obs/traces.jsonl` and show the notes as `[NAME]`, `[ADDRESS]`, `[INJURY]`.

*If the live run differs from the recorded one, say so. One sample, temperature 0, is not guaranteed identical.*

## Part 2: the failures we found (3:00–6:00)

1. **The 2024 loss on 2025 wording**: open `trace_v1_wrong_edition.json` (`tr_184a6ee0c06c`). The loss is dated
   2025-03-31, the day before ed. 04-25. Undated search returned three editions mixed, and the referral cites
   **ed. 04-25**, although `check_coverage_in_force` said ed. 03-24. Frequency: **2/5 cases** on v1 (taxonomy M5).
2. **The mode integration created**: taxonomy M1, `tr_074df177646e`. On a river flood, the agent applied the $15,000
   *surface-water* sub-limit and wrote that river overflow is "not excluded". It's false: ed. 04-25 keeps flood
   excluded. Frequency: **8/26**, and 8 of the 9 homeowners water losses after April 2025. Every part was right on its
   own.
3. **The weaknesses written before any run** (`weaknesses.md`):
   - #1, "the flood row retrieves badly": E-15 was returned in **0/26** runs.
   - #3, "three money numbers": the $15k sub-limit misapplied in 8/26 cases. The condo $250 trap held: 3/3 right.
   - #2 played out as predicted on v1, and turned into M2 on v2.
4. **The trace that fooled us**: `trace_v2_ungrounded_e15.json`. Assertions A1–A8 passed it, and the judge passed it.
   E-15 was never retrieved. That led to assertion A9.

## Part 3: a number that moved (6:00–8:00)

- **Wrong-endorsement-version citation rate: 2/4 (50%) → 0/11 (0%), on the same n=5 cases. 0/41 across the full
  suite.** (`before_after.md`)
- Say what did *not* move: those 5 cases went from 1/5 to 0/5 on every assertion, because the date fix doesn't make
  E-15 retrievable.
- **Judge agreement on integrated outputs: 21/26 = 80.8%. It does not clear 85%, so the judge is not a gate.**
  (`eval_report.md` §3; labels written by the builder, not an adjuster.)
- **One sentence on what the suite doesn't measure:** *"Nothing here measures motor, real claims, or whether the
  same claim gets the same referral twice: every number is one sample of 26 synthetic claims."*

## Part 4: what's next (8:00–10:00)

- **The eval cases that permanently guard it:** the 8 `version_straddle` cases in `evals/w12/suite.jsonl`, A5 in
  `app/triage/suite.py`, and `test_suite_fails_the_2025_wording_on_a_2024_loss_and_passes_the_right_one` in
  `backend/tests/test_triage.py` (offline, runs in `./run.sh test`).
- **Cost per claim triaged: $0.00058** (6,287 tokens, 4 model calls).
- **What breaks first in a hailstorm week:** 18,000 FNOLs = 2,571 a day = 16.2M tokens a day. The provider's daily
  token cap allows **31 claims a day**, 81× short, and already short at normal volume. The week's model bill is
  about **$10**. Not cost: capacity. (`cost_and_10x.md`)
- **Next, ranked:**
  1. Attach the in-force exclusions schedule to every search (fixes M3, and with it most of M2).
  2. Tie each sub-limit to its peril, with a code check that the sub-limit's peril matches the loss (M1).
  3. Re-validate the judge on a fresh, human-labelled set.

## Hostile questions: where the answers are

| question | answer, and where |
|---|---|
| Cases between two endorsement versions, and their scores? | 8 cases: A5 8/8, A6 6/8, A9 2/8, all assertions 0/8. `eval_report.md` §2 |
| Does it ever say "covered"? Show the assertion. | The model wrote it in 3/26 cases. `run.guard()` removed it in code, and A1 checks the output: 26/26 clean. `suite.py` A1, `test_guard_removes_decision_language` |
| The sub-limit trace and the assertion that would catch it | `trace.json` (CLM-2026-10008: $500 / $2,500 / $300,000). A7 compares all three numbers separately. |
| Reproduce claim X in 18 months? | Each trace stores model, `prompt_sha`, triage version, temperature, the retrieved chunk ids, and each cited edition with its file and line. Editions are kept in the corpus, never overwritten. What isn't pinned: the provider can retire `gpt-oss-20b`. |
| What did your MCP server hand another squad? | Policy wording only, with no claim data; its span log stores redacted arguments. `fresh_eyes.md`. The session itself hasn't happened yet. |
