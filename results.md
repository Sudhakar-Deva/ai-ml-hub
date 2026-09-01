# Results — Week 4 · Task Set D

## Label the failures, then buy back hit-rate@3 with exactly one change

**The one-line answer:** the failures were not the model. 4 of 4 were **R** —
retrieval never fetched the clause — and all 4 were exclusion-code / form-number
lookups. One retrieval change (BM25 + RRF, k=60) took hit-rate@3 from
**8/12 → 11/12** for **+1.3 ms p50**. Swapping the model would have fixed none of them.

**Run metadata**

| | |
| --- | --- |
| Chunker | `structure_aware` — unchanged across both runs (Week 3's winner) |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` — unchanged across both runs |
| Corpus | the 6 endorsements in [data/endorsements/](data/endorsements/), 55 chunks |
| k | 3 (hit-rate@3) |
| The ONE variable changed | `retriever`: `dense` → `hybrid` (dense + BM25, fused with RRF k=60) |
| Candidate depth per arm | 25 |
| Raw dumps | [`evals/w4-runs/`](evals/w4-runs/) |

Reproduce:

```bash
cd backend
python -m app.retrieval.hitrate --retrievers dense --markdown          # the baseline, before
python -m app.retrieval.inspect --retriever dense --answers --markdown # the labels
python -m app.retrieval.hitrate --retrievers dense hybrid --markdown   # before -> after
```

---

## 1. The 12-question golden set

[`evals/golden_set.jsonl`](evals/golden_set.jsonl) — written from the endorsements
and from how an adjuster actually types a question into a claim note, **before**
any Week-4 search was run. 6 of the 12 carry an exact token dense retrieval is
structurally bad at (requirement: at least 4).

Scoring is strict: a hit means the **gold `chunk_id` itself** is in the top-3. The
right form with the wrong clause is a miss, which is the entire point — "three
fluent water-damage clauses, none of them E-17" must not be able to score as a pass.

| # | Question | Known-correct chunk_id | Exact token |
| - | -------- | ---------------------- | ----------- |
| G01 | Does exclusion E-17 apply under form HO-0304 ed. 03-24 when a supply line ruptures and floods the kitchen? | `structure_aware:HO-0304:HO-0304-ed-03-24.md:0004` | **E-17 · HO-0304 ed. 03-24** |
| G02 | Same loss on a dwelling fire risk — is E-17 excluded under DP-0110 ed. 02-24? | `structure_aware:DP-0110:DP-0110-ed-02-24.md:0002` | **E-17 · DP-0110 ed. 02-24** |
| G03 | What is the aggregate sub-limit in HO-0521 ed. 06-24 for remediation of fungi, wet or dry rot, or bacteria? | `structure_aware:HO-0521:HO-0521-ed-06-24.md:0003` | **HO-0521 ed. 06-24** |
| G04 | The association is assessing the unit owner for its master policy deductible — does E-31 under CO-0715 ed. 04-24 exclude that? | `structure_aware:CO-0715:CO-0715-ed-04-24.md:0003` | **E-31 · CO-0715 ed. 04-24** |
| G05 | Does E-21 in HO-0304 still exclude mold remediation when the mold came from a covered water loss? | `structure_aware:HO-0304:HO-0304-ed-03-24.md:0008` | **E-21 · HO-0304** |
| G06 | Under HO-0304, what is the E-19 duration threshold and when does the clock start? | `structure_aware:HO-0304:HO-0304-ed-03-24.md:0006` | **E-19 · HO-0304** |
| G07 | Supply line under the sink burst overnight and flooded the kitchen — is the water damage covered on a homeowners policy? | `structure_aware:HO-0304:HO-0304-ed-03-24.md:0004` | no |
| G08 | The insured says the leak was sudden — what does the policy actually require before I can treat a loss as sudden and accidental? | `structure_aware:HO-0417:HO-0417-ed-05-24.md:0002` | no |
| G09 | Is the flexible connector between the shutoff valve and the fixture part of the supply line, or is it a drain line? | `structure_aware:HO-0417:HO-0417-ed-05-24.md:0003` | no |
| G10 | How long does the insured have to get us a signed and sworn proof of loss, and when does that clock start? | `structure_aware:HO-0608:HO-0608-ed-01-24.md:0005` | no |
| G11 | Landlord is refusing to let us inspect the plumbing on the rental — do we still owe water coverage while he refuses? | `structure_aware:DP-0110:DP-0110-ed-02-24.md:0008` | no |
| G12 | One continuous leak damaged three rooms before anyone noticed — is that one occurrence or three for the deductible? | `structure_aware:HO-0417:HO-0417-ed-05-24.md:0005` | no |

G01 and G07 ask the same coverage question — one in exclusion-code form, one in
adjuster-prose form — and point at the same gold chunk. That pair is the cleanest
evidence in the set that the failure is about the *token*, not the *topic*: prose
found it, the code did not.

---

## 2. Baseline hit-rate@3 — written down before anything was changed

> **`dense` (Chroma cosine, the Week 3 retriever): 8/12 = 66.7%**
> p50 latency 7.4 ms · p95 9.3 ms

Dump: [`evals/w4-runs/dense_20260901T203736Z.json`](evals/w4-runs/dense_20260901T203736Z.json)

Split by question type, which is where the number stops being one number:

| Question type | hit-rate@3 |
| ------------- | ---------- |
| 6 exact-token questions (code / form number) | **2/6** |
| 6 prose questions | **6/6** |

Every prose question passed at rank 1 or 3. Every failure was a literal-token
lookup. That split is the whole diagnosis.

---

## 3. The tally — R / G / Not-In-Corpus, one line of evidence each

Produced by the inspection view:
`python -m app.retrieval.inspect --retriever dense --markdown`
→ [`evals/w4-runs/labels_dense_20260901T202744Z.json`](evals/w4-runs/labels_dense_20260901T202744Z.json)

> **R = 4 · G = 0 · Not-In-Corpus = 0 · passed = 8** (of 12)

| # | Label | Evidence — one line, from the inspection view |
| - | ----- | --------------------------------------------- |
| G01 | **R** | Gold `HO-0304:…:0004` (the E-17 row) absent from top-3; the 3 slots went to HO-0304 *APPLICATION OF THESE EXCLUSIONS*, HO-0304 *APPLICATION … / E-19*, and **DP-0110 *SECTION I — EXCLUSIONS / E-17*** — the right code on the wrong form. |
| G02 | **R** | Gold `DP-0110:…:0002` absent from top-3; the slots went to DP-0110 *APPLICATION*, DP-0110 *SECTION I — EXCLUSIONS* (the prose stem), DP-0110 *preamble* — right form, three times, never the row. |
| G05 | **R** | Gold `HO-0304:…:0008` (the E-21 row) absent from top-3; the slots went to HO-0521 *A. Remediation of "fungi"…*, HO-0304 *CONDITIONS*, HO-0304 *E-22* — semantically about mold, none of them E-21. |
| G06 | **R** | Gold `HO-0304:…:0006` (the E-19 row) absent from top-3; the slots went to DP-0110 *APPLICATION*, HO-0304 *APPLICATION … / E-19*, HO-0304 *E-22* — two paragraphs *about* E-19, not the row that states the 14-day rule. |

**Not-In-Corpus = 0**, and that is a check, not an assumption: the harness resolves
every gold `chunk_id` against the store before labelling
([inspect.py](backend/app/retrieval/inspect.py) — `gold_in_corpus`), and all 12
resolve. The three genuinely out-of-corpus probes are held separately in
[`evals/questions.json`](evals/questions.json) (`out_of_corpus`) and are a refusal
test, not a retrieval test.

**G = 0 — and this is the label that had to be earned, not assumed.** G01 is the
trap the brief warns about: its dense top-3 *did* contain an E-17 row, so an answer
reading "excluded" looks like the model misusing good context. It is not. The E-17
row it got was **DP-0110's** — the dwelling-fire form, where E-17 *is* excluded —
while the question named HO-0304, where E-17 is expressly **not**. Right code,
wrong form: the model was handed a confidently wrong document, which is R.

> **Status of the answer-side pass.** The retrieval evidence above is complete and
> is what every label rests on. The LLM answer pass — the second, independent
> confirmation that no *passing* question hides a G — needs `LLM_API_KEY` in `.env`
> and has not been run:
> `python -m app.retrieval.inspect --retriever dense --answers --markdown`
> It cannot change any of the 4 R labels (a chunk that never reached the model
> cannot have been misused); it can only convert a currently-passing row to G.

---

## 4. The one change, and why the tally chose it

**BM25 + RRF fusion, k=60.** ([hybrid.py](backend/app/retrieval/hybrid.py),
[lexical.py](backend/app/retrieval/lexical.py))

Four of four failures are R, and all four are the same R: a literal identifier —
`E-17`, `E-21`, `E-19`, a form number — that the embedding does not preserve.
MiniLM encodes "an exclusion clause about water damage" and discards the digits,
which are the entire question; that is why G06's top-3 held two paragraphs *about*
E-19 and not the row stating the rule, and why G01 returned the E-17 row from the
wrong form. **A cross-encoder rerank cannot fix this class.** A reranker only
reorders what the first stage retrieved, and for G06 the gold chunk is not in the
dense top-25 at all — there is nothing there for it to promote. BM25 scores the
literal token `e-17` as a high-IDF term, so the chunk enters the candidate list in
the first place; RRF then fuses the two arms on **rank**, never on score, because a
cosine in [0.2, 0.8] and an unbounded BM25 score are not on the same scale and
adding them just hands every query to whichever arm has the larger numbers. The
tally pointed at lexical recall, so lexical recall is what got bought — one change,
and the reranker stays on the shelf until a tally says otherwise.

---

## 5. Before → after, both numbers

Same 12 questions, same chunker, same embedding model, k=3. p50 is over 9 samples
per question (108 measurements per retriever); a single sample per question puts a
1 ms delta inside the noise.

| | `dense` (before) | `hybrid` (after) | Δ |
| --- | --- | --- | --- |
| **hit-rate@3** | **8/12 (66.7%)** | **11/12 (91.7%)** | **+3 questions, +25 pts** |
| **p50 latency / query** | **7.4 ms** | **8.7 ms** | **+1.3 ms (+18%)** |
| p95 latency / query | 9.3 ms | 10.2 ms | +0.9 ms |
| BM25 index build | — | 4.5 ms | one-time, at process start |
| exact-token questions | 2/6 | 5/6 | +3 |
| prose questions | 6/6 | 6/6 | unchanged |

Dumps: [`dense_20260901T203736Z.json`](evals/w4-runs/dense_20260901T203736Z.json) ·
[`hybrid_20260901T203736Z.json`](evals/w4-runs/hybrid_20260901T203736Z.json) ·
[`hitrate_20260901T203736Z.md`](evals/w4-runs/hitrate_20260901T203736Z.md)

Repeat runs land at 7.4–7.5 ms (`dense`) and 8.6–8.7 ms (`hybrid`), so the +1.3 ms
is a real gap and not run-to-run drift — but it is a ~1 ms gap, and it should be
read as "about a millisecond", not as three significant figures.

**The honest reading of the latency number.** +1.3 ms p50 is real but it is
retrieval-only, on a 55-chunk corpus, with an in-memory BM25 index. It is not a
number that survives a 500k-chunk library — BM25 there means a real index, and the
cost would have to be re-measured, not extrapolated. What it *does* establish is
the shape of the trade at this size: the change is free relative to the ~1–2 s the
LLM call adds on top, so p50 is not the constraint here.

---

## 6. Per-question: fixed / unfixed / untouched

| # | Exact token | dense rank | hybrid rank | Which arm found the gold chunk | Verdict |
| - | ----------- | ---------- | ----------- | ------------------------------ | ------- |
| G01 | yes | miss | **#3** | bm25 #2 (dense had it at #8) | **R fixed** |
| G02 | yes | miss | **#2** | bm25 #1 (dense #4) | **R fixed** |
| G03 | yes | #1 | #1 | both arms #1 | already passing |
| G04 | yes | #2 | #2 | bm25 #1, dense #2 | already passing |
| G05 | yes | miss | **#3** | bm25 #2 (dense #6) | **R fixed** |
| G06 | yes | miss | **miss** | neither — bm25 #7, dense outside top-25 | **R NOT fixed** |
| G07 | no | #3 | **#1** | bm25 #1, dense #3 | passing, promoted 3 → 1 |
| G08 | no | #1 | #1 | dense #1 | untouched |
| G09 | no | #1 | #1 | both #1 | untouched |
| G10 | no | #1 | #1 | both #1 | untouched |
| G11 | no | #1 | #1 | dense #1 | untouched |
| G12 | no | #1 | #1 | both #1 | untouched |

**Fixed by the change: G01, G02, G05.** All three are exclusion-code lookups where
BM25 put the gold row in the top 2 of its arm and RRF carried it into the top-3.

**Not touched at all: G08–G12.** The five prose questions were at rank 1 before and
rank 1 after. The change bought nothing there, and it was never supposed to — that
is what "the tally chose it" means. (G07, also prose, moved 3 → 1: the same rank-1
BM25 evidence that fixed the code lookups also firmed up a prose question that was
already scraping in.)

**Still broken: G06** — and it is not the retriever's fault, which matters for what
we do next. The gold chunk is the E-19 row from HO-0304's exclusion table. Two
things beat it, both legitimately: DP-0110's *APPLICATION* paragraph and HO-0304's
own *APPLICATION OF THESE EXCLUSIONS / E-19* paragraph, each of which discusses
E-19 by name in running prose. Meanwhile the gold row's own chunk carries four
unrelated rows with it (E-15 through E-18 arrive as its "table header" — see
[structure_aware_chunker.py](backend/app/chunking/structure_aware_chunker.py)
`_table_header`), which dilutes its term frequency for `e-19` and drops it to BM25
#7 and fused #16. **This is a chunking defect, not a retrieval defect**, and no
amount of fusion or reranking repairs it — the fix is to stop dragging four
irrelevant rows into a row-level chunk. That is next week's one change, measured
the same way.

---

## 7. Shipping decision

**Ship `hybrid`.** The number behind it: **8/12 → 11/12 hit-rate@3 (+25 points) for
+1.3 ms p50** — a 3-question gain against a latency cost that is under 1% of the
end-to-end answer time, on a change that touches one function
([search.py](backend/app/retrieval/search.py) `retriever`) and is a one-line
rollback.

The specific exposure it closes is the one from the brief: an adjuster asking
"does E-17 apply under HO-0304 ed. 03-24" and being handed **DP-0110's** E-17 row,
which says *excluded* where HO-0304 says *not excluded*. Before the change, that
was the top-3 on a live query. After it, HO-0304's own E-17 row is in the top-3.

What shipping this does **not** buy, stated plainly: nothing for the 6 prose
questions (6/6 before and after), and nothing for G06, whose fix lives in the
chunker. And the model swap the team lead asked for would have bought **zero** of
the 4 failures — all four were R, and the model never saw the clause.

---

## 8. Bonus — MMR over the fused candidate list

[mmr.py](backend/app/retrieval/mmr.py). MMR reorders the 25 fused candidates with
`λ·rel − (1−λ)·max sim(d, selected)`, where `rel` is the RRF score min-max
normalised and the similarity is cosine between chunk embeddings. Tuned once, three
values, same 12 questions:

| Retriever | hit-rate@3 | p50 | mean distinct forms in top-3 | mean pairwise cosine in top-3 (lower = more diverse) | misses |
| --------- | ---------- | --- | ---------------------------- | ---------------------------------------------------- | ------ |
| `hybrid` (shipped) | **11/12** | 8.7 ms | 1.75 | 0.6574 | G06 |
| `hybrid+mmr λ=0.9` | 10/12 | 16.6 ms | 1.75 | 0.6428 | G05, G06 |
| `hybrid+mmr λ=0.7` | 9/12 | 16.7 ms | 1.83 | 0.5783 | G04, G05, G06 |
| `hybrid+mmr λ=0.5` | 8/12 | 17.0 ms | 2.25 | 0.4501 | G01, G04, G05, G06 |

Diversity moves exactly as advertised — pairwise similarity in the top-3 falls from
0.66 to 0.45 as λ drops, and the top-3 starts spanning 2.25 forms instead of 1.75.
And hit-rate falls monotonically with it: **every step of diversity is paid for
with a correct answer.** At λ=0.5 the E-17 query (G01) loses the gold chunk
outright — MMR spends a slot on DP-0110's near-identical E-17 row precisely
*because* it is near-identical, which is the failure mode the brief predicts:
nothing in MMR knows that HO-0304 is the edition the adjuster asked about.

**Would I ship it? No.** At its best setting (λ=0.9) MMR costs one question and
doubles p50 to buy a 0.015 drop in redundancy. The redundancy it is fighting is
real — the top-3 for the E-17 query is genuinely one fact wearing three hats — but
diversity is not the metric an adjuster is served by. Deduplicating *identical
clause text across editions* is worth doing; the right instrument for that is a
metadata rule (one chunk per `form_number` in the top-3, or a `form_number` filter
from the question), which drops the duplicates without ever putting the correct
edition at risk. MMR trades away the wrong thing here, and the table is the reason.

---

## 9. The code diff — exactly one retrieval change

```
backend/app/retrieval/lexical.py   NEW  — BM25 arm over the same chunks
backend/app/retrieval/hybrid.py    NEW  — RRF fusion (k=60) of the two rankings
backend/app/retrieval/search.py    MOD  — `retriever` param routes dense | hybrid
                                          the dense path is byte-for-byte the before run
backend/app/config.py              MOD  — EVAL_K=3, CANDIDATE_K=25, RRF_K=60,
                                          SHIPPED_RETRIEVER="hybrid"
backend/app/generation/answer.py   MOD  — answers with the shipped retriever, and
                                          takes it as an argument so the inspection
                                          view labels what the model was really handed

measurement / inspection only, not part of the retrieval change:
backend/app/retrieval/hitrate.py   NEW  — hit-rate@3 + p50, per retriever
backend/app/retrieval/inspect.py   NEW  — the inspection view + R/G/NIC labels
backend/app/retrieval/mmr.py       NEW  — bonus only, never in the shipped path
backend/app/api/routes.py          MOD  — /api/inspect, /api/hitrate, /api/golden-set
backend/tests/test_hybrid.py       NEW  — RRF fuses ranks; tokenizer keeps E-17 whole
frontend/src/components/…          NEW  — InspectionView, HitRateTable
evals/golden_set.jsonl             NEW  — the 12 questions
```

`git diff` for the retrieval change itself:

```bash
git diff -- backend/app/retrieval/search.py backend/app/config.py
git show --stat -- backend/app/retrieval/hybrid.py backend/app/retrieval/lexical.py
```

The before run and the after run differ by one argument value:
`search(..., retriever="dense")` → `search(..., retriever="hybrid")`. Chunker,
embedding model, corpus, k, and the golden set are identical across both.

---

## 10. Submission checklist

- [x] `golden_set.jsonl` — 12 real adjuster questions, each with its known-correct `chunk_id` (6 exact-token, requirement was 4)
- [x] Baseline hit-rate@3 = 8/12, written down before any change was made
- [x] R/G/Not-In-Corpus tally — R=4, G=0, NIC=0 — with one line of evidence per failure
- [x] Before → after hit-rate@3 and p50 latency in one table (§5)
- [x] Per-question fixed / unfixed / untouched table (§6)
- [x] Code diff showing exactly one retrieval change (§9)
- [x] Shipping decision with the number behind it (§7)
- [x] Bonus: MMR, λ tuned, hit-rate **and** diversity reported, ship/no-ship answered (§8)
- [ ] Answer-side pass (`--answers`) to confirm no passing question hides a G — needs `LLM_API_KEY`
