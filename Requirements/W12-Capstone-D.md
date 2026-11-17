<!-- Soft Suave · The AI Engineering League -->
# Week 12 Capstone — Variant D

## Claims Triage & Coverage Assistant

| | |
|---|---|
| Domain | Insurance claims |
| Duration | Week 12 — Monday to Friday, 1 hr/day + the Friday demo |
| Marks | 100 |
| Gate | **M6 — end-to-end app + closed loop → AI Summit & certification** |

> **Nothing new to learn — deliberately.** This is an integration and defence of eleven weeks of artifacts you already have. If you find yourself building something new, that's anxiety, not engineering.


---

## 1. The brief

The client is a mid-size general insurer whose motor and household adjusters spend the first 20 minutes of every claim doing the same thing: finding the policy, checking it was in force on the loss date, and reading the exclusions schedule to see whether this loss is even arguable. At ~1,800 FNOLs a month that is a full-time team's worth of hours spent on lookup rather than judgement. Their compliance function has one hard rule that came out of a regulator's finding: nothing automated may state a coverage decision — it may only surface the wording and the facts an adjuster then decides on. Their live wound is a 2024 flood claim assessed against the 2025 exclusion wording, because the newer document simply read better to whoever searched it. They want a system that triages a claim, retrieves the policy wording IN FORCE ON THE LOSS DATE, cites the exclusion by clause and endorsement version, keeps deductible and sub-limit distinct, and refers to a human rather than saying the word "covered".

### Corpus

The motor and household policy wordings (~60 pages each) including the exclusions schedule, plus BOTH the 2023 and 2025 endorsement sets; 500 anonymised claim files with FNOL text, adjuster notes, photo captions, and the final coverage decision with its reason code; the deductible / sub-limit / policy-limit table by product; and the coverage-in-force date ranges per policy number. The two endorsement sets are the point: the flood exclusion was rewritten in 2025, and a loss dated August 2024 must be decided against the wording in force on THAT date, not the wording that happens to retrieve best today. The adjuster notes are your Week-5 random sample and your PII problem simultaneously — they contain names, addresses and injury descriptions, and your MCP server will hand whatever you don't redact to another squad's agent on Thursday.


---

## 2. Requirements

1. Your Week 3–4 RAG pipeline, wired in behind the single entry point and answering a real claim question with clickable citations to clause — the citation must name the ENDORSEMENT VERSION and the loss date it was resolved against, or it does not count as a citation here
2. Your Week 7 hand-built agent loop, running against the integrated retriever with at least three tools — policy lookup by claim/policy number, coverage-in-force check against the loss date, and refer-to-adjuster — of which the tools reachable over MCP are discovered at runtime, not hardcoded
3. One MCP server of your own exposing a genuine capability (your policy-wording search, scoped by product and date, is the obvious one), called live by a client that isn't yours — Thursday's fresh-eyes reviewer from another squad is that client
4. Your Week 6 eval suite running against the INTEGRATED system in one command: 25–40 cases, assertions before judges, and your validated judge re-checked on integrated outputs — report its agreement against your hand labels as a number, and it must still clear 85%
5. Your Week 5 error taxonomy re-scored on the integrated system: 4–7 named modes with frequency %, severity, and one trace id each. At least one mode must be NEW — created by integration, not inherited from the parts
6. Your Week 8 trajectory eval over 10+ cases on the integrated agent, reporting tool-choice accuracy and your outcome-vs-trajectory gap as numbers — the gap is the honest one, so show it even when it embarrasses you
7. Week 11 per-request logging surviving both the agent hop and the MCP hop: one trace id from FNOL in to referral out, cost and latency per span, and the PII line held — claimant names, addresses and injuries out of the logs and out of anything your MCP server returns
8. One closed failure→test loop demonstrated live on the integrated system, plus cost per claim triaged and a 10× plan naming what breaks first at catastrophe-event volume (a hailstorm week is 18,000 FNOLs), with the number behind it


---

## 3. Expected output

One repo a stranger can clone and run — one command, one entry point — containing the integrated system, the eval suite that runs against it, Tuesday's unedited seam list, the one-page architecture sketch, the eval report with its stated non-coverage, the top-3 weaknesses you wrote down on Wednesday before anyone asked, and the 10-minute demo script. Plus the demo, delivered live to the clock.


---

## 4. Evaluation rubric

| Criterion | Points |
|---|---|
| Failure-finding & error analysis — the integrated system's taxonomy with frequencies and trace ids, the traces you actually read, and the top 3 weaknesses you wrote down before anyone asked. A demo where nothing failed scores zero here. | 30 |
| A number that moved — before → after on a named metric, with sample size, judge-agreement rate, and an explicit statement of what your suite does NOT cover. Adjectives score zero. | 25 |
| Integration completeness — RAG + agent + MCP consumed AND exposed + evals + logging behind one entry point, from one command, with one trace id surviving every hop. No points for UI. No points for polish. No points for "it works". | 20 |
| Application depth — does it behave like it has actually worked claims: coverage-in-force checked against the loss date, the exclusion cited by clause AND endorsement version, deductible and sub-limit and policy limit kept as three distinct numbers, and referral to an adjuster preferred over the word "covered". | 15 |
| Iteration thinking — what you'd do next, ranked and costed: the closed failure→test loop, the cost/query number, and the 10× plan naming what breaks first. | 10 |
| **Total** | **100** |


