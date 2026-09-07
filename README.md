# ai-ml-hub

Claims-assistant RAG over homeowners policy endorsements. Monorepo: FastAPI
backend, React + Vite frontend, and an eval harness that measures retrieval
changes against a fixed golden set — no change ships without a before and after
number on the same questions.

- **Week 3** — two chunking strategies, hit-in-top-5 over 8 known-answer questions.
- **Week 4** — separate retrieval failures from generation failures, then buy back
  hit-rate@3 with exactly ONE retrieval change. Baseline `dense` 8/12 → `hybrid`
  (BM25 + RRF k=60) 11/12, for +1.3 ms p50. Write-up: [results.md](results.md).
- **Week 5** — trace every answer, sample 20 at random from a published seed, read
  them by hand without fixing anything, and hand back a ranked failure taxonomy.
  Write-ups: [taxonomy.md](taxonomy.md) and [notes.md](notes.md); the order of
  operations is [week5/RUNBOOK.md](week5/RUNBOOK.md).

```
ai-ml-hub/
├── frontend/                  React + Vite (JS), yarn
│   ├── src/
│   ├── public/
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── backend/
│   ├── app/
│   │   ├── api/               FastAPI routes
│   │   ├── chunking/
│   │   │   ├── current_chunker.py          fixed window — the control
│   │   │   └── structure_aware_chunker.py  form/clause split
│   │   ├── ingestion/         loader + ingest CLI
│   │   ├── retrieval/
│   │   │   ├── search.py                   dense | hybrid — the ONE Week 4 variable
│   │   │   ├── lexical.py                  BM25 arm (keeps E-17 whole)
│   │   │   ├── hybrid.py                   RRF fusion, k=60
│   │   │   ├── mmr.py                      bonus only, not in the shipped path
│   │   │   ├── evaluate.py                 wk3: hit-in-top-5, both chunkers
│   │   │   ├── hitrate.py                  wk4: hit-rate@3 + p50, per retriever
│   │   │   └── inspect.py                  the inspection view + R/G/NIC labels
│   │   ├── tracing/
│   │   │   ├── redact.py                   PII out BEFORE the write, not after
│   │   │   ├── trace.py                    the record + the only writer
│   │   │   ├── traffic.py                  push a question bank through the app
│   │   │   ├── sample.py                   seeded random sample, reproducible
│   │   │   ├── replay.py                   replay from the trace alone + audit
│   │   │   ├── opencode.py                 one sentence per trace, zero-fix check
│   │   │   ├── taxonomy.py                 4-7 modes -> taxonomy.md
│   │   │   └── notes.py                    assembles notes.md from artifacts
│   │   ├── generation/        grounded answers + forced refusal
│   │   ├── models/            pydantic schemas
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── .python-version
│
├── data/endorsements/         the 6 supplied endorsements (committed)
├── traces/traces.jsonl        wk5: the redacted trace log (committed — deliverable)
├── week5/                     wk5: sample, open coding, modes, prediction, runbook
├── evals/
│   ├── traffic/               wk5: the question banks that produce the traces
│   ├── questions.json         wk3: the 8 questions + 3 out-of-corpus
│   ├── expected.json          wk3: known-correct form_number / clause
│   ├── golden_set.jsonl       wk4: 12 adjuster questions + known-correct chunk_id
│   ├── failure_labels.json    wk4: R/G/Not-In-Corpus labelling (last inspect run)
│   ├── search-dumps/          wk3 search-only dumps (committed — deliverable)
│   └── w4-runs/               wk4 before/after runs (committed — deliverable)
│
├── results.md                 the write-up that gets graded
├── Requirements/
└── .env                       from .env.example, gitignored
```

## Setup

**Backend** — Python 3.12 (3.14 has no torch/chromadb wheels).

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env        # add LLM_API_KEY
```

**Frontend** — yarn only.

```bash
cd frontend && yarn install
```

## Run

```bash
# 1. index the 6 endorsements under both strategies (not the whole library)
cd backend
python -m app.ingestion.ingest --strategy current --reset
python -m app.ingestion.ingest --strategy structure_aware --reset

