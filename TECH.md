# Tech Guide — What Is Used, Where, and Why

Every technology and technique in this project, with **where it lives** and **what it's for**, explained in plain language.

- **Section 1:** tools and libraries (the software the project is built with)
- **Section 2:** techniques (the ideas and methods)
- **Section 3:** a map of every folder and file
- **Section 4:** one question followed from start to finish
- **Section 5:** all the settings you can change

For the demo script, see [DEMO.md](DEMO.md). For the full course theory, see [Requirements/COMPLETE-GUIDE.md](Requirements/COMPLETE-GUIDE.md).

---

## The app in one picture

```
  Adjuster types a question in the browser
                 │
                 ▼
  ┌──────────────────────────┐
  │  FRONTEND (React + Vite) │   the web page you see
  └────────────┬─────────────┘
               │  sends the question
               ▼
  ┌──────────────────────────┐
  │  BACKEND (FastAPI)       │   the "brain" running on your computer
  │                          │
  │  1. SEARCH ──────────────┼──► ChromaDB (meaning search)
  │                          │    + BM25    (keyword search)
  │                          │    combined with RRF
  │                          │
  │  2. ASK THE AI ──────────┼──► Groq (gpt-oss-120b model)
  │                          │
  │  3. CHECK THE SOURCES    │
  │  4. SAVE A RECORD (trace)│
  └────────────┬─────────────┘
               │  answer + sources
               ▼
  Shown on the web page
```

---

## 1. Tools and libraries

### Programming languages

| Tool | Where | What it's for |
|---|---|---|
| **Python 3.12** | Everything in [backend/](backend/) | The main language for search, AI calls, tests and measurements. Version 3.12 specifically, because some libraries (torch, chromadb) don't work on 3.14 yet. |
| **JavaScript (React)** | Everything in [frontend/](frontend/) | The web page you use in the demo. |

### Backend (the "brain")

| Tool | Where | What it's for |
|---|---|---|
| **FastAPI** | [backend/app/main.py](backend/app/main.py), [backend/app/api/routes.py](backend/app/api/routes.py) | Creates the web addresses the page talks to, like `/api/search` and `/api/ask`. It also gives you a free test page at http://127.0.0.1:8000/docs. |
| **uvicorn** | The command `uvicorn app.main:app` | The server program that runs FastAPI and keeps it listening for requests. |
| **Pydantic** | [backend/app/models/schemas.py](backend/app/models/schemas.py) | Checks that incoming requests have the right fields and types, for example that a question is text. |
| **python-dotenv** | [backend/app/config.py](backend/app/config.py) | Reads secret settings, such as your API key, from the `.env` file so they're never written into the code. |

### Search

| Tool | Where | What it's for |
|---|---|---|
| **ChromaDB** | [backend/app/retrieval/store.py](backend/app/retrieval/store.py). Data is saved in `backend/.chroma/` | A **vector database**: it stores every document piece along with a list of numbers describing its meaning, and finds the pieces closest in meaning to a question. It runs inside the app, so no separate server is needed. |
| **sentence-transformers** (model: `all-MiniLM-L6-v2`) | Loaded in [backend/app/retrieval/store.py](backend/app/retrieval/store.py) | The **embedding model**: turns text into 384 numbers that capture its meaning, so similar sentences get similar numbers. It runs on your own computer: free, fast, no internet needed. |
| **rank-bm25** | [backend/app/retrieval/lexical.py](backend/app/retrieval/lexical.py) | **Keyword search** (like a smart Ctrl+F). It finds exact words and codes such as `E-17`, which the meaning search is bad at. This was the fix in Week 4. |
| **pypdf** | [backend/app/ingestion/loader.py](backend/app/ingestion/loader.py) | Reads text out of PDF files, in case the policy documents are PDFs. |

### AI model

