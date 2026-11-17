# Eval report: the integrated system

**One command:** `./run.sh eval v2-after`, which runs `app.triage.suite` (26 cases through the real entry point, MCP and
all) and then `app.triage.trajectory`. The judge is `./run.sh judge v2-after`. Model `openai/gpt-oss-20b`, temperature 0,
one sample per case. The full machine output is in [suite_v2-after.md](suite_v2-after.md),
[suite_v1-before.md](suite_v1-before.md), [before_after.md](before_after.md) and [trajectory.md](trajectory.md).

## 1. The number that moved

**Wrong-endorsement-version citation rate: 2/4 citations (50%) → 0/11 (0%). Cases citing a wrong edition: 2/5 → 0/5.**

Measured on the same 5 cases (n=5), whose loss dates straddle the 2025 HO-0304 edition. Before is `triage-v1`, the
parts as they were: the Week 9 MCP search with no loss date. After is `triage-v2`: the loss date is a required tool
argument, enforced as `effective_from ≤ loss_date ≤ effective_to` in the Chroma query (`retrieval/search.py`,
`build_where`). The same metric across all of v2: **0/41 citations, 0/24 in-force cases.**

What did not move: on those 5 cases, **pass-every-assertion went from 1/5 to 0/5.** The date fix removed the wrong
edition, but it didn't put the flood row in front of the model: E-15 was returned in **0 of 26** v2 runs (taxonomy M3).
Before the fix, an ungrounded E-15 citation also carried the wrong edition and got caught. After it, the edition is
right and only A9 catches it. The one "before" pass (CLM-2025-20003, loss dated 2025-04-01) passed only because the
newest edition happens to be the one in force on that day.

## 2. Full suite, per mode (`triage-v2`, n=26)

**7/26 (27%) pass every applicable assertion.**

| mode | n | pass | what the mode tests |
|---|---|---|---|
| version_straddle | 8 | **0/8** | loss dates in 2023, 2024 and on both sides of 2025-04-01 |
| notes_exclusion | 5 | 0/5 | an exclusion only the adjuster notes reveal |
| sub_limit | 4 | 3/4 | jewelry B, fungi A, condo loss assessment |
| policy_line_trap | 2 | 2/2 | dwelling-fire E-17 has no sudden-rupture exception |
| coverage_gap | 2 | 2/2 | lapse between terms / loss before inception |
| clean | 2 | 0/2 | |
| flood_wording | 1 | 0/1 | river overflow |
| missing_info | 1 | 0/1 | no adjuster notes |
| decision_bait | 1 | 0/1 | insured asks for "covered" in writing |

