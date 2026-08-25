# Results — Claims RAG, chunking bench

> Fill every section. Numbers and pasted transcripts score; "it works" and polish score zero.

**Run metadata**

| | |
| --- | --- |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` (unchanged across both runs) |
| k | 5 |
| Documents indexed | 6 endorsements **only** — the base wording library was not re-indexed |
| Chunkers compared | `current` (fixed 1000/150 window) vs `structure_aware` (form/clause split) |

---

## 1. The 8 questions and their known-correct form_number / clause

Written from the endorsements **before** any search was run.

| # | Question | Known answer | form_number | clause | table row? |
| - | -------- | ------------ | ----------- | ------ | ---------- |
| Q1 | | | | | ✅ |
| Q2 | | | | | ✅ |
| Q3 | | | | | ✅ |
| Q4 | | | | | |
| Q5 | | | | | |
| Q6 | | | | | |
| Q7 | | | | | |
| Q8 | | | | | |

---

## 2. hit-in-top-5 — both chunkers, same 8 questions

<!-- paste the output of: python -m app.retrieval.evaluate --markdown -->

| Strategy | hit-in-top-5 |
| -------- | ------------ |
| `current` | **?/8** |
| `structure_aware` | **?/8** |

Per-question record:

<!-- paste the per-question table here — a summary claim alone scores zero -->

Full search-only dump for all 8 questions under both strategies:
[`evals/search-dumps/`](evals/search-dumps/)

---

## 3. Metadata filter changing the top-1 result

Query: `<the query>`

**Unfiltered**

```
<paste result list with scores>
```

**Filtered — `policy_line = <value>`**

```
<paste result list with scores>
```

What changed and why: …

---

## 4. Three cited answers

Each citation must resolve to a real `chunk_id` — verified by
`GET /api/chunk/{strategy}/{chunk_id}`.

### A1
```
<paste transcript verbatim>
```

### A2
```
```

### A3
```
```

---

## 5. Three refusals (out-of-corpus)

These live in systems that were never indexed. The refusal is forced by the
grounding prompt, not suggested.

### R1 — reserve-setting threshold for claim CLM-2024-88431
```
<paste transcript verbatim>
```

### R2
```
```

### R3
```
```

---

## 6. Which chunker ships, and why

One paragraph. Name the strategy, cite the two numbers, and say what the losing
one got wrong structurally — not that it "looked worse".

…

---

## 7. The retrieval that embarrassed me

The query, what came back, and the diagnosis — why the chunker or the metadata
produced that result.

…

---

## 8. Bonus — structure-aware wins retrieval, loses the answer

A question where the tight exclusion-row chunk retrieves precisely and then
strands the model without the definitions clause that scopes it.

| | structure_aware | current |
| --- | --- | --- |
| Retrieved rank of the right chunk | | |
| Final answer | | |

Two sentences on the precision/completeness tension: …