| Tool | Where | What it's for |
|---|---|---|
| **Groq** (model: `openai/gpt-oss-120b`) | [backend/app/llm.py](backend/app/llm.py) | The AI that writes answers, writes claim summaries, grades summaries (the "judge"), and runs the agent. Groq is the company hosting the model. |
| **httpx** | [backend/app/llm.py](backend/app/llm.py) | Sends the web requests to Groq. It was already installed, so no extra package was needed. |
| **Anthropic SDK** | [backend/app/llm.py](backend/app/llm.py) (optional path) | A backup option. Set `LLM_PROVIDER=anthropic` in `.env` to use Claude models instead. It isn't used right now. |

### Frontend (the web page)

| Tool | Where | What it's for |
|---|---|---|
| **React 18** | [frontend/src/](frontend/src/) | Builds the screens and tabs. |
| **Vite** | [frontend/vite.config.js](frontend/vite.config.js) | Runs the page during development (`yarn dev`) and forwards `/api/...` requests to the backend. |
| **yarn** | [frontend/package.json](frontend/package.json) | Installs the frontend's packages. |

### Testing

| Tool | Where | What it's for |
|---|---|---|
| **pytest** | [backend/tests/](backend/tests/) (94 tests) | Automatically checks the important rules still hold after any code change (details in §2.9). Run with `python -m pytest backend/tests -q`. |

---

## 2. Techniques: what each idea is and where it's used

### 2.1 RAG (Retrieval-Augmented Generation)

- **Plain meaning:** "Find the right pages first, then let the AI answer from those pages only."
- **Why:** An AI on its own knows nothing about *our* policy documents and would invent an answer. RAG makes it answer from real text and show its source.
- **Where:** the whole flow in [backend/app/generation/answer.py](backend/app/generation/answer.py): search → build the prompt → ask the AI → check the sources.

### 2.2 Loading documents and their labels (ingestion)

- **Plain meaning:** Reading the 6 policy documents and labelling each one.
- **Where:** [backend/app/ingestion/loader.py](backend/app/ingestion/loader.py) reads the files. [backend/app/ingestion/ingest.py](backend/app/ingestion/ingest.py) saves them into the database.
- **The 4 labels on every piece:** `source_file` (file name), `form_number` (e.g. HO-0304), `policy_line` (homeowners / dwelling_fire / condo), `edition_date` (e.g. 03-24).
- **Why:** The labels make it possible to show sources ("this came from HO-0304") and to filter searches. **If a label is missing, loading stops with an error**, because a piece with no label could never be cited.
- **The documents:** [data/endorsements/](data/endorsements/). The 6 files, e.g. `HO-0304-ed-03-24.md`.

### 2.3 Chunking (cutting documents into pieces)

- **Plain meaning:** Documents are too long to search as a whole, so they're cut into small pieces ("chunks"), each about a paragraph.
- **Two methods were compared (Week 3):**

| Method | Where | How it cuts | Purpose |
|---|---|---|---|
| **Fixed-size** ("current") | [backend/app/chunking/current_chunker.py](backend/app/chunking/current_chunker.py) | Every 1,000 characters, with 150 characters of overlap | The **baseline** to compare against. Kept deliberately simple. |
| **Structure-aware** (used by the app) | [backend/app/chunking/structure_aware_chunker.py](backend/app/chunking/structure_aware_chunker.py) | Along section headings; an exclusion row is **never** separated from its table header and document code | Each piece stays meaningful and always carries its document code |

- **Shared helper:** [backend/app/chunking/common.py](backend/app/chunking/common.py) gives both methods the same labels and the same ID format, so the **only** difference between them is how they cut.
- **Chunk ID format:** `structure_aware:HO-0304:HO-0304-ed-03-24.md:0004`, meaning method : document : file : piece number. This is the ID that appears in citations.

### 2.4 Embeddings and meaning search (dense retrieval)