| assertion (code, before any judge) | pass |
|---|---|
| A1 no decision language reaches the adjuster | **26/26** (guard removed 3 cases' sentences) |
| A2 ends in refer_to_adjuster | 26/26 |
| A3 in-force checked with the loss date, and right | 26/26 |
| A4 citation names form + edition + clause, and it exists | 26/26 |
| A5 cited edition was in force on the loss date | 24/24 |
| A6 governing clause cited at the governing edition | **11/20** |
| A7 deductible, sub-limit, policy limit each right | **17/24** |
| A8 no name / address / injury anywhere in the trace | 26/26 |
| A9 every cited clause was actually retrieved | **11/24** |

A9 was added after reading trace `tr_b10ee85439fa` (see [taxonomy.md](taxonomy.md)). It is applied to every run
identically, and it moved v2 from 13/26 to 7/26. One scorer bug was also fixed: a section cited as "B. Other special
limits" was not normalised to "B". The fix applies identically to all runs.

**The hostile question, answered with numbers.** 8 eval cases have a loss date that falls within a specific HO-0304
edition window adjacent to a boundary (2023-09-02, 2024-02-10, 2024-03-05, 2024-08-11, 2025-02-14, 2025-03-31,
2025-04-01, 2025-06-20). They score **8/8 on the right edition (A5), 6/8 on naming the governing clause at the governing
edition (A6), 2/8 on having actually retrieved what they cite (A9), and 0/8 on pass-every-assertion.** Of the 6 flood
or surface-water losses among them, 5 cite E-15 without any search having returned it. The sixth (CLM-2025-20004,
brook overflow) doesn't cite E-15 at all.

## 3. Judge, re-checked on integrated outputs

Judge v3 is v1's criterion restated for a referral, which has no coverage position
([evals/w12/judge_v3.txt](../evals/w12/judge_v3.txt)). Model `gpt-oss-120b` (the Week 6 judge model), temperature 0.
The hand labels ([evals/w12/labels.json](../evals/w12/labels.json)) were written before the judge's first call.

**Agreement: 21/26 = 80.8%. It does NOT clear the 85% gate.** It catches 16/19 labelled failures and passes 5/7
labelled passes.

- 2 disagreements: the judge isn't shown the coverage-in-force result, so it calls a correct "not in force, no clause"
  referral a failure. That's a gap in the judge's context.
- 3 disagreements: E-15 cited but never retrieved, and the judge said "supported by the retrieved text". A judge
  doesn't notice absence well, which is why A9 now checks it in code.

I didn't edit the judge and re-score it on these same 26 labels: that would tune it to the labels. The judge is
**not used as a gate**; the assertions are. Next: give it the in-force result, hand criterion (c) to A9, and validate
it on a fresh labelled set.

**Who labelled:** the labels were written by Claude, the assistant that built the system, not by a claims adjuster.
They are the system builder's labels and should be re-done by a person before anyone relies on the 80.8%.

## 4. Trajectory (Week 8), on the integrated agent

**Tool-choice accuracy 101/101 = 100%. Trajectory pass 26/26. Outcome pass 7/26. Outcome-vs-trajectory gap: −73.1
points.** Every wrong referral took the right path. The failures are in what the tools returned (M3) and what the
model did with it (M1, M2, M4), not in which tool it called. (The first report scored the two correct
"in-force → refer" paths for lapsed policies as failures; the expected path was fixed.)

## 5. Bonus: loss-date-aware retrieval, proven

- The date filter is code, not prompt: `build_where(..., loss_date)` adds the range clauses, and a malformed date
  raises instead of silently dropping the filter (`test_bad_loss_date_raises_instead_of_dropping_the_filter`).
- **5 cases straddling the 2025 edition**, including **2025-03-31, the day before it took effect**. Before: 4/5 red
  (CLM-2025-20003 was green, because the newest edition was the right one that day). After: **0/5 cite a wrong
  edition**, but **0/5 are fully green** (M2, M3). Not "all 5 red then all 5 green". Stated as measured.
- **Cost of the filter in hit-rate@3 on 12 cases that don't straddle** (notes as the query, offline): undated **5/12**,
  dated **6/12**. On this set it didn't cost hit-rate; it gained one case, because undated, three copies of the same row
  crowd the top 3. The real cost is elsewhere. A loss before 2024-05-01 can't retrieve HO-0417 (definitions) or
  HO-0521 (limits) at all, because no edition of either was in force. Earlier editions of those forms aren't in the
  corpus, and the filter hides that gap instead of papering over it.

## 6. What this suite does NOT cover

- **Motor.** No motor wording, no motor claims. Homeowners, dwelling-fire and condo only.
- **Real claims.** All 26 claims and both added editions are synthetic, written for this week. Only HO-0304 has more
  than one edition.
- **Endorsement changes mid-term, or across a policy renewal.** The edition is resolved by loss date only, never by
  the edition attached at inception.
- **Variance.** One sample per case at temperature 0. No case was re-run to see whether the same input gives the same
  referral.
- **Load.** Nothing here measures behaviour under concurrency. The 10× plan is arithmetic from measured per-claim
  numbers.
- **PII recall on unseen formats.** Redaction is regex. It was tested on these notes, not on 500 real files.
- **The human.** No adjuster has read a referral. The labels are the builder's.
