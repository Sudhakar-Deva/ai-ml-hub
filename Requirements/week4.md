# Week 4 · Module 2 — Retrieval & RAG

## Debugging Retrieval — Hybrid, Reranking & Failure Separation

**Build week**

Find out exactly why your app gets things wrong, fix it, and prove the fix with a number.

|                   |                      |
| ----------------- | -------------------- |
| **Week**          | 4 of 12              |
| **Module**        | M2 — Retrieval & RAG |
| **Evaluated**     | Week 5 · Monday      |
| **Mentor review** | Friday, no marks     |

---

## What this week is about

Your document app from last week works — but sometimes it's wrong. "Wrong sometimes" is useless to fix. This week you learn to tell apart the two kinds of wrong: the app fetched the wrong document, or it fetched the right one and still messed up the answer. They need completely different fixes.

---

## Why it matters

**Why not just switch to a smarter AI model when it's wrong?**

If the problem is that the app fetched the wrong document, a smarter model changes nothing. You'd pay more and fix nothing.

**What does "hybrid search" mean?**

Combining two ways of searching — by meaning and by exact words — so you catch both "what does the policy say" and exact codes like ERR-4032.

**Why measure instead of eyeballing it?**

So you can prove a change actually helped, with a number, instead of a gut feeling.

---

## What you'll learn

- The two kinds of failure: fetched the wrong document, vs. fetched the right one and answered badly
- Building a simple view that shows the question, what was fetched, and the final answer side by side
- Adding keyword search alongside meaning search, so exact terms (codes, names, IDs) aren't missed
- "Reranking": a second pass that pushes the best result to the top
- Rewriting a user's messy question into a better search
- Measuring "did the right document show up?" as a number, before and after your change

---

## Topics covered — the exact concepts to study

- Retrieval vs generation failures
- The inspection view
- Keyword search (BM25)
- Keyword vs semantic search
- Hybrid search (RRF fusion)
- Reranking (cross-encoder)
- Cohere Rerank / BGE-Reranker
- MMR
- Query rewriting
- HyDE
- hit-rate@k, recall@k, MRR

---

## Your task this week

**Evaluated Week 5 · Monday**

Take a set of failing questions and sort each one into "wrong document fetched" or "right document, wrong answer." Then make one improvement, and measure whether the right document now shows up more often — with a before-and-after number.

| Option | Domain                   | Task                                                                 |
| ------ | ------------------------ | -------------------------------------------------------------------- |
| A      | Customer support tickets | Label the failures, then buy back hit-rate@3 with exactly one change |
| B      | Recipes & food           | Label the failures, then buy back hit-rate@3 with exactly one change |
| C      | HR policy                | Label the failures, then buy back hit-rate@3 with exactly one change |
| D      | Insurance claims         | Label the failures, then buy back hit-rate@3 with exactly one change |
| E      | Developer documentation  | Label the failures, then buy back hit-rate@3 with exactly one change |
| F      | Legal contracts          | Label the failures, then buy back hit-rate@3 with exactly one change |

Same task, six different topics — so everyone works on their own version. Download whichever you're assigned.

---

## How your mentor checks

**Friday · no marks**

A quick review of your task. Not a test — just a few things your mentor looks at, so you can fix anything before Monday.

- Can they show, for a specific failure, which of the two kinds it is — with evidence?
- Did they make one change (not five) so they know what actually helped?
- Is there a before-and-after number, not just "it feels better"?
- Did they notice which failures their change did NOT fix?
