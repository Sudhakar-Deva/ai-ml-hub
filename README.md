# ai-ml-hub

Claims-assistant RAG over homeowners policy endorsements. Monorepo: FastAPI
backend, React + Vite frontend, and an eval harness that measures two chunking
strategies against the same 8 known-answer questions.

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
│   │   ├── retrieval/         store, search, evaluate
│   │   ├── generation/        grounded answers + forced refusal
│   │   ├── models/            pydantic schemas
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── .python-version
│
├── data/endorsements/         the 6 supplied endorsements (committed)
├── evals/
│   ├── questions.json         the 8 questions + 3 out-of-corpus
│   ├── expected.json          known-correct form_number / clause
│   └── search-dumps/          search-only dumps (committed — deliverable)
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

# 2. the number that matters — both strategies, same 8 questions
python -m app.retrieval.evaluate --markdown

# 3. one-off search, with and without the metadata filter
python -m app.retrieval.search "does E-17 apply to a burst supply line?"
python -m app.retrieval.search "..." --policy-line homeowners

# 4. grounded answer (refuses when the corpus can't source it)
python -m app.generation.answer "..." --json

# 5. serve the API, then the UI
uvicorn app.main:app --reload --port 8000
cd ../frontend && yarn dev        # http://localhost:5173
```

## Tests

```bash
python -m pytest backend/tests -q
```

The tests guard the one invariant the second chunker exists for: an exclusion
row is never separated from its table header or its form number.

## Rules this repo enforces in code

- **Every chunk carries `source_file`, `form_number`, `policy_line`, `edition_date`.**
  A chunk missing any of them aborts the ingest — it can't be cited later.
- **Refusal is forced, not suggested.** The grounding prompt in
  [answer.py](backend/app/generation/answer.py) forbids judgement, general
  knowledge, and partial answers. An invented coverage answer is a bad-faith exposure.
- **Citations are verified.** Every `[chunk_id | form | clause]` is resolved
  against the store; unresolvable ones are surfaced, not swallowed.
- **One variable per run.** Change the chunker or the embedding model, never both.
