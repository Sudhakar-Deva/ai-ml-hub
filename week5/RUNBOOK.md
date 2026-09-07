# Week 5 runbook — the order matters

Every step below depends on the one before it being finished and untouched.
Doing them out of order is how the common mistakes in the brief happen.

## 0. Prerequisite — the key

Generation traces need the model that produced them.

```bash
cp .env.example .env       # then set LLM_API_KEY
```

Nothing after this point can be faked. A taxonomy built on invented traces
describes an app that does not exist.

## 1. Generate the traffic

```bash
cd backend
python -m app.tracing.traffic --bank traffic          # 77 adjuster questions
python -m app.tracing.traffic --bank demo             # 10 curated ones (bonus)
```

The banks in `evals/traffic/` were written before anything was run, as traffic
gets typed rather than as demos get chosen. Reruns resume rather than duplicate.
Traces land in `traces/traces.jsonl`, redacted on the way in.

## 2. Prove a trace is replayable

```bash
python -m app.tracing.replay <trace_id> --audit                  # completeness only
python -m app.tracing.replay <trace_id> --json > ../week5/replay.json
```

Replay reads nothing but the trace: not the store, not today's prompt. If a
field is missing it fails and names it.

## 3. Draw the sample — seeded, and published

```bash
python -m app.tracing.sample --seed 20260907 --n 20 --source traffic
```

`--source traffic` keeps the curated demo set out of the random draw. The seed,
the population size and a fingerprint of the population are written to
`week5/sample.json` so anyone can redraw the identical 20.

## 4. Open-code all 20 — and change nothing

```bash
python -m app.tracing.opencode --start        # pins the code you are reading
python -m app.tracing.opencode --next         # prints the next uncoded trace
python -m app.tracing.opencode --code tr_xxxx "What I saw, in one sentence."
python -m app.tracing.opencode --status       # progress + the zero-fix check
```

One sentence per trace, describing what you SAW. Not the category, not the fix.
"I don't know why this failed" is permitted and valuable. Sentences containing
diagnosis words are refused at entry. `--status` reports
`zero_fixes_during_coding` by comparing the working-tree fingerprint against the
one taken at `--start`; the zero is graded, so it is measured, not asserted.

**Do not fix the thing you find at trace 6.** You would then have 14 traces from
a different system.

## 5. Cluster into 4–7 named modes

Write `week5/modes.json` by hand — the clustering is the judgement being graded:

```json
{"modes": [
  {"name": "applies the wrong form edition's exclusion list",
   "severity": "wrongly-denies",
   "trace_ids": ["tr_a", "tr_b"],
   "example": "tr_a",
   "note": "optional"}
]}
```

`severity` is one of `wrongly-denies`, `wrongly-pays`, `annoys-adjuster`, or
`none` for traces where nothing went wrong. Every sampled trace goes in exactly
one mode. Names must say what happened in terms a claims manager can act on —
`retrieval issue` is rejected by the validator.

```bash
python -m app.tracing.taxonomy --write        # -> taxonomy.md
```

## 6. Write and commit the prediction, before any fix

Fill `week5/prediction.md`, then:

```bash
git add week5/prediction.md && git commit -m "week 5: dated prediction before any fix"
git log -1 --format=%H       # paste this hash into notes.md
```

## 7. Assemble the write-up

```bash
python -m app.tracing.notes --write           # -> notes.md
```

`notes.md` is generated from the artifacts, never typed. Missing sections are
reported as missing rather than quietly dropped.