- **Plain meaning:** Each piece is turned into a list of numbers that represent its meaning. A question is turned into numbers the same way, and the pieces with the closest numbers are returned.
- **Where:** [backend/app/retrieval/store.py](backend/app/retrieval/store.py) (the database and the model), [backend/app/retrieval/search.py](backend/app/retrieval/search.py) (the search).
- **Good at:** "pipe burst under the sink" finds "sudden discharge from a plumbing system", even with no shared words.
- **Bad at:** exact codes. "E-17" and "E-19" look almost the same to it. This weakness is what Week 4 fixed.
- **Named "dense"** in the app's dropdowns.

### 2.5 Keyword search (BM25)

- **Plain meaning:** Finds pieces containing the exact words of the question, giving more weight to rare words.
- **Where:** [backend/app/retrieval/lexical.py](backend/app/retrieval/lexical.py).
- **Why:** Codes like `E-17` and `HO-0304` are rare words, so BM25 ranks the pieces containing them near the top.
- **A detail that matters:** the word splitter keeps `E-17` as one word, and also stores `E` and `17` separately, so "HO 0304" written without a dash still matches.

### 2.6 Combining both searches (Hybrid search + RRF)

- **Plain meaning:** Run both searches, then merge the two result lists into one.
- **Where:** [backend/app/retrieval/hybrid.py](backend/app/retrieval/hybrid.py).
- **How they're merged:** **Reciprocal Rank Fusion (RRF).** Each piece gets points based on its **position** in each list: `1 ÷ (60 + position)`. Pieces near the top of either list end up on top.
- **Why position and not score:** The two searches score on different scales, like kilograms vs kilometres. Adding them would let one search overpower the other every time.
- **Named "hybrid"** in the app's dropdowns. **This is what the app uses** (`SHIPPED_RETRIEVER = "hybrid"` in [config.py](backend/app/config.py)).
- **Result:** 8/12 → 11/12 correct, for about 1 millisecond more per search.

### 2.7 Metadata filter

- **Plain meaning:** "Only search inside documents with this label", e.g. only `dwelling_fire`.
- **Where:** `build_where` in [backend/app/retrieval/search.py](backend/app/retrieval/search.py). This is the "policy_line filter" box on the Search tab.
- **Why:** Stops the app from using the wrong document's version of a code.

### 2.8 MMR (tested, NOT used)

- **Plain meaning:** Re-orders results to make them more varied, so you don't get three near-identical paragraphs.
- **Where:** [backend/app/retrieval/mmr.py](backend/app/retrieval/mmr.py). **Not used by the app.** It was only an experiment.
- **Why it isn't used:** It lowered the score at every setting (11/12 → 10, 9, 8), because it pushed out the correct document to add variety.

### 2.9 Grounded answers, citations and forced refusal

- **Where:** [backend/app/generation/answer.py](backend/app/generation/answer.py).
- **Strict AI instructions (the "prompt"):**
  1. Answer **only** from the given pieces.
  2. End every sentence with a source: `[chunk_id | form | clause]`.
  3. If the answer isn't there, reply `INSUFFICIENT_CONTEXT: …`.
  4. No guessing, no general knowledge. Partially answerable counts as not answerable.
- **Source checking:** After the AI answers, the app looks up every source ID in the database. If one doesn't exist, it's flagged, because that means the AI invented it.
- **Why:** In insurance, an invented "yes, you're covered" leads to wrong payouts and legal risk.

### 2.10 Measuring search quality

| Measurement | Where | What it checks | Week |
|---|---|---|---|
| **hit-in-top-5** | [backend/app/retrieval/evaluate.py](backend/app/retrieval/evaluate.py) | Out of 8 questions, is the right document section in the top 5 results? | 3 |
| **hit-rate@3** | [backend/app/retrieval/hitrate.py](backend/app/retrieval/hitrate.py) | Out of 12 questions, is the **exact correct piece** in the top 3? (stricter) | 4 |
| **p50 latency** | [backend/app/retrieval/hitrate.py](backend/app/retrieval/hitrate.py) | The typical (middle) time one search takes, in milliseconds | 4 |

- **Test questions:**
  - [evals/questions.json](evals/questions.json) and [evals/expected.json](evals/expected.json): Week 3's 8 questions and their answers.
  - [evals/golden_set.jsonl](evals/golden_set.jsonl): Week 4's 12 questions, each with its correct piece ID. Called the **golden set**.
