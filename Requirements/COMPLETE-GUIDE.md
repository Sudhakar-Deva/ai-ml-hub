# ai-ml-hub — Complete Guide, Weeks 3 → 7

**Domain:** insurance claims (Task Set D). **App:** a claims assistant that answers from 6 homeowners-policy endorsements, cites where each answer came from, and refuses when it can't.

This document covers every requirements file in [Requirements/](.), and for each week answers:

- **What:** the concept and what the task asked for
- **Why:** the problem it solves and why the requirement is written that way
- **When:** when to use the technique, and when not to
- **What I used:** the concrete choice in this repo, with the file it lives in
- **What else exists:** the alternatives, and why they weren't picked
- **Resources:** papers, docs and articles to study

> Source files: [week3.md](week3.md), [W4-Task-Set-D.md](W4-Task-Set-D.md), [W5-Task-Set-D.md](W5-Task-Set-D.md), [W6-Task-Set-D.md](W6-Task-Set-D.md), [W7-Task-Set-D.md](W7-Task-Set-D.md), [Retrieval_and_RAG.pdf](Retrieval_and_RAG.pdf).

---

## Table of contents

0. [The big picture: how the five weeks connect](#0-the-big-picture)
1. [Tech stack: every tool, why it was chosen, and the alternatives](#1-tech-stack)
2. [Week 3: RAG from parts (chunking, embeddings, vector DB, citations, refusal)](#2-week-3--rag-from-parts)
3. [Week 4: Debugging retrieval (golden set, R/G labels, BM25 + RRF, MMR)](#3-week-4--debugging-retrieval)
4. [Week 5: Error analysis (traces, replay, redaction, seeded sampling, open coding, taxonomy)](#4-week-5--error-analysis)
5. [Week 6: Evals (assertions vs LLM judge, blind labels, agreement, kappa)](#5-week-6--evals)
6. [Week 7: Agents vs workflows (tool design, budgets, the race, the decision rule)](#6-week-7--agents-vs-workflows)
7. [Principles that run through every week](#7-cross-cutting-principles)
8. [Current status of each week's deliverables](#8-status)
9. [Glossary](#9-glossary)
10. [Master resource list](#10-master-resource-list)

---

## 0. The big picture

Each week builds on the previous one. None of them start from scratch.

```
Week 3  BUILD      Load docs → chunk → embed → store → retrieve → answer with citations / refuse
          │        "Does my chunking find the answer?"   metric: hit-in-top-5 (X/8)
          ▼
Week 4  DEBUG      When an answer is wrong: was it retrieval (R) or the model (G)?
          │        Fix with ONE retrieval change.         metric: hit-rate@3 + p50 latency
          ▼
Week 5  OBSERVE    Log every answer as a replayable trace, sample 20 at random,
          │        read them by hand, name the failure modes.   output: ranked taxonomy
          ▼
Week 6  MEASURE    Turn the taxonomy into an eval set. Split checks into regex
          │        assertions vs one LLM judge, and validate the judge against human labels.
          │                                                metric: judge–human agreement %
          ▼
Week 7  DECIDE     Is an agent loop needed, or would a fixed workflow do?
                   Race both.                             metric: pass rate, p50, tokens, cost
```

Every week's rubric ends with the same line: **"Zero points for polish, UI, or 'it works'… failure-finding and a number that moved are what score."** That one rule explains most design decisions in this repo:

- **Measure before you change anything.** The baseline number has to exist before the fix.
- **Change one variable per run.** With two changes, you can't tell which one moved the number.
- **Look at the data itself** (retrieved chunks, traces, labels), not at how the output feels.
- **Write the number down honestly**, including when it says "not worth it".

---

## 1. Tech stack

Pinned in [backend/requirements.txt](../backend/requirements.txt) and [frontend/package.json](../frontend/package.json). All settings live in [backend/app/config.py](../backend/app/config.py).

| Layer | Used | Why this one | Alternatives, and why not |
|---|---|---|---|
| Language | **Python 3.12** | The ML ecosystem (torch, chromadb, sentence-transformers) ships wheels for it. 3.14 has no torch/chromadb wheels yet. | 3.13/3.14: missing wheels. Node/TS: weaker local-embedding ecosystem. |
| Vector DB | **ChromaDB 0.5.23** (`PersistentClient`, HNSW, cosine) | Embedded (no server to run), persists to `backend/.chroma`, supports metadata `where` filters, and gives one collection per chunking strategy so both can be compared side by side. Right size for 55 chunks. | **Qdrant**: strong filtering, production server, but needs a running service. **pgvector**: good if you already run Postgres, since SQL joins with claim data are a big plus in production. **FAISS**: a library, not a DB, with no metadata filtering built in. **Pinecone/Weaviate**: managed/cloud, overkill and adds network latency to the measurements. |
| Embeddings | **sentence-transformers `all-MiniLM-L6-v2`** (384-dim) | Runs locally with no API key, is fast (~7 ms p50 retrieval) and free. A small model also makes the Week 4 lesson visible: dense embeddings lose exact tokens like `E-17`. | **all-mpnet-base-v2** (768-d, better, slower; listed in `.env.example` as the swap). **BGE** (`bge-small/base-en-v1.5`), **E5** (`e5-base-v2`), **GTE**, **nomic-embed**: rank higher on MTEB. **OpenAI / Voyage / Cohere embeddings**: hosted, cost money, add network latency. Rule: swapping the model is its own run, never in the same run as a chunker change. |
| Lexical search | **rank-bm25 0.2.2** (`BM25Okapi`) | Pure Python, in-memory, builds in 4.5 ms over 55 chunks, and scores the literal token `e-17`. | **Elasticsearch / OpenSearch / Tantivy / SQLite FTS5**: real inverted indexes, needed at 500k chunks, overkill at 55. **SPLADE**: learned sparse retrieval, stronger but needs a model. |
| LLM | **Anthropic SDK 0.40**, default model **`claude-sonnet-5`** | Good at following strict grounding and refusal rules, and supports tool use for Week 7. Temperature 0 for Q&A and judging, for reproducibility. | `claude-opus-5` (deeper reasoning, more expensive), `claude-haiku-4-5` (cheaper and faster, a candidate for the judge or the workflow step). OpenAI/Gemini work too, but the model stays fixed across comparisons. |
| PDF reading | **pypdf 5.1** | Pure Python and good enough for text-layer PDFs. The loader reads `.pdf/.txt/.md`. | **pdfplumber** (better tables), **PyMuPDF** (fast), **unstructured / docling / LlamaParse** (layout-aware, better on complex tables). |
| API | **FastAPI 0.115 + uvicorn** | Typed request models with Pydantic, auto-generated docs at `/docs`, async-ready, minimal boilerplate. | Flask (no typing or validation built in), Django (too heavy). |
| Config | **python-dotenv**, all settings in `config.py` | One file to diff, and every setting an experiment can change is visible there. | pydantic-settings, Hydra (useful with many experiment configs). |
| Frontend | **React 18 + Vite 6**, yarn | Fast dev server. The Inspect tab is the Week 4 "inspection view". | Streamlit/Gradio (quicker for demos, but can't be extended into a real app). |
| Tests | **pytest** | Tests guard *invariants* (an exclusion row never separated from its header, RRF fuses ranks, a claim number never reaches the trace file, the same seed gives the same sample, all 4 budgets fire). | — |
| Orchestration | **None (hand-built)** | Every step is visible and measurable: token counts per lap, budget checks, trace fields. Frameworks hide exactly what these weeks grade. | **LangChain / LlamaIndex / LangGraph / Haystack / DSPy**: faster to prototype, but they hide prompts, retries and token usage. |

---

## 2. Week 3 — RAG from parts

**Brief:** [week3.md](week3.md) · **Course notes:** [Retrieval_and_RAG.pdf](Retrieval_and_RAG.pdf) · Module M2, Retrieval & RAG

### 2.1 The problem

Underwriting issued 6 new endorsements (HO-0304 ed. 03-24, etc.), each with an exclusions table and an effective date. Does your chunker keep exclusion **E-17** attached to the endorsement that scopes it? Ingest them, compare two chunking strategies, add a metadata filter, cite every claim, and refuse what the corpus can't source.

### 2.2 Requirements, in plain words

| # | Requirement | What it's really testing |
|---|---|---|
| 1 | Ingest the 6 endorsements with `source_file, form_number, policy_line, edition_date` on every chunk | Metadata is what makes citations and filters possible |
| 2 | 8 known-answer questions, ≥3 depending on a row inside an exclusions table | A fixed test set written *before* looking at results |
| 3 | Same 8 questions against two chunkers, report hit-in-top-5 as X/8 each | Comparing with a number, not by eyeballing |
| 4 | A `policy_line` filter that changes the top-1 result, with both lists pasted | Metadata filtering is a retrieval tool, not decoration |
| 5 | 3 cited answers + 3 refused out-of-corpus questions | Grounding and forced refusal |
| 6 | Index only the 6 new docs | Time management: the measurement is the deliverable |

### 2.3 Concepts

#### Why RAG
- **What:** Retrieval-Augmented Generation. Fetch relevant passages from your documents, put them in the prompt, and have the model answer only from them.
- **Why:** The model was trained on public data and knows nothing about HO-0304 ed. 03-24. Ask anyway and it invents a plausible-sounding answer. In insurance, an invented coverage answer is a **bad-faith exposure**.
- **When:** The answer must come from specific, private, or frequently changing documents (policies, handbooks, support docs).
- **When not:** The knowledge is stable and general (the base model already knows it), or the task is a style or behaviour change (fine-tuning suits that better).
- **Alternatives:** **Fine-tuning** (bakes knowledge into weights: expensive, can't cite, goes stale). **Long-context stuffing** (put all 6 docs in the prompt: feasible at this size, but it doesn't scale, costs more per query, and suffers from "lost in the middle"). **Tool calling / SQL** (for structured data).

#### Embeddings and dense retrieval
- **What:** An embedding model maps text to a vector. Similar meaning gives nearby vectors. Dense retrieval embeds the question and returns the chunks with the highest cosine similarity.
- **Why:** It matches *meaning*, not just keywords. "Pipe burst under the sink" finds "sudden discharge from a plumbing system".
- **Weakness (the setup for Week 4):** It blurs exact identifiers. `E-17` and `E-19` land about 0.02 apart, because the model encodes "an exclusion code about water" and drops the digits.

#### Bi-encoder vs cross-encoder
| | Bi-encoder | Cross-encoder |
|---|---|---|
| How | Embeds query and doc **separately**, then compares vectors | Reads **query + doc together**, outputs one relevance score |
| Speed | Fast: docs are pre-embedded once | Slow: one model pass per (query, doc) pair |
| Quality | Good | Better, since it sees the interactions between words |
| Use as | First-stage retriever (search millions) | Reranker over the top 25–100 |
| In this repo | `all-MiniLM-L6-v2` | Considered in Week 4 and rejected (see §3.4) |

#### Embedding model choice (MTEB, BGE, E5)
- **MTEB** (Massive Text Embedding Benchmark) is the public leaderboard for comparing embedding models across retrieval, clustering, and other tasks.
- **BGE** (BAAI) and **E5** (Microsoft) are strong open families. E5 needs `query:` / `passage:` prefixes, and BGE recommends a query instruction.
- **Why MiniLM here:** It's small, fast, local, and free. A leaderboard rank doesn't predict performance on *your* corpus. That's the point of building your own golden set.

#### Chunking strategies
- **What:** Splitting documents into retrievable units.
- **Why it matters:** The chunk is both the unit of retrieval *and* the unit the model reads. If a table row is split away from its header, the retrieved text says "E-17 … Excluded" with no form number, so the model can't know which policy it's about.

| Strategy | Used? | Notes |
|---|---|---|
| **Fixed-size window + overlap** | `current` (control): 1000 chars, 150 overlap, [current_chunker.py](../backend/app/chunking/current_chunker.py) | Simple, structure-blind. It is the *control* and is deliberately not improved. |
| **Structure-aware** (split on form/clause headers, keep exclusion row + table header + form number together, soft-split at 1800 chars) | `structure_aware`, [structure_aware_chunker.py](../backend/app/chunking/structure_aware_chunker.py) | Every chunk is stamped `[form_number ed. edition \| policy_line \| source_file]`, so its scope survives retrieval |
| Recursive character splitter (LangChain-style) | no | A middle ground: splits on paragraphs, then sentences |
| Semantic chunking (split where embedding similarity drops) | no | Costs embeddings to chunk, and is unpredictable on tables |
| Parent–child / small-to-big | no | Retrieve the small row, send the parent section. Directly addresses the Week 3 bonus (see below) |
| Late chunking / contextual retrieval (prepend an LLM-written context sentence to each chunk) | no | Anthropic's "contextual retrieval". Costs one LLM call per chunk at ingest |

- **Chunk size and overlap:** Small chunks give precise retrieval but strand the model without context. Large chunks give complete context but dilute the embedding and cost more tokens. Overlap reduces boundary cuts but duplicates text.
- **Shared helpers ([common.py](../backend/app/chunking/common.py))** make sure the *only* difference between the two chunkers is the splitting policy, never the metadata. That's what makes the comparison fair.

#### Vector databases and HNSW
- **What:** A store that indexes vectors for fast approximate nearest-neighbour (ANN) search.
- **HNSW** (Hierarchical Navigable Small World): a layered graph. Search starts at the sparse top layer and descends. Queries are O(log n)-ish with high recall, at the cost of memory. Chroma uses HNSW, configured with `hnsw:space = cosine` in [store.py](../backend/app/retrieval/store.py).
- **Other index types:** IVF (cluster then search nearby clusters), PQ (compressed vectors), flat/brute-force (exact, fine at 55 chunks).

#### Similarity search and top-K
- Cosine similarity, top-K = 5 in Week 3 (`TOP_K = 5`, held fixed across both strategies).
- **Why K is fixed:** Changing K changes the metric, so the two strategies must use the same K.

#### Metadata filtering
- **What:** Restrict the search to chunks whose metadata matches (`where={"policy_line": "homeowners"}`), in [search.py](../backend/app/retrieval/search.py) `build_where`.
- **Why:** E-17 exists in *both* HO-0304 (homeowners: burst supply line **not** excluded) and DP-0110 (dwelling fire: **excluded**). Without a filter, the wrong form's E-17 row can win. With it, the top-1 changes. Requirement 4 asks you to show exactly that.
- **Pre- vs post-filtering:** Chroma filters during the search. Filtering *after* top-K can leave you with zero results.

#### Grounded generation, citations and forced refusal
- In [answer.py](../backend/app/generation/answer.py):
  - Every claim must end with `[chunk_id | form_number | clause]`, copied verbatim from the chunk header.
  - Not in context → output exactly `INSUFFICIENT_CONTEXT: <what is missing>`.
  - No general knowledge, no "best judgement", no inference from similar clauses. **Partially answerable counts as unanswerable.**
  - Citations are **resolved against the store** afterwards (`get_chunk`). Unresolvable ones are surfaced, not ignored.
- **Why "forced, not suggested":** "If the context is insufficient, use your best judgement" invites invention, which the brief calls out as a common mistake.
- **Refusal tests:** 3 out-of-corpus questions, e.g. the reserve-setting threshold for claim CLM-2024-88431, which lives in an adjuster system that was never indexed.
- **Alternatives:** Structured output (JSON with a `citations` array), Anthropic's Citations API feature, a post-hoc NLI/groundedness check, or constrained decoding.

#### Chunk metadata and ingestion
- [loader.py](../backend/app/ingestion/loader.py) parses the form number (`HO-\d{4}` etc.), the edition (`ed. MM-YY`), the policy line, and the effective date from the header, falling back to the filename.
- [ingest.py](../backend/app/ingestion/ingest.py) **refuses** to index a chunk with an `UNKNOWN` field. A chunk without a `source_file` can never be cited.
- `chunk_id = "{strategy}:{form}:{file}:{idx:04d}"` is stable and resolvable, so citations can be checked.

### 2.4 Results

| Strategy | hit-in-top-5 |
|---|---|
| `current` | **8/8** |
| `structure_aware` | **8/8** |

Source: [evals/search-dumps/hit_table_20260826T070022Z.md](../evals/search-dumps/hit_table_20260826T070022Z.md).

**What this tie tells you:** Top-5 is a lenient metric, and the questions contain enough prose to match. The rank positions still differ (for example Q2: current #3, structure-aware #4). **structure_aware was kept** because its chunks carry the form/edition stamp, so a single retrieved row can still be scoped and cited. It became Week 4's baseline chunker. The tie also motivated Week 4's stricter metric (the gold `chunk_id` in the top-3).

### 2.5 Bonus: the precision vs completeness tension
A tight exclusion-row chunk retrieves precisely, but leaves the model without the *definitions* clause ("sudden and accidental", in HO-0417). Fixes that exist: parent–child retrieval, attaching the referenced definition as linked metadata, or K>1 with MMR-style diversity across clause types.

### 2.6 Common mistakes and how this repo avoids them
| Mistake | Guard |
|---|---|
| Writing questions after seeing retrieval results | `questions.json` `_instructions`: "Write these from the ENDORSEMENTS FIRST" |
| Changing the chunker *and* the embedding model together | `config.py` header and `.env.example`: one variable per run |
| "Looks better" | A hit is metadata-verified (form_number + clause marker), [evaluate.py](../backend/app/retrieval/evaluate.py) |
| "Use your best judgement" in the prompt | The prompt forbids it, and the refusal sentinel is required |
| Re-indexing the whole library | Only `data/endorsements/` is indexed |

### 2.7 Resources: Week 3
- Lewis et al., 2020, *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*: https://arxiv.org/abs/2005.11401
- Sentence-Transformers docs (bi-encoders, cross-encoders): https://www.sbert.net
- all-MiniLM-L6-v2 model card: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- MTEB leaderboard: https://huggingface.co/spaces/mteb/leaderboard · paper: https://arxiv.org/abs/2210.07316
- BGE: https://huggingface.co/BAAI/bge-base-en-v1.5 · E5: https://huggingface.co/intfloat/e5-base-v2
- HNSW paper, Malkov & Yashunin: https://arxiv.org/abs/1603.09320
- Chroma docs: https://docs.trychroma.com · Qdrant: https://qdrant.tech/documentation/ · pgvector: https://github.com/pgvector/pgvector · FAISS: https://github.com/facebookresearch/faiss
- Anthropic, *Contextual Retrieval*: https://www.anthropic.com/news/contextual-retrieval
- Liu et al., *Lost in the Middle*: https://arxiv.org/abs/2307.03172
- Pinecone Learn, chunking strategies: https://www.pinecone.io/learn/chunking-strategies/

---

## 3. Week 4 — Debugging retrieval

**Brief:** [W4-Task-Set-D.md](W4-Task-Set-D.md) · **Write-up:** [results.md](../results.md) · Module M2

### 3.1 The problem

"Is water damage covered?" works. "Does exclusion E-17 apply under form HO-0304 ed. 03-24?" returns three fluent water-damage clauses, **none of them E-17**. The team lead wants to swap the model. You have to prove where the failures actually are, make **one** retrieval change, and report before and after numbers.

### 3.2 Requirements, in plain words
1. A 12-question golden set of *real* adjuster questions, each tagged with the correct `chunk_id`. At least 4 contain an exact token (exclusion code, form number, endorsement number).
2. Baseline hit-rate@3, **written down before any change**.
3. Label every miss **R / G / Not-In-Corpus** with one line of evidence from the inspection view.
4. Exactly **one** change: BM25 + RRF (k=60) **or** a cross-encoder rerank over the top 25, justified by the tally.
5. Re-measure on the same 12: hit-rate@3 **and** p50 latency, before and after.
6. Name which R-failures were fixed and which weren't.

### 3.3 Concepts

#### Golden set
- **What:** A fixed set of questions with known-correct answers (here, the gold `chunk_id`). It's your ruler.
- **Why real questions:** A golden set made only of questions you already pass measures nothing.
- **In the repo:** [evals/golden_set.jsonl](../evals/golden_set.jsonl). 6 exact-token questions (the requirement was ≥4) and 6 prose questions. G01 and G07 ask the *same* thing in code form and in prose form. Prose found the chunk and the code didn't, which proves the failure is about the **token**, not the topic.

#### hit-rate@k and strict scoring
- **What:** The fraction of questions where the gold chunk is in the top-k.
- **Why strict (gold `chunk_id` only):** A looser rule (right form, any clause) lets "three water-damage clauses, none of them E-17" count as a pass.
- **Related metrics:** Recall@k, **MRR** (mean reciprocal rank, which rewards rank 1 over rank 3), **nDCG** (graded relevance), Precision@k.

#### p50 latency
- **What:** The median per-query retrieval time. In [hitrate.py](../backend/app/retrieval/hitrate.py) it's measured around the retrieval call only, 9 samples per question (108 per retriever), after a warm-up.
- **Why p50 and not the mean:** Outliers (GC pauses, first-call model load) distort the mean. Report p95 too for tail latency.
- **Why the build cost is separated:** Building the BM25 index (4.5 ms) is a one-time startup cost. Folding it into the per-query p50 would make the baseline look better and the change look worse.

#### The R / G / Not-In-Corpus labels
| Label | Evidence rule | What fixes it |
|---|---|---|
| **R**: retrieval fetched bad context | Gold chunk **not** in the top-3; the model never saw it | A retrieval change |
| **G**: generation misused good context | Gold chunk **in** the top-3, answer still wrong | A prompt or model change. No retrieval change will help |
| **Not-In-Corpus** | Gold chunk doesn't exist in the store | Ingest the document, or refuse |

- **Why it matters:** The team lead's proposed model swap only fixes **G**. The tally was **R=4, G=0, NIC=0**, so a new model would have fixed **none** of them.
- **The trap (G01):** The dense top-3 *did* contain an E-17 row, but it was **DP-0110's**, where E-17 *is* excluded. The question named HO-0304, where it's **not**. Right code, wrong form: that's **R**, not G.
- **Implementation:** [inspect.py](../backend/app/retrieval/inspect.py) computes the label from the retrieved list, never from whether the answer "felt" wrong. `gold_in_corpus` checks NIC.

#### BM25 (lexical retrieval)
- **What:** A classic term-frequency × inverse-document-frequency ranking with length normalisation (params k1≈1.2–2.0, b≈0.75).
- **Why it fits here:** `e-17` is a rare, high-IDF token, so BM25 ranks the chunk containing it highly. Dense embeddings throw the digits away.
- **Tokenizer detail ([lexical.py](../backend/app/retrieval/lexical.py)):** Hyphenated codes are kept whole (`e-17`, `ho-0304`), *and* their parts are indexed, so "HO 0304" still matches.
- **Same chunks as the dense arm:** Only the scoring differs, never which chunks exist.

#### RRF (Reciprocal Rank Fusion)
- **Formula:** `rrf(d) = Σ_arms 1 / (k + rank_arm(d))`, with **k = 60** (Cormack et al., 2009).
- **Why ranks, not scores:** Cosine similarity sits around [0.2, 0.8]. BM25 is unbounded and depends on the corpus. Adding or averaging them lets whichever arm has bigger numbers win every query. Rank is the only scale the two arms share.
- **Why k=60:** Large enough that neither arm's #1 dominates outright, small enough that the top of each list still counts.
- **Candidate depth:** 25 per arm (`CANDIDATE_K`).
- **Alternatives:** Weighted score fusion after normalisation (min-max or z-score; fragile, needs tuning), CombSUM/CombMNZ, or learned fusion.

#### Why BM25 + RRF and not a cross-encoder reranker
- A reranker **only reorders what the first stage already retrieved**. For G06, the gold chunk wasn't even in the dense top-25, so there was nothing to promote.
- The tally said "lexical recall is missing", so lexical recall is what was added. The reranker stays unused until a future tally points at *ordering* instead of *recall*.
- **When a reranker is the right choice:** The gold chunk is in the top-25 but ranked below 3, and you can afford ~50–300 ms more per query. Options: `cross-encoder/ms-marco-MiniLM-L-6-v2`, BGE-reranker, Cohere Rerank, or an LLM-as-reranker.

### 3.4 Results

| | `dense` (before) | `hybrid` (after) | Δ |
|---|---|---|---|
| **hit-rate@3** | **8/12 (66.7%)** | **11/12 (91.7%)** | +3 questions, +25 pts |
| **p50 latency** | 7.4 ms | 8.7 ms | +1.3 ms |
| p95 | 9.3 ms | 10.2 ms | +0.9 ms |
| Exact-token questions | 2/6 | 5/6 | +3 |
| Prose questions | 6/6 | 6/6 | — |

- **Fixed:** G01, G02, G05 (BM25 put the gold row in its own top 2, and RRF carried it into the top-3).
- **Not touched:** G08–G12 (already at rank 1). G07 moved from 3 to 1.
- **Still broken: G06.** A **chunking defect**, not a retrieval defect. The E-19 row's chunk also carries rows E-15 to E-18 as its "table header", which dilutes the term frequency of `e-19` (BM25 #7, fused #16). That's the next single change.
- **Decision: ship `hybrid`.** 8/12 → 11/12 for +1.3 ms, which is under 1% of the ~1–2 s LLM call. Rolling back means changing one argument.
- **Caveat stated in the write-up:** +1.3 ms applies to 55 chunks with an in-memory BM25. At 500k chunks it would need a real index and has to be re-measured, not extrapolated.

### 3.5 Bonus: MMR (Maximal Marginal Relevance)
- **What:** `mmr(d) = λ·rel(d) − (1−λ)·max sim(d, already selected)`. It trades relevance for diversity. See [mmr.py](../backend/app/retrieval/mmr.py).
- **Why considered:** The E-17 top-3 was "one fact wearing three hats": the same exclusion text across editions.

| Setting | hit@3 | p50 | Distinct forms in top-3 | Pairwise cosine |
|---|---|---|---|---|
| hybrid (shipped) | **11/12** | 8.7 ms | 1.75 | 0.657 |
| MMR λ=0.9 | 10/12 | 16.6 ms | 1.75 | 0.643 |
| MMR λ=0.7 | 9/12 | 16.7 ms | 1.83 | 0.578 |
| MMR λ=0.5 | 8/12 | 17.0 ms | 2.25 | 0.450 |

- **Verdict: don't ship.** Each step of diversity costs a correct answer, because MMR doesn't know which edition the adjuster asked about. **Better tool:** a metadata rule (one chunk per `form_number` in the top-3, or a form filter parsed from the question).

### 3.6 Common mistakes and guards
| Mistake | Guard |
|---|---|
| BM25 *and* a reranker in one run | Only the `retriever` argument differs between runs: `dense` → `hybrid` |
| Adding cosine and BM25 scores | `rrf_fuse` works on ranks, with a test in [test_hybrid.py](../backend/tests/test_hybrid.py) |
| Invented, easy golden questions | Written from endorsements and adjuster phrasing before any search |
| Labelling R without checking the top-3 | Labels are computed from the retrieved list |
| Agreeing to a model swap | The tally R=4 / G=0 is the evidence against it |

### 3.7 Resources: Week 4
- Robertson & Zaragoza, *The Probabilistic Relevance Framework: BM25 and Beyond* (2009), the standard BM25 reference
- rank_bm25: https://github.com/dorianbrown/rank_bm25
- Cormack, Clarke & Büttcher, *Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods* (SIGIR 2009): https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
- Carbonell & Goldstein, *The Use of MMR, Diversity-Based Reranking…* (SIGIR 1998)
- BEIR benchmark (shows BM25 is a strong zero-shot baseline): https://arxiv.org/abs/2104.08663
- Cross-encoder reranker model: https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2
- ColBERT (late-interaction alternative): https://arxiv.org/abs/2004.12832
- Anthropic, *Contextual Retrieval* (also covers BM25 + embeddings + reranking): https://www.anthropic.com/news/contextual-retrieval

---

## 4. Week 5 — Error analysis

**Brief:** [W5-Task-Set-D.md](W5-Task-Set-D.md) · **Runbook:** [week5/RUNBOOK.md](../week5/RUNBOOK.md) · Module M3 (the core module)

### 4.1 The problem

The trace file has grown past 1,000 lines that nobody has read. The claims manager says it "sometimes gets coverage wrong", which isn't a bug report. Draw a **random** sample, **read every trace by hand without fixing anything**, and turn what you see into a ranked list someone can act on.

### 4.2 Requirements, in plain words
1. **Replayability:** Pick one trace at random (seeded), replay it from the trace alone, and show original vs replayed output. Name any missing field. **Redact before the write, not after.**
2. **A random sample of 20**, seeded, with the seed published. Not the demo claims.
3. **Open-code** all 20: one honest *observation* sentence each. **Zero code changes** during this step (the zero is graded).
4. **Cluster** into 4–7 named modes with count, %, severity (wrongly denies/pays vs annoys the adjuster), and one example trace_id.
5. **A falsifiable, dated prediction** with numbers, committed to git before any fix.
6. **Three sentences** on why a public benchmark wouldn't surface your top-3 modes.

### 4.3 Concepts

#### Tracing
- **What:** A structured record of one request: input, retrieval, prompt, model, params, and output.
- **Why:** Without traces, "sometimes wrong" can't be investigated or reproduced.
- **Fields ([trace.py](../backend/app/tracing/trace.py)) and why each exists:**

| Field | Why it's there |
|---|---|
| `trace_id`, `ts` | A stable handle to reference and discuss |
| `prompt_version` + sha | *Which* prompt, provably (`PROMPT_VERSION = "claims-grounded-v1"`) |
| `model` + `params` | Replay has to use the same model and settings |
| retriever config (strategy, retriever, k) | Retrieval is half the system |
| `retrieved[]` with chunk_id, score, rank | Needed for R-vs-G labelling |
| `system_prompt`, `rendered_prompt` | The exact text sent to the model |
| `output` | Raw model text, unparsed |
| `redaction` | Which rules fired, and proof they ran before the write |
| git sha | Which build produced the trace |

- **Format:** JSONL (append-only, one record per line, easy to grep and stream).
- **Alternatives:** **Langfuse**, **Arize Phoenix**, **LangSmith**, **Braintrust**, **Weights & Biases Weave**, **OpenTelemetry GenAI semantic conventions**. They give you UIs, search, and cost dashboards. A hand-built JSONL file was chosen so every field is visible and replay can be proven without a vendor.

#### Replay
- **What:** Re-send the *stored* system prompt and rendered prompt to the *stored* model with the *stored* params. Never call `search()` or read today's prompt ([replay.py](../backend/app/tracing/replay.py)).
- **Why:** If you can't replay a trace, you can't tell whether a difference is a regression or just "today's prompt against last week's output". `--audit` lists what is missing and what can't be reconstructed.
- **Caveat:** LLM output isn't bit-for-bit deterministic even at temperature 0. Compare the substance, and say so.

#### PII redaction, before the write
- **What:** [redact.py](../backend/app/tracing/redact.py) replaces claim numbers `CLM-…`, policy numbers, SSNs, emails, phones, addresses, and titled or role names with placeholders.
- **Why before:** A file scrubbed after the fact has already existed unscrubbed on disk, in backups, and been readable by anyone with the machine. `write()` can't reach the file handle without going through `redact_deep`.
- **Deliberately not redacted:** `HO-0304`, `ed. 03-24`, `E-17`, `DP-0110`. These are corpus vocabulary. Redacting them would make traces unreadable and unreplayable.
- **Alternatives:** **Microsoft Presidio** (NER + regex, multilingual), spaCy NER, cloud DLP (Google DLP, AWS Comprehend PII). Regex was chosen because the identifiers have fixed formats and regex is deterministic and testable.

#### Seeded random sampling
- **What:** `selection = f(seed, sorted(trace_ids), n)` in [sample.py](../backend/app/tracing/sample.py), seed `20260907`, n=20. The population size and a population fingerprint are recorded.
- **Why random:** A curated sample gives made-up frequencies, and frequency decides half of the fix order.
- **Why sort the ids first:** File order depends on when requests happened, so an unsorted population would make the same seed draw a different sample tomorrow.
- **Why record the population:** 20 out of 60 and 20 out of 6,000 say different things about the system.
- **Alternatives:** Stratified sampling (by question type or source), which is useful once you know the strata. Pure random is right for a first look.

#### Open coding (from qualitative research / grounded theory)
- **What:** Read each trace and write **one sentence describing what you saw**. No categories, no diagnoses, no fixes.
- **Why:** If you decide categories first, you only find the modes you expected. "I don't know why this failed" is allowed and useful.
- **Enforced in [opencode.py](../backend/app/tracing/opencode.py):**
  - Diagnosis words ("hallucination", "retrieval issue") are rejected when you enter them.
  - `--start` fingerprints HEAD + the working-tree diff, and `--status` compares against it. **Zero fixes during coding** is measured, not just claimed.
- **Why no fixing:** If you fix something at trace 6, the remaining 14 traces come from a different system.

#### Axial coding / clustering into a taxonomy
- **What:** Group the sentences into **4–7 failure modes**, named so a claims manager can act on them ("applies the wrong form edition's exclusion list", not "retrieval issue").
- **Ranking ([taxonomy.py](../backend/app/tracing/taxonomy.py)):** **Severity first, then frequency.** A 10% mode that wrongly denies a claim outranks a 40% mode that annoys an adjuster.
- **Severity vocabulary:** `wrongly-denies`, `wrongly-pays`, `annoys-adjuster`, `none`.
- **Validation:** 4–7 modes, every sampled trace in exactly one mode, and the example id actually belongs to its mode.
- **Why the clustering is manual:** It's the judgement being graded. [week5.py](../backend/app/tracing/week5.py) automates traffic, replay, sampling and notes, then **stops** at the human part.

#### A falsifiable prediction
- **What:** "Filtering on edition_date drops the wrong-edition mode from 30% to under 10% of a fresh seeded 20-trace sample." It's dated and **committed to git before the fix**, with the commit hash pasted into the write-up.
- **Why:** "This should improve things a lot" can't be wrong, so it teaches you nothing. Template: [week5/prediction.md](../week5/prediction.md).

#### Why public benchmarks miss your failure modes
- Benchmarks (MMLU, HELM, MTEB…) measure general ability on public data. They've never seen HO-0304 vs DP-0110, have no idea that E-17 means opposite things in two forms, and score every error the same, so they carry none of your severity ordering. Template: [week5/benchmark_note.md](../week5/benchmark_note.md).

#### Bonus: random sample vs demo set
Compare how often the top mode appears in the random 20 vs the 10 curated demo questions ([evals/traffic/questions_demo.txt](../evals/traffic/questions_demo.txt)). The gap shows what the team has been telling itself based on the demos.

### 4.4 Common mistakes and guards
| Mistake | Guard |
|---|---|
| Categories decided first | Diagnosis words are rejected during coding |
| Sampling the traces you know are broken | Seeded sample, `--source traffic` excludes the demo set |
| Fixing at trace 6 | Working-tree fingerprint, zero-fix check |
| Mode names like "hallucination" or "retrieval issue" | Rejected by the taxonomy validator |
| An unfalsifiable prediction | Template requires numbers, a date, a falsifier, and a commit hash |

### 4.5 Resources: Week 5
- Hamel Husain, *Your AI Product Needs Evals*: https://hamel.dev/blog/posts/evals/
- Hamel Husain & Shreya Shankar, error analysis / LLM evals FAQ: https://hamel.dev/blog/posts/evals-faq/
- Shankar et al., *Who Validates the Validators?* (criteria drift, grading traces): https://arxiv.org/abs/2404.12272
- Grounded theory / open coding: https://en.wikipedia.org/wiki/Grounded_theory
- Langfuse: https://langfuse.com · Arize Phoenix: https://github.com/Arize-ai/phoenix · OpenTelemetry GenAI conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- Microsoft Presidio (PII): https://github.com/microsoft/presidio

---

## 5. Week 6 — Evals

**Brief:** [W6-Task-Set-D.md](W6-Task-Set-D.md) · Code: [backend/app/evals/](../backend/app/evals/) · Module M3

### 5.1 The problem

Every claim summary gets a quality score from an LLM judge that **nobody has ever checked against a human**. Claims ops wants to route work by that score, and a summary that invents coverage leads to a payout that shouldn't happen. You need to prove the judge agrees with a human, or find out it doesn't, and improve the agreement using evidence.

### 5.2 Requirements, in plain words
1. An eval set of **25+ cases**, each tagged with one Week-5 mode, including **≥2 regression cases replayed verbatim** from real failed traces. **One command** prints pass rate **by mode**.
2. Move **≥2 criteria out of the judge into deterministic assertions** and delete them from the judge prompt. Report assertion count vs judged-criteria count.
3. **Hand-label 25 summaries blind** on the judge's single binary criterion, **committed before** the judge runs.
4. Run the judge and compute **agreement %**. Iterate the prompt using **2 of its own disagreements as few-shot examples**, then report before → after.
5. Write a **one-sentence prediction** before iterating, then score it.

### 5.3 Concepts

#### A second generation path: claim summaries
- [summarize.py](../backend/app/generation/summarize.py): notes in, summary out. It has its own `SUMMARY_PROMPT_VERSION = "claims-summary-v1"` so Week 5's Q&A traces stay replayable.
- The output is **labelled lines + prose**, not forced JSON, so a model that can't find the date of loss can get that line *wrong*. Otherwise the assertion would be testing the parser instead of the app.

#### Deterministic assertions vs LLM judge
**Rule:** anything a regex can decide doesn't go to a model. A regex is free and never has an off day.

| Criterion | Where | Why |
|---|---|---|
| A1: claim number echoed in `CLM-YYYY-NNNNN` form | assertion | A format check |
| A2: date of loss present and a real calendar date (not "last Tuesday", not 2024-02-30) | assertion | Parseable by code |
| A3: excess/deductible is numeric | assertion | A format check |
| A4: an exclusion code is cited whenever a denial is stated | assertion | Internal consistency. A denial without a code is the sentence that becomes a bad-faith exhibit, and it's still not a judgement call |
| **C5: the coverage position rests on the wording that actually governs this claim** | **judge** (binary PASS/FAIL) | Real judgement: is it the right form and edition, and do the citations support the claims? |
| C6: writing quality | **deleted** | Nobody routes claims on prose quality, and averaging it in hides coverage errors |

- **Count: 4 assertions vs 1 judged criterion.** [assertions.py](../backend/app/evals/assertions.py), [test_assertions.py](../backend/tests/test_assertions.py).
- **Enforced:** [judge.py](../backend/app/evals/judge.py) refuses to load a prompt file that still mentions the asserted criteria.
- **Diff:** [judge_v0.txt](../evals/w6/judges/judge_v0.txt) (6 criteria, 1–10 score) → [judge_v1.txt](../evals/w6/judges/judge_v1.txt) (1 criterion, binary).

#### LLM-as-a-judge
- **What:** Using a model to grade another model's output.
- **When:** The criterion needs judgement and can't be expressed as code, and you've **validated** the judge against human labels.
- **Design choices here:**
  - **Binary, not 1–10.** Neither a model nor a human can reliably tell a 6 from a 7, and "within 1 counts as agreement" inflates the figure until it's meaningless.
  - **One criterion per judge.** Multi-criteria scores average away the one that matters.
  - **The prompt lives in a file** (`evals/w6/judges/judge_vN.txt`), so versions can be diffed and named.
  - **A separate `JUDGE_MODEL`** at temperature 0, so the judge doesn't silently inherit changes made to the app's model.
  - **The anchor case is spelled out** in v1: "A homeowners claim decided on dwelling-fire wording is a FAIL… Faithfully quoting the wrong policy is not a pass."
- **Known judge biases:** position bias, verbosity bias, self-preference (a model grading its own family), and leniency.
- **Alternatives:** Pairwise comparison judges, reference-based judges, a fine-tuned small classifier, or human review for high-stakes cases.

#### The blind labelling protocol
- **Why:** If you run the judge first and then write labels, you're just agreeing with yourself with extra steps.
- **Enforced in [label.py](../backend/app/evals/label.py) + [store.py](../backend/app/evals/store.py):**
  - `--next` never shows a judge verdict, and refuses to start if a judge run already exists for the current `summaries.sha`.
  - Each label records the sha256 of `summaries.json`, proving it's about the summary that was judged.
  - `judge.py` **won't run** until `labels_25.json` is committed and clean. The git commit is the ordering evidence (worth 25 points, and 0 without it).
- **Summaries are frozen:** They're generated once. Regenerating would silently invalidate every agreement number, so `--regenerate` is loud.

#### Agreement and Cohen's kappa
- **Agreement %:** (both PASS + both FAIL) / 25. This is the number the brief asks for.
- **Cohen's kappa:** `κ = (p_o − p_e) / (1 − p_e)`. It subtracts the agreement you'd expect by chance. If 22 of 25 are passes, a judge that always says PASS gets 88% agreement with κ≈0. [agreement.py](../backend/app/evals/agreement.py) reports both.
- **Confusion matrix, split by cost:** *judge PASS / human FAIL* is a payout that shouldn't happen. *judge FAIL / human PASS* costs an adjuster some wasted reading time. They're never averaged together.
- **Other metrics:** precision/recall of the judge on FAIL (treating human labels as ground truth), TPR/TNR, Krippendorff's alpha (for several raters).

#### Iterating the judge using its own disagreements
- Pick 2 cases where the judge and human disagreed, put them into judge_v2 as few-shot examples, and re-measure.
- **The honest version:** Only fix the **judge**. Relabelling the cases you disagreed on moves the ruler instead of fixing what's being measured.
- **Overfitting risk:** Agreement on the same 25 will rise partly because 2 of them are now in the prompt. Report that, or hold those 2 out.

#### Pass rate by mode (the one command)
- [run.py](../backend/app/evals/run.py) prints pass rate **per mode**. The overall figure is printed last and labelled as the least informative row.
- **Why:** An average hides a regression on the exclusion-citation mode while the easy notes-summarisation mode props up the number.
- A case passes only if **every applicable assertion AND the judge** pass, and both halves are reported separately.

#### Regression cases
- Notes replayed **verbatim** from a real failed trace, with `source_trace_id` named ([cases.py](../backend/app/evals/cases.py)). A regression case that's been tidied up is a different case.

#### Bonus: RAGAS faithfulness vs context precision
- **Faithfulness:** Are the summary's claims supported by the retrieved context?
- **Context precision:** Are the retrieved chunks relevant and ranked well?
- **The trap:** A summary can score **0.9+ faithfulness** while faithfully quoting the **wrong policy's** exclusions. It's faithful to bad context. The average hides it because most cases are fine. This is exactly why the v1 judge criterion says "faithfully quoting the wrong policy is not a pass".

### 5.4 Common mistakes and guards
| Mistake | Guard |
|---|---|
| Judge first, labels after | `judge.py` refuses until labels are committed; `label.py` refuses once a judge run exists |
| Relabelling to hit 85% | Labels are pinned to a sha, and the note has to say who was right |
| Paying a model to check formats | A1–A4 are regex, and the judge prompt loader rejects those criteria |
| 1–10 with "within 1" tolerance | Binary PASS/FAIL only |
| One overall pass rate | By-mode table, overall figure printed last |

### 5.5 Resources: Week 6
- Hamel Husain, *Creating a LLM-as-a-Judge That Drives Business Results*: https://hamel.dev/blog/posts/llm-judge/
- Eugene Yan, *Evaluating the Effectiveness of LLM-Evaluators*: https://eugeneyan.com/writing/llm-evaluators/
- Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* (judge biases): https://arxiv.org/abs/2306.05685
- Shankar et al., *Who Validates the Validators?*: https://arxiv.org/abs/2404.12272
- Cohen's kappa: https://en.wikipedia.org/wiki/Cohen%27s_kappa
- RAGAS docs (faithfulness, context precision): https://docs.ragas.io
- Eval tooling alternatives: promptfoo https://www.promptfoo.dev · DeepEval https://github.com/confident-ai/deepeval · Inspect AI https://inspect.aisi.org.uk · Braintrust, LangSmith evals

---

## 6. Week 7 — Agents vs workflows

**Brief:** [W7-Task-Set-D.md](W7-Task-Set-D.md) · **Write-up:** [week7/README.md](../week7/README.md) · Code: [backend/app/agents/](../backend/app/agents/) · Module M4

### 6.1 The problem

A hand-built agent triages claims: pull the claim, read the notes, check exclusions, compute the payout after the excess. The claims director asks: **does this need to be an agent, or would four hard-coded steps be faster, cheaper and easier to audit?** You have to settle it with numbers, not opinion.

### 6.2 Requirements, in plain words
1. Add a **third tool** (`compute_payout` or `get_adjuster_notes`) with a one-job description, an **enum** for claim status, and no overlap with the existing two.
2. Re-implement the same task as a **fixed workflow**: same tools, same model, same output contract, **no loop**.
3. **Race** both over the same 10 claims (≥3 where step 3 depends on what step 2 found). Report **pass rate, p50 latency, total tokens, cost per claim** for each system.
4. **Enforce all four budgets** (iterations, tokens, cost, wall-clock) and include a log of one clean budget termination.
5. A **verdict under 150 words** applying the decision rule ("does the path vary by input?"), naming the claim class that forces an agent, or stating that none does.

### 6.3 Concepts

#### Agent vs workflow
| | Workflow | Agent |
|---|---|---|
| Who picks the next step | **Code** (fixed path) | **The model** (loop until it stops calling tools) |
| Path | Same for every input | Varies by input |
| Cost and latency | Predictable, usually lower | Variable, usually higher (the message list is re-sent every lap) |
| Auditability | High: same six steps every time | Lower: need per-lap logs |
| Best when | The steps are known in advance | The next step depends on what the last one found and can't be enumerated |

- **The decision rule:** *Does the path vary by input?* If every claim can follow the same steps, use a workflow. Use an agent only for the input class where a fixed path demonstrably fails.
- Anthropic's *Building effective agents* makes the same argument: start with the simplest thing (a single call, then workflows like prompt chaining, routing, and orchestrator-workers) and add agentic loops only when needed.

#### The two implementations
- **Agent ([agent.py](../backend/app/agents/agent.py)):** `while True`: call the model with tools. If `stop_reason != "tool_use"`, parse the contract and stop. Otherwise run each tool call, append the results, and loop. The system prompt tells it to "search again if the first results do not contain the clause".
- **Workflow ([workflow.py](../backend/app/agents/workflow.py)):** Six fixed steps: `get_claim` → read notes → `search_policy(query=notes, policy_line)` **once** → **one** model call to decide → `compute_payout` → assemble the contract. No `while`, no retry, no second search.
- **The same `Budget` guards both**, so a hung request can't hide in either system.
- **Same model, same tools ([tools.py](../backend/app/agents/tools.py)), same rules and contract ([contract.py](../backend/app/agents/contract.py)).** The only variable is who picks the next step (the same one-variable principle as Week 4).
- **Thinking is disabled on both**, and neither system gets a setting the other lacks, so the race measures the architecture and not a setting.

#### Tool design (the third tool, and fixing tool thrash)
- **v1 problem:** `get_claim` "check[s] it against the policy" and `search_policy` "check[s] coverage for a claim". Both claimed the coverage job, so the model thrashed between them.
- **v2 fix, in the descriptions and not the system prompt** ([tool_descriptions.diff](../week7/tool_descriptions.diff)):
  - `get_claim`: returns the claim-file record only. *"It does not read policy wording and does not decide coverage."* `claim_number` uses the pattern `^CLM-\d{4}-\d{5}$`.
  - `search_policy`: returns policy text only, and *"knows nothing about any claim."* `policy_line` is an **enum** `{homeowners, dwelling_fire, condo}`, and `k` is bounded 1–8.
  - **`compute_payout` (new):** arithmetic only. `claim_status` is an **enum** `{covered, partial, denied, undetermined}`. It subtracts the excess first, then caps at the special limit (per HO-0521 §II), and returns 0 for denied or undetermined.
  - `additionalProperties: false` on every schema.
- **Why descriptions and not the system prompt:** Adding "use the correct tool" to the prompt leaves the description bug in place, and it comes back the next time a tool is added. `tools --check` enforces one job, typed enums, and no overlap.
- **Why `compute_payout` over `get_adjuster_notes`:** Notes already come back from `get_claim`, so a notes tool would overlap it. Payout arithmetic was a job no tool owned. Models make arithmetic mistakes, and code doesn't.

#### The four budgets ([budget.py](../backend/app/agents/budget.py))
| Budget | Default | Checked |
|---|---|---|
| `MAX_ITERS` | 8 laps | before each call |
| `MAX_TOKENS` | 60,000 **summed over every lap** | before and after each call |
| `MAX_COST_USD` | $0.25 | before and after each call |
| `WALL_CLOCK_S` | 90 s | before and after each call, plus the API timeout mapped to wall-clock |

- **Why sum tokens per lap:** The loop re-sends the whole message list every lap. Counting only the last call understates cost by a multiple of the lap count.
- **Clean termination:** `BudgetExceeded` is caught, and the run returns an `UNDETERMINED` contract naming which budget fired. It never raises and never spins. Demo: `--claim CLM-2026-10007 --max-iters 2 --log ../week7/budget_termination.log`.
- **"An unenforced budget is a comment with ambition."** Every limit is checked in code, and [test_agents.py](../backend/tests/test_agents.py) tests all four without network access.
- **Cost** = `(in_tok × price_in + out_tok × price_out) / 1M`, from `config.PRICING`. An unknown model aborts rather than guessing a price.

#### The output contract and grading
```json
{"claim_number": "CLM-2026-10001",
 "decision": "COVERED | PARTIAL | DENIED | UNDETERMINED",
 "exclusion_codes": ["E-15"],
 "payable_amount": 7500.0,
 "reason": "<one or two sentences citing chunk_ids>"}
```
**Pass** = the decision matches, required codes ⊆ cited codes ⊆ required + optional codes, and the payable amount is within $1. The parser doesn't repair malformed output.

#### The race set ([evals/w7/claims.jsonl](../evals/w7/claims.jsonl))
| Class | Claims | Why it's in the set |
|---|---|---|
| clean | 10001 | Sudden supply-line burst |
| notes_trigger_exclusion | 10002, 10003, 10006, 10007, 10010 | Notes reveal flood, seepage, association deductible, sewer + mould, or deferred maintenance |
| notes_trigger_limit | 10005, 10008 | Loss assessment ($250 form deductible), jewelry theft ($2,500 sublimit) |
| policy_line_trap | 10004 | Dwelling-fire excludes what homeowners covers |
| missing_notes | 10009 | The only right answer is UNDETERMINED |

- **Why this mix:** On 10 clean claims the workflow wins by construction. The race is decided by the input mix.
- **Pre-race evidence (no LLM needed):** The workflow's single search finds the needed clause for 8 of 10 claims. The decision rule predicts the agent can only win on **10001 and 10002**, where a second, reformulated search is the only way to reach the clause.
- **Fairness:** Claims are interleaved (workflow, then agent, claim by claim) so both see the same API conditions. The retriever is warmed up first so the embedding-model load isn't charged to whichever system runs first ([race.py](../backend/app/agents/race.py)).

#### Bonus: memory (sliding window + summarisation, persistence)
- **Sliding window:** Keep the last N turns verbatim, and summarise older ones.
- **Persist one fact across a process restart:** e.g. the excess amount, stored in a file or SQLite and reloaded at startup.
- **Expected finding:** Summarisation destroys a specific detail (a date, a dollar figure, a "three weeks" duration that triggers E-19). Name the detail and the claim it broke.
- **Alternatives:** Structured memory (extract key facts into a schema instead of free-text summaries), retrieval over past turns, MemGPT-style tiered memory, Anthropic's context-editing and memory tools.

### 6.4 Common mistakes and guards
| Mistake | Guard |
|---|---|
| Racing on clean claims only | 9 of 10 are exclusion, limit, trap, or missing-notes cases |
| Declaring the agent the winner when the table says otherwise | The verdict must agree with the table (0 points otherwise) |
| Counting only the final call's tokens | `Budget.charge` sums every lap |
| Budgets that are only constants | `check()` + `charge()` + tests for all four |
| Fixing thrash through the model or prompt | Fixed in the tool descriptions, enforced by `tools --check` |

### 6.5 Resources: Week 7
- Anthropic, *Building effective agents*: https://www.anthropic.com/research/building-effective-agents
- Anthropic tool use docs: https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview
- Anthropic, *Writing effective tools for agents*: https://www.anthropic.com/engineering/writing-tools-for-agents
- Yao et al., *ReAct: Synergizing Reasoning and Acting*: https://arxiv.org/abs/2210.03629
- Packer et al., *MemGPT* (tiered memory): https://arxiv.org/abs/2310.08560
- JSON Schema (enums, patterns, `additionalProperties`): https://json-schema.org/understanding-json-schema
- Framework alternatives: LangGraph https://langchain-ai.github.io/langgraph/ · OpenAI Agents SDK · Claude Agent SDK · CrewAI · Temporal / Prefect (durable workflows)

---

## 7. Cross-cutting principles

| Principle | Where it shows up | Why |
|---|---|---|
| **One variable per run** | W3 chunker vs embedding · W4 `retriever` only · W6 judge prompt only · W7 who picks the step | Two changes tell you nothing about which one moved the number |
| **Baseline before change** | W4 baseline 8/12 written first · W5 prediction committed before the fix · W6 labels committed before the judge | Order is evidence, and git commits prove it |
| **Write the test set before the results** | W3 questions from the endorsements · W4 golden set · W5 traffic bank · W6 gold positions | Otherwise you're measuring your question-writing |
| **Look at the data** | W4 inspection view · W5 reading 20 traces | "Felt wrong" isn't evidence |
| **Break the number down** | W4 exact-token vs prose · W6 pass rate by mode | Averages hide the failure that matters |
| **Report the cost** | W4 p50 latency · W7 tokens and $ per claim | A gain without its cost is half a result |
| **Deterministic where possible** | W6 regex assertions · W7 `compute_payout` · redaction regex | Free, testable, never has an off day |
| **Enforce rules in code** | Ingest refuses UNKNOWN · opencode refuses diagnosis words · judge refuses before labels · budgets raise | A rule that lives only in a runbook gets broken at 11pm |
| **Severity over frequency** | W5 ranking · W6 confusion-matrix cells | Wrongly paying a claim outweighs annoying an adjuster |
| **Refuse rather than invent** | W3 forced refusal · W7 UNDETERMINED on missing notes or a fired budget | Bad-faith exposure |

---

## 8. Status

As of the current working tree:

| Week | Built | Deliverables produced | Still pending |
|---|---|---|---|
| 3 | Both chunkers, ingest, filter, grounded answer, refusal | Search dumps, hit table (8/8 vs 8/8) | — |
| 4 | Golden set, BM25, RRF, hitrate, inspect, MMR, UI | [results.md](../results.md) with every number | Answer-side `--answers` pass (needs `LLM_API_KEY`) |
| 5 | Tracing, redaction, replay, sampling, open-coding, taxonomy, and notes tools; [RUNBOOK](../week5/RUNBOOK.md) | Traffic banks | `traces.jsonl`, `sample.json`, 20 open codes, `modes.json`, `taxonomy.md`, `notes.md`, filled `prediction.md` + commit hash, filled `benchmark_note.md` |
| 6 | Summarizer, assertions A1–A4, judge v0/v1, label, agreement, run, store | `judge_v0.txt`, `judge_v1.txt` | `eval_set.jsonl` (25+ cases), `summaries.json`, **`labels_25.json` committed first**, `prediction.txt`, `judge_v2.txt`, agreement before/after, the disagreement note, `week6/assertion_split.md` |
| 7 | Agent, workflow, budget, tools v1/v2, contract, race, run log | `tools_v1/v2.json`, description diff, `claims.jsonl`, pre-race evidence | `race.csv` (8 numbers), `budget_termination.log`, the verdict paragraph (needs `LLM_API_KEY`) |

**Order for Week 6 (it matters, because the blind protocol is worth 25 points):** build the eval set → `run --generate` (freezes the summaries) → `label` all 25 → **commit `labels_25.json`** → write `prediction.txt` → run judge v1 → agreement → write v2 using 2 disagreements → run v2 → agreement before → after.

---

## 9. Glossary

| Term | Meaning |
|---|---|
| **RAG** | Retrieve relevant passages, then generate an answer from them |
| **Chunk** | The unit of text that gets embedded, retrieved, and cited |
| **Embedding** | A vector representing the meaning of a piece of text |
| **Dense retrieval** | Search by embedding similarity (cosine) |
| **Sparse / lexical retrieval** | Search by term matching (BM25) |
| **Hybrid retrieval** | Dense + sparse, fused (here with RRF) |
| **Bi-encoder / cross-encoder** | Encode query and doc separately / jointly |
| **HNSW** | Graph-based approximate nearest-neighbour index |
| **Top-K / hit@k** | Return K results / is the gold result among the top k |
| **Golden set** | A fixed set of questions with known-correct answers |
| **RRF** | Reciprocal Rank Fusion, Σ 1/(k+rank) |
| **MMR** | Maximal Marginal Relevance, a relevance vs diversity trade-off |
| **p50 / p95** | Median / 95th-percentile latency |
| **R / G / NIC** | Retrieval failure / generation failure / not in corpus |
| **Trace** | A replayable record of one request |
| **Open coding** | One observation sentence per item, with no categories yet |
| **Taxonomy** | Named, counted, severity-ranked failure modes |
| **Assertion** | A deterministic code check (regex or parse) |
| **LLM judge** | A model grading output against a criterion |
| **Agreement / Cohen's κ** | Raw match rate / match rate corrected for chance |
| **Regression case** | An eval case replayed verbatim from a real failure |
| **Agent** | An LLM in a loop choosing tools until done |
| **Workflow** | A fixed, code-defined sequence of steps |
| **Budget** | A hard limit (iterations, tokens, cost, time) that terminates a run |
| **Tool thrash** | The model alternating between tools with overlapping descriptions |
| **Excess / deductible** | The amount the insured pays before coverage applies |
| **Endorsement / form / edition** | A policy amendment / its form number (HO-0304) / its version date (ed. 03-24) |
| **Exclusion code** | A row in an exclusions table (E-17 etc.). The same code can mean different things in different forms |

---

## 10. Master resource list

**RAG and retrieval**
- RAG paper: https://arxiv.org/abs/2005.11401
- Sentence-Transformers: https://www.sbert.net
- MTEB: https://huggingface.co/spaces/mteb/leaderboard
- HNSW: https://arxiv.org/abs/1603.09320
- BEIR: https://arxiv.org/abs/2104.08663
- RRF (Cormack 2009): https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
- ColBERT: https://arxiv.org/abs/2004.12832
- Lost in the Middle: https://arxiv.org/abs/2307.03172
- Anthropic, Contextual Retrieval: https://www.anthropic.com/news/contextual-retrieval
- Chroma: https://docs.trychroma.com · Qdrant: https://qdrant.tech/documentation/ · pgvector: https://github.com/pgvector/pgvector · FAISS: https://github.com/facebookresearch/faiss
- rank_bm25: https://github.com/dorianbrown/rank_bm25

**Error analysis and evals**
- Hamel Husain, Your AI Product Needs Evals: https://hamel.dev/blog/posts/evals/
- Hamel Husain, LLM-as-a-Judge: https://hamel.dev/blog/posts/llm-judge/
- Evals FAQ (Husain & Shankar): https://hamel.dev/blog/posts/evals-faq/
- Who Validates the Validators?: https://arxiv.org/abs/2404.12272
- Judging LLM-as-a-Judge: https://arxiv.org/abs/2306.05685
- Eugene Yan on LLM evaluators: https://eugeneyan.com/writing/llm-evaluators/
- RAGAS: https://docs.ragas.io
- Cohen's kappa: https://en.wikipedia.org/wiki/Cohen%27s_kappa

**Tracing and observability**
- Langfuse: https://langfuse.com · Arize Phoenix: https://github.com/Arize-ai/phoenix · OpenTelemetry GenAI: https://opentelemetry.io/docs/specs/semconv/gen-ai/ · Presidio: https://github.com/microsoft/presidio

**Agents**
- Building effective agents: https://www.anthropic.com/research/building-effective-agents
- Writing tools for agents: https://www.anthropic.com/engineering/writing-tools-for-agents
- Tool use docs: https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview
- ReAct: https://arxiv.org/abs/2210.03629 · MemGPT: https://arxiv.org/abs/2310.08560

**Stack docs**
- FastAPI: https://fastapi.tiangolo.com · Vite: https://vitejs.dev · React: https://react.dev · pytest: https://docs.pytest.org · Anthropic Python SDK: https://github.com/anthropics/anthropic-sdk-python
