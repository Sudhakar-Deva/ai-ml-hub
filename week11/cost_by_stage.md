# Cost per query, by stage

## The found request (`req_e9fffc122627`, `claims-summary-v1`), straight from its spans

| stage | what runs | latency | tokens in / out | cost | share of cost |
|---|---|---|---|---|---|
| retrieval | hybrid search (local MiniLM embedder + Chroma + BM25), k=5 | 5,565 ms* | 0 / 0 | **$0.0000000** | 0% |
| generation | `openai/gpt-oss-120b`, one call, temp 0 | 1,517 ms | 1,779 / 385 | **$0.0004978** | **100%** |
| tools | citation resolution against the index (×1) | 6 ms | 0 / 0 | **$0.0000000** | 0% |
| **total** | | 7,088 ms | 2,164 | **$0.0004978** | |

\* The squadmate ran this request as a fresh process, so the embedder loaded inside the span. Across yesterday's 22
requests, retrieval latency is **p50 43 ms**.

Retrieval and tools have no API cost: the embedder and the index run locally. Their real cost is compute and latency, not
dollars. **Every dollar is generation**, so generation is the only stage where a cost change can come from.

## What the fix cost (same 11 suite inputs, measured)

| | v1 (before fix) | v2 (after fix) | Δ |
|---|---|---|---|
| context chunks per request | 5 | 5–14 (homeowners: 5 searched + up to 9 schedule rows) | +up to 9 |
| tokens per request, p50 | 2,115 | 3,787 | **+79%** |
| cost per request, p50 | $0.000491 | $0.000740 | **+51%** |
| the drill input itself | 2,164 tok · $0.000498 | 4,500 tok · $0.000830 | +67% cost |

All of the increase is generation input tokens: the attached exclusions schedule. Retrieval and tools stay at $0.
Sources: `week11/trace.json`, `evals/w11/runs/red-before-fix.json`, `evals/w11/runs/green-after-fix.json`.