- **Saved results:** [evals/search-dumps/](evals/search-dumps/) (Week 3) and [evals/w4-runs/](evals/w4-runs/) (Week 4).

### 2.11 Inspection view (R / G / Not-In-Corpus)

- **Plain meaning:** For each failed question, decide **whose fault** it was.
- **Where:** [backend/app/retrieval/inspect.py](backend/app/retrieval/inspect.py), shown on the **Inspect** tab ([frontend/src/components/InspectionView.jsx](frontend/src/components/InspectionView.jsx)).

| Label | Meaning | What fixes it |
|---|---|---|
| **R** | The search didn't find the right piece, so the AI never saw it | A better search |
| **G** | The search found it, but the AI still answered wrong | A better AI or better instructions |
| **Not-In-Corpus** | The answer isn't in any document | Add the document, or refuse |

- **Result:** R = 4, G = 0. The problem was the search, not the AI.

### 2.12 Traces (recording every answer), Week 5

- **Plain meaning:** Like a flight recorder. Every question and answer is saved with everything needed to repeat it later.
- **Where:** [backend/app/tracing/trace.py](backend/app/tracing/trace.py) writes to `traces/traces.jsonl` (one record per line).
- **What's saved:** the question, which pieces were found (with scores), the exact instructions sent to the AI, the model name and settings, the raw answer, and the time.

| Supporting tool | Where | Purpose |
|---|---|---|
| **Redaction** | [backend/app/tracing/redact.py](backend/app/tracing/redact.py) | Hides private data (claim numbers, policy numbers, names, emails, phones, addresses) **before** the record is saved. Document codes like HO-0304 are kept, because they aren't private. |
| **Replay** | [backend/app/tracing/replay.py](backend/app/tracing/replay.py) | Re-sends a saved record to the AI to check it can be reproduced from the record alone. |
| **Random sample** | [backend/app/tracing/sample.py](backend/app/tracing/sample.py) | Picks 20 records at random using a fixed number (a "seed", `20260907`), so anyone can pick the exact same 20 again. |
| **Open coding** | [backend/app/tracing/opencode.py](backend/app/tracing/opencode.py) | Helps write one plain sentence about each of the 20 records. It rejects "diagnosis" words like "hallucination", and checks no code was changed while reading. |
| **Taxonomy** | [backend/app/tracing/taxonomy.py](backend/app/tracing/taxonomy.py) | Groups the sentences into 4–7 named problem types, ranked by how harmful each is. |
| **Traffic** | [backend/app/tracing/traffic.py](backend/app/tracing/traffic.py), questions in [evals/traffic/](evals/traffic/) | Sends a batch of realistic questions through the app to create records. |
| **Notes** | [backend/app/tracing/notes.py](backend/app/tracing/notes.py) | Builds the Week 5 write-up from the saved files. |
| **Runbook** | [week5/RUNBOOK.md](week5/RUNBOOK.md) | The step-by-step order to do Week 5 in. |

### 2.13 Evals: checking an AI "grader", Week 6

- **Plain meaning:** The app writes claim summaries, and an AI "judge" grades them. Before trusting the judge, you check it agrees with a human.

