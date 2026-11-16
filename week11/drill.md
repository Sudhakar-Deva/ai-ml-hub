# Drill: find the coverage answer that ignored an exclusion

**Time-to-find: 00:09.** **Slice that found it: time + output** (`--day 2026-11-15 --position COVERED`), then input
fingerprint (`notes_sha`) to separate the one unknown claim from the known ones.

| | |
|---|---|
| complaint (all I was given) | "an adjuster says it told a claimant something was covered when the policy excludes it, sometime yesterday." |
| planted by | **a Claude subagent acting as squadmate** (no human squadmate was available). It wrote new adjuster notes, ran them through the real app with a `ts` yesterday, retried until the app genuinely answered COVERED (2 attempts), sealed the answer in a file and reported only the complaint. I opened the sealed file after the find. If your course requires a human squadmate, re-run with one: the procedure is identical. |
| log searched | `week11/obs/requests.jsonl`: 22 requests on 2026-11-15 (20 replayed traffic + the squadmate's 2) |
| clock | [drill_clock.txt](drill_clock.txt): start 08:24:52 UTC, found 08:25:01 UTC (wall clock, including my reading time) |
| found | `req_e9fffc122627`, ADJ-412, 10:22 yesterday, homeowners, `claims-summary-v1`, COVERED / exclusions NONE |
| confirmed | sealed answer: same request_id; correct position DENIED, HO-0304 **E-22** |

## The three steps

1. **The complaint describes the OUTPUT ("said it was covered") and a TIME ("yesterday"), so I sliced on both.**
   `python -m app.obs.find --day 2026-11-15 --position COVERED` returned **5 of 22** requests.
2. **Fewer COVERED answers should be legitimate than that.** Yesterday's traffic re-opened each fixed claim twice, and only
   the clean burst (10001) and the covered loss assessment (10005) are COVERED, so 4 are expected and one is extra. The two
   condo rows are the assessment. Of the three homeowners rows, two share `notes_sha f28c5663c1fa` (the clean burst, opened
   by two adjusters).
3. **The third, `req_e9fffc122627`, has its own fingerprint:** a claim nobody else touched ("storm damage to ceilings").
   Its `retrieved_context_ids` held **3 condo chunks and no HO-0304 E-22**, which is the bad answer and its cause in one hop.

## Why it was fast, and the field that would have cost the time

The log indexes the **output** (`output.coverage_position`) as well as the input. Without it I'd have had to regex the free
text of 22 summaries for "covered", which also matches "E-17 … is covered" in denials. The field whose absence would have
cost the most is **`retrieved_context_ids`**: without it I could see the wrong call but not whether retrieval missed E-22 or
the model ignored it. The answer was the first: E-22 was never in the context.

**Honest limits.** 22 requests is a small day, so the slice reduced it to 5 by hand-countable reasoning. At real volume,
step 2 needs an index such as "COVERED with none of the declared line's exclusions in context". That's the bonus field,
which I didn't build (see README).