# 2. week 3 — both strategies, same 8 questions
python -m app.retrieval.evaluate --markdown

# 3. week 4 — the before number, the labels, then before -> after
python -m app.retrieval.hitrate --retrievers dense --markdown            # baseline first
python -m app.retrieval.inspect --retriever dense --answers --markdown   # R / G / Not-In-Corpus
python -m app.retrieval.hitrate --retrievers dense hybrid --markdown     # the one change
python -m app.retrieval.hitrate --retrievers hybrid --mmr --lambda 0.7   # bonus

# 4. one-off search, with and without the metadata filter
python -m app.retrieval.search "does E-17 apply to a burst supply line?"
python -m app.retrieval.search "..." --policy-line homeowners
python -m app.retrieval.search "..." --retriever hybrid

# 5. grounded answer (refuses when the corpus can't source it) — writes a trace
python -m app.generation.answer "..." --json

# 6. week 5 — traffic, then sample, then read. Full order in week5/RUNBOOK.md
python -m app.tracing.traffic --bank traffic
python -m app.tracing.sample --seed 20260907 --n 20 --source traffic
python -m app.tracing.replay <trace_id> --json > ../week5/replay.json
python -m app.tracing.opencode --start && python -m app.tracing.opencode --next
python -m app.tracing.taxonomy --write && python -m app.tracing.notes --write

# 7. serve the API, then the UI — the Inspect tab is the inspection view
uvicorn app.main:app --reload --port 8000
cd ../frontend && yarn dev        # http://localhost:5173
```

## Tests

```bash
python -m pytest backend/tests -q
```

The tests guard the invariants each change exists for: an exclusion row is never
separated from its table header or its form number (chunking); RRF fuses ranks
rather than scores and the BM25 tokenizer keeps `E-17` and `HO-0304` whole
(retrieval); and a claim number never reaches the trace file while `HO-0304`
always does, the same seed always redraws the same 20 traces regardless of file
order, and a trace carries everything replay needs (tracing).

## Rules this repo enforces in code

- **Every chunk carries `source_file`, `form_number`, `policy_line`, `edition_date`.**
  A chunk missing any of them aborts the ingest — it can't be cited later.
- **Refusal is forced, not suggested.** The grounding prompt in
  [answer.py](backend/app/generation/answer.py) forbids judgement, general
  knowledge, and partial answers. An invented coverage answer is a bad-faith exposure.
- **Citations are verified.** Every `[chunk_id | form | clause]` is resolved
  against the store; unresolvable ones are surfaced, not swallowed.
- **One variable per run.** Change the chunker, the embedding model, or the
  retriever — never two in the same run, or the number tells you nothing about
  which one earned it.
- **Ranks fuse, scores don't.** [hybrid.py](backend/app/retrieval/hybrid.py) fuses
  the dense and BM25 rankings with RRF. Cosine and BM25 are not on the same scale;
  adding or averaging them hands every query to whichever arm has bigger numbers.
- **A hit is the gold `chunk_id`, not a near-miss.** Week 4 scores strictly, so
  "three fluent water-damage clauses, none of them E-17" cannot score as a pass.
- **Latency is reported with its build cost separated.** The one-time BM25 index
  build is timed on its own, never smeared into the per-query p50.
- **Traces are redacted before the write, never after.** `tracing.write()` runs
  every string through [redact.py](backend/app/tracing/redact.py) on the way to
  the file; there is no path to the file handle that skips it. Form numbers and
  exclusion codes are deliberately spared — they are corpus vocabulary, not PII.
- **A trace that cannot be replayed is not a trace.** Prompt version, system and
  rendered prompt, model, params, and every retrieved chunk_id with its score
  travel in the record, so [replay.py](backend/app/tracing/replay.py) never
  touches the app that produced it.
- **Observations before categories.** The open-coding tool refuses sentences
  carrying diagnosis words, and proves no code changed while the traces were
  being read by fingerprinting the working tree at the start and comparing.