| Part | Where | Purpose |
|---|---|---|
| **Summary writer** | [backend/app/generation/summarize.py](backend/app/generation/summarize.py) | Turns adjuster notes into a claim summary (the thing being graded). |
| **Code checks (assertions)** | [backend/app/evals/assertions.py](backend/app/evals/assertions.py) | 4 simple checks done with plain code, not AI: (1) claim number in the right format, (2) date of loss is a real date, (3) deductible is a number, (4) if the claim is denied, an exclusion code is named. Code is free and never gets these wrong. |
| **AI judge** | [backend/app/evals/judge.py](backend/app/evals/judge.py), instructions in [evals/w6/judges/](evals/w6/judges/) | Grades **one** thing only, with PASS or FAIL: "Is the coverage decision based on the correct policy document?" |
| **Human labelling** | [backend/app/evals/label.py](backend/app/evals/label.py) | You grade 25 summaries yourself **before** seeing the judge's grades, so you aren't influenced by them. |
| **Agreement** | [backend/app/evals/agreement.py](backend/app/evals/agreement.py) | The percentage of cases where the judge and the human agreed, plus **Cohen's kappa** (agreement after removing lucky guesses). |
| **Test cases** | [backend/app/evals/cases.py](backend/app/evals/cases.py) | The 25+ test cases, each tagged with a Week-5 problem type. |
| **One command** | [backend/app/evals/run.py](backend/app/evals/run.py) | Runs everything and shows the pass rate **per problem type**. |
| **Proof of order** | [backend/app/evals/store.py](backend/app/evals/store.py) | Fingerprints files so it can prove the human labels were done before the judge ran. |

### 2.14 Agent vs workflow, Week 7

- **Plain meaning:** Two designs for the same job (checking a claim and computing the payout):
  - **Agent:** the AI decides each next step itself, in a loop.
  - **Workflow:** fixed steps written in code, the same every time.

| Part | Where | Purpose |
|---|---|---|
| **Agent** | [backend/app/agents/agent.py](backend/app/agents/agent.py) | Loop: the AI picks a tool, the app runs it, the result goes back to the AI, and so on until it's done. |
| **Workflow** | [backend/app/agents/workflow.py](backend/app/agents/workflow.py) | 6 fixed steps: get claim → read notes → search the policy once → one AI decision → compute payout → final result. |
| **Tools** | [backend/app/agents/tools.py](backend/app/agents/tools.py), described in [week7/tools_v2.json](week7/tools_v2.json) | 3 tools. `get_claim` gets the claim file. `search_policy` searches the documents. `compute_payout` does the payout arithmetic. Each has exactly one job. |
| **Budgets (safety limits)** | [backend/app/agents/budget.py](backend/app/agents/budget.py) | 4 limits so the agent can't run forever: max 8 steps, max 60,000 tokens, max $0.25, max 90 seconds. If one is reached, it stops cleanly and returns "UNDETERMINED". |
| **Output format** | [backend/app/agents/contract.py](backend/app/agents/contract.py) | The exact answer format both designs must return, plus the grading rules. |
| **AI call** | [backend/app/agents/llm.py](backend/app/agents/llm.py) | One shared function both designs use to call the AI, so the comparison is fair. |
| **Race** | [backend/app/agents/race.py](backend/app/agents/race.py) | Runs both designs on the same 10 claims and records accuracy, speed, tokens and cost. |
| **Log** | [backend/app/agents/runlog.py](backend/app/agents/runlog.py) | Writes a line for every step, used to show a budget stop. |
| **Test claims** | [evals/w7/claims.jsonl](evals/w7/claims.jsonl) | 10 made-up claims covering different situations: clean, flood, missing notes, and so on. |
| **Tool description change** | [week7/tool_descriptions.diff](week7/tool_descriptions.diff) | Shows how vague, overlapping tool descriptions were rewritten so each tool has one clear job. |

### 2.15 AI provider layer (Groq)

- **Where:** [backend/app/llm.py](backend/app/llm.py).
- **Purpose:** The **one** place the app talks to the AI company. All AI calls go through it: answers, summaries, judge, replay, agent and workflow.
- **What it handles:**
  - **Switching provider:** `LLM_PROVIDER=groq` or `anthropic` in `.env`.
  - **Rate limits:** Groq's free tier allows about 8,000 tokens per minute. When the limit is hit, it waits and retries instead of crashing.
  - **Character clean-up:** This model writes `【 】` instead of `[ ]`, and a special dash in `E‑17`. These are converted back to normal characters so source checking and code checks work.
  - **Tool format translation:** The agent was written in Anthropic's message format. This file translates it to Groq's format and back, so the agent code didn't need to change.