---

## 5. The 10-minute demo — the four-part standard

1. Part 1 — a real run: a live FNOL in, coverage-in-force checked against the loss date via a visible tool call, the exclusion cited by clause and endorsement version, deductible and sub-limit reported as separate numbers, and the claim referred to an adjuster rather than decided.
2. Part 2 — the failures you found: the trace where a 2024 loss got assessed against the 2025 flood wording (or whatever your top mode turned out to be), its frequency in the re-scored taxonomy, the mode that integration created, and the two other weaknesses you wrote down on Wednesday before anyone asked.
3. Part 3 — a number that moved: wrong-endorsement-version citation rate before → after, with n, the judge's agreement rate on the integrated system's outputs, and one sentence on what your suite does not measure at all.
4. Part 4 — what's next: the eval case that now permanently guards that failure, cost per claim triaged, and what breaks first in a hailstorm week at 18,000 FNOLs — named, with the number that proves it, not a shrug.

*A flawless demo is a red flag. Show the failure you found and how you know it's fixed.*


---

## 6. Hostile questions you will be asked

- The loss is dated 11 August 2024 and your system cited the 2025 flood exclusion. How many of your eval cases have a loss date falling between two endorsement versions, and what do those cases score — not the average, those.
- It said "covered" and we paid out. Who is liable — you, or my adjuster? And does your system ever actually say "covered", or does it only ever refer with citations? Show me the assertion that enforces that, not the prompt that asks for it.
- Deductible, sub-limit and policy limit are three different numbers and juniors confuse them weekly. Show me the trace where it got the sub-limit right, and the eval assertion that would have caught it if it hadn't.
- The regulator asks why claim 4471-A was declined, eighteen months from now. Can you reproduce that exact answer — same wording version, same retrieved context, same model — and prove it? Show me the trace, not the log view.
- Adjuster notes carry the claimant's name, address and injuries. What is in your logs, and what exactly did your MCP server hand to another squad's agent on Thursday?


---

## 7. Bonus challenge

Loss-date-aware retrieval, proven. Make the retriever resolve the wording in force on the loss date rather than the latest wording — a date filter your code enforces, not a hint in the prompt. Add 5 eval cases whose loss dates straddle the 2025 endorsement, including one loss dated the day before it took effect, and show all 5 red before and green after. Then report what the date filter cost you in hit-rate@3 on the cases that DON'T straddle a version boundary, because it will have cost you something.


---

## 8. Submission checklist

- [ ] One command that runs the integrated system end to end, plus the README a stranger actually used
- [ ] Tuesday's seam list, unedited, each seam marked fixed / accepted / ran-out-of-time
- [ ] The one-page architecture sketch: boxes, arrows, where the model calls happen, where the money goes
- [ ] Full eval-suite output on the integrated system: pass rate per taxonomy mode, n, and the judge-agreement number
- [ ] The re-scored error taxonomy, with the mode integration created called out
- [ ] Trajectory eval results + the outcome-vs-trajectory gap
- [ ] One end-to-end trace with cost and latency per span, trace id intact across the agent and MCP hops
- [ ] Your top 3 known weaknesses, dated Wednesday, unprompted
- [ ] Cost per claim triaged + the 10× plan naming the first thing that breaks
- [ ] The fresh-eyes note: who from which squad ran it, where they stumbled, what you changed


---

## 9. Common mistakes

- **Rebuilding the policy-wording ingestion on Tuesday because the exclusions schedule parsed badly — Week 12 is four hours and nothing new to learn. The Week-4 pipeline with a measured hit-rate is the one that produces a number by Friday; put the parse quality in your known limits instead.**
- **Demoing a clean covered / not-covered call that runs perfectly. A flawless demo is a red flag: the rubric pays 30 points for the loss-date failure you found and zero for the run that never breaks.**
- **Retrieving the 2025 flood exclusion for a 2024 loss because it ranked highest. Coverage is decided against the wording in force on the loss date — "the retriever preferred it" is not a defence anyone in claims, or compliance, will sit through.**
- **Letting your system emit the word "covered" at all. It triages and cites; the adjuster decides. If you skipped the referral path because it made the demo less impressive, you built a regulatory finding with a chat window on it.**
- **Piping raw adjuster notes into your logs and out through your MCP server without redaction, because it was your own server and you trusted it. Another squad's agent called that server on Thursday. Say out loud what it saw.**
- **Reporting overall pass rate across all 500 claim files as the number that moved. The average hides the regression — the panel wants pass rate on the exclusion cases specifically, per mode, and will ask for exactly that.**


---

*Variant D of 6. All six are equivalent in difficulty and graded on the same rubric.*