### 2.16 Configuration

- **Where:** [backend/app/config.py](backend/app/config.py) holds all settings. [.env](.env) holds your private values (never uploaded to git). [.env.example](.env.example) is the template.
- **Why one file:** Every setting an experiment could change is in one place, so it's easy to see and change **one thing at a time**.

---

## 3. Folder and file map

```
ai-ml-hub/
│
├── DEMO.md                    demo script (plain language)
├── TECH.md                    this file
├── README.md                  setup + run commands
├── results.md                 Week 4 write-up with all numbers
├── .env                       YOUR API key + settings (private, not in git)
├── .env.example               template for .env
│
├── data/endorsements/         the 6 insurance documents the app answers from
│
├── backend/
│   ├── requirements.txt       list of Python libraries
│   ├── .chroma/               the saved search database (auto-created)
│   ├── app/
│   │   ├── main.py            starts the backend
│   │   ├── config.py          ALL settings
│   │   ├── llm.py             talks to the AI (Groq)
│   │   ├── api/routes.py      the web addresses the page calls
│   │   ├── models/            request formats
│   │   ├── ingestion/         reading + labelling documents          (Week 3)
│   │   ├── chunking/          cutting documents into pieces          (Week 3)
│   │   ├── retrieval/         search, hybrid, filter, measuring      (Weeks 3–4)
│   │   ├── generation/        writing answers + summaries            (Weeks 3, 6)
│   │   ├── tracing/           recording + reviewing answers          (Week 5)
│   │   ├── evals/             code checks + AI judge                 (Week 6)
│   │   └── agents/            agent, workflow, tools, budgets        (Week 7)
│   └── tests/                 94 automatic tests
│
├── frontend/
│   └── src/
│       ├── App.jsx            the tabs and buttons
│       ├── api/client.js      sends requests to the backend
│       └── components/        each screen part:
│           ├── ResultList.jsx       search results       (Search tab)
│           ├── AnswerPanel.jsx      AI answer + sources  (Ask tab)
│           ├── InspectionView.jsx   R/G labels           (Inspect tab)
│           ├── HitRateTable.jsx     before/after score   (hit-rate@3 tab)
│           └── EvalTable.jsx        8/8 vs 8/8           (Bench tab)
│
├── evals/                     test questions + saved results
│   ├── questions.json, expected.json   Week 3 questions
│   ├── golden_set.jsonl                Week 4 12 questions
│   ├── search-dumps/, w4-runs/         saved results
│   ├── traffic/                        Week 5 question batches
│   ├── w6/judges/                      Week 6 judge instructions
│   └── w7/claims.jsonl                 Week 7 10 claims
│
├── traces/                    Week 5 recorded answers
├── week5/  week7/             week write-ups and helper files
└── Requirements/              the course task files + COMPLETE-GUIDE.md
```

### Which file powers each tab of the web page

| Tab | Screen file | Backend address | Backend file |
|---|---|---|---|
| **Search** | `ResultList.jsx` | `/api/search` | `retrieval/search.py` |
| **Ask** | `AnswerPanel.jsx` | `/api/ask` | `generation/answer.py` → `llm.py` |
| **Inspect** | `InspectionView.jsx` | `/api/inspect` | `retrieval/inspect.py` |
| **hit-rate@3** | `HitRateTable.jsx` | `/api/hitrate` | `retrieval/hitrate.py` |
| **Bench (wk3)** | `EvalTable.jsx` | `/api/evaluate` | `retrieval/evaluate.py` |

---

## 4. One question, start to finish

What happens when you type *"Does E-17 apply under HO-0304?"* in the **Ask** tab:

| # | What happens | File | Tech used |
|---|---|---|---|
| 1 | The page sends the question to the backend | `frontend/src/api/client.js` | React, fetch |
| 2 | The backend receives it at `/api/ask` | `backend/app/api/routes.py` | FastAPI |
| 3 | **Meaning search** finds pieces similar in meaning | `retrieval/search.py`, `store.py` | ChromaDB + MiniLM |
| 4 | **Keyword search** finds pieces containing "E-17" and "HO-0304" | `retrieval/lexical.py` | BM25 |
| 5 | The two lists are **merged by position** and the top 5 kept | `retrieval/hybrid.py` | RRF |
| 6 | The pieces are placed into the strict AI instructions | `generation/answer.py` | Prompt |
| 7 | The instructions are sent to the AI | `llm.py` | Groq, gpt-oss-120b |
| 8 | Odd characters are cleaned (`【】` → `[]`) | `llm.py` | — |
| 9 | Every source in the answer is **checked** in the database | `generation/answer.py` | ChromaDB lookup |
| 10 | Private data is hidden and a **record** is saved | `tracing/redact.py`, `trace.py` | Regex, JSONL |
| 11 | The answer and sources are sent back and shown | `AnswerPanel.jsx` | React |

---

## 5. Settings you can change

Put these in the `.env` file. You only **need** `LLM_API_KEY`; everything else has a default.

| Setting | Default | What it controls |
|---|---|---|
| `LLM_PROVIDER` | `groq` | Which AI company to use (`groq` or `anthropic`) |
| `LLM_API_KEY` | — | Your secret key for that company |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Which AI model writes answers |
| `LLM_REASONING_EFFORT` | `low` | How much the model "thinks" before answering (more = slower) |
| `JUDGE_MODEL` | same as above | Which model grades summaries (Week 6) |
| `AGENT_MODEL` | same as `LLM_MODEL` | Which model the agent and workflow use (Week 7) |
| `GROQ_PRICE_IN` / `GROQ_PRICE_OUT` | `0.15` / `0.60` | Price per million tokens, used for cost figures. **Check https://groq.com/pricing** |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | The model that turns text into numbers for meaning search |
| `AGENT_MAX_ITERS` | `8` | Agent safety limit: max steps |
| `AGENT_MAX_TOKENS` | `60000` | Agent safety limit: max tokens |
| `AGENT_MAX_COST_USD` | `0.25` | Agent safety limit: max cost |
| `AGENT_WALL_CLOCK_S` | `90` | Agent safety limit: max seconds |

These are fixed in [config.py](backend/app/config.py) and not in `.env`:

| Setting | Value | What it controls |
|---|---|---|
| `TOP_K` | 5 | How many pieces are given to the AI |
| `EVAL_K` | 3 | "Top 3" for the Week 4 score |
| `CANDIDATE_K` | 25 | How many results each search contributes before merging |
| `RRF_K` | 60 | The constant in the merging formula |
| `SHIPPED_RETRIEVER` | `hybrid` | Which search the app uses |
| `SAMPLE_SEED` | 20260907 | The fixed number for the Week 5 random pick |

---

## 6. Quick glossary

| Term | Plain meaning |
|---|---|
| **API** | A web address one program calls to ask another program to do something |
| **Backend / Frontend** | The "brain" running on the computer / the web page you see |
| **Embedding** | A list of numbers representing the meaning of text |
| **Vector database** | A database that finds text by meaning, using those numbers |
| **Chunk** | A small piece of a document |
| **Retrieval** | Searching for the right pieces |
| **Dense / Hybrid** | Meaning search only / meaning search + keyword search together |
| **BM25** | A keyword-search method |
| **RRF** | A way to merge two result lists by position |
| **Prompt** | The instructions sent to the AI |
| **Token** | A small piece of a word. AI usage and cost are counted in tokens |
| **LLM** | Large Language Model, the AI that writes text |
| **Trace** | A saved record of one question and answer |
| **Redaction** | Hiding private information |
| **Eval** | A test that measures quality |
| **Assertion** | A simple check done with code (not AI) |
| **Judge** | An AI used to grade another AI's output |
| **Agent** | An AI that chooses its own next steps in a loop |
| **Workflow** | Fixed steps written in code |
| **p50 latency** | The typical (middle) time something takes |
| **Rate limit** | A cap on how much you can use per minute |
