"""Week 4's number: hit-rate@3 over the 12-question golden set, with the p50
latency it cost, per retriever.

    python -m app.retrieval.hitrate --retrievers dense              # baseline, before
    python -m app.retrieval.hitrate --retrievers dense hybrid --markdown
    python -m app.retrieval.hitrate --retrievers hybrid --mmr --lambda 0.6   # bonus

A HIT is the gold chunk_id itself appearing in the top-3. Not the right form,
not an adjacent clause — the chunk the answer actually lives in. A looser rule
would let 'returned three water-damage clauses, none of them E-17' score as a
pass, which is the exact failure this week is about.

Latency is measured per query around the retrieval call only (no LLM), after a
warm-up query that pays the one-time embedding-model load and BM25 index build.
Those are startup costs, not per-query costs, and folding them into the p50
would flatter the baseline and slander the change.
"""
import argparse
import json
import statistics
import time
from datetime import datetime, timezone

from .. import config
from .search import search


def load_golden_set() -> list[dict]:
    rows = [
        json.loads(line)
        for line in config.GOLDEN_SET_FILE.read_text().splitlines()
        if line.strip()
    ]
    questions = [r for r in rows if "_comment" not in r]
    if len(questions) != 12:
        raise SystemExit(f"Golden set must hold exactly 12 questions, found {len(questions)}")
    missing = [q["id"] for q in questions if not q.get("gold_chunk_id")]
    if missing:
        raise SystemExit(f"No gold chunk_id recorded for: {missing}")
    return questions


def redundancy(hits: list[dict], strategy: str) -> float:
    """Mean pairwise cosine between the retrieved chunks. High means the top-3
    is the same clause wearing three hats — a full top-3 that carries one fact.
    This is the diversity number the MMR bonus moves."""
    if len(hits) < 2:
        return 0.0
    from .mmr import _cosine, _embeddings

    emb = _embeddings([h["chunk_id"] for h in hits], strategy)
    ids = [h["chunk_id"] for h in hits]
    pairs = [
        _cosine(emb[a], emb[b])
        for i, a in enumerate(ids)
        for b in ids[i + 1 :]
    ]
    return round(statistics.mean(pairs), 4)


def run(
    retriever: str,
    questions: list[dict],
    strategy: str = config.BASELINE_STRATEGY,
    k: int = config.EVAL_K,
    mmr: bool = False,
    mmr_lambda: float = config.MMR_LAMBDA,
    repeats: int = 5,
) -> dict:
    def retrieve(q: str) -> list[dict]:
        if mmr:
            from .mmr import mmr_search

            return mmr_search(q, strategy, k, lambda_=mmr_lambda)
        return search(q, strategy, k, retriever=retriever)

    # The BM25 index is built once per process. Timed here and reported on its
    # own rather than smeared across the per-query p50, where it would read as
    # a 40x latency regression that no user ever pays.
    index_build_ms = None
    if retriever == "hybrid" or mmr:
        from .lexical import build
        from .store import get_collection

        get_collection(strategy).count()  # pay the client/embedder load first, off the clock
        t = time.perf_counter()
        build(strategy, force=True)
        index_build_ms = round((time.perf_counter() - t) * 1000, 1)

    retrieve(questions[0]["question"])  # warm-up: embedding model load, not per-query cost

    records, latencies = [], []
    for q in questions:
        # p50 over repeats × questions — at 12 queries a single sample per
        # question puts the whole before/after latency claim inside the noise.
        samples = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            hits = retrieve(q["question"])
            samples.append((time.perf_counter() - t0) * 1000)
        latencies.extend(samples)
        latency_ms = statistics.median(samples)

        ranks = [h["rank"] for h in hits if h["chunk_id"] == q["gold_chunk_id"]]
        records.append(
            {
                "id": q["id"],
                "question": q["question"],
                "exact_token": q.get("exact_token", False),
                "gold_chunk_id": q["gold_chunk_id"],
                "hit": bool(ranks),
                "hit_rank": ranks[0] if ranks else None,
                "latency_ms": round(latency_ms, 1),
                "distinct_forms": len({h["form_number"] for h in hits}),
                "redundancy": redundancy(hits, strategy),
                "top_k": [
                    {
                        "rank": h["rank"],
                        "chunk_id": h["chunk_id"],
                        "score": h["score"],
                        "score_kind": h.get("score_kind", "cosine"),
                        "dense_rank": h.get("dense_rank"),
                        "bm25_rank": h.get("bm25_rank"),
                        "form_number": h["form_number"],
                        "clause": h["clause"],
                        "is_gold": h["chunk_id"] == q["gold_chunk_id"],
                        "snippet": " ".join(h["text"].split())[:200],
                    }
                    for h in hits
                ],
            }
        )

    hits_n = sum(r["hit"] for r in records)
    return {
        "retriever": f"{retriever}+mmr(λ={mmr_lambda})" if mmr else retriever,
        "strategy": strategy,
        "embed_model": config.EMBEDDING_MODEL,
        "k": k,
        "candidate_k": config.CANDIDATE_K if retriever == "hybrid" else None,
        "rrf_k": config.RRF_K if retriever == "hybrid" else None,
        "hits": hits_n,
        "total": len(records),
        "hit_rate_at_k": round(hits_n / len(records), 4),
        # Bonus: 'three copies of the same clause' and 'three different clauses'
        # both fill a top-3, so diversity is reported next to the hit-rate.
        "mean_distinct_forms": round(statistics.mean(r["distinct_forms"] for r in records), 2),
        "mean_redundancy": round(statistics.mean(r["redundancy"] for r in records), 4),
        "index_build_ms": index_build_ms,
        "repeats_per_question": repeats,
        "p50_latency_ms": round(statistics.median(latencies), 1),
        "p95_latency_ms": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 1),
        "mean_latency_ms": round(statistics.mean(latencies), 1),
        "records": records,
    }


def markdown_report(runs: list[dict]) -> str:
    names = [r["retriever"] for r in runs]
    lines = [
        "| # | Question | exact token? | " + " | ".join(names) + " |",
        "| - | -------- | ------------ | " + " | ".join("---" for _ in names) + " |",
    ]
    for i, rec in enumerate(runs[0]["records"]):
        cells = [
            (f"✅ #{r['records'][i]['hit_rank']}" if r["records"][i]["hit"] else "❌ miss")
            for r in runs
        ]
        q = rec["question"][:78] + ("…" if len(rec["question"]) > 78 else "")
        lines.append(
            f"| {rec['id']} | {q} | {'yes' if rec['exact_token'] else 'no'} | "
            + " | ".join(cells)
            + " |"
        )

    lines += [
        "",
        "| Retriever | hit-rate@3 | p50 latency | p95 latency | index build (one-time) | "
        "mean distinct forms in top-3 | mean pairwise cosine in top-3 |",
        "| --------- | ---------- | ----------- | ----------- | --------------------- | "
        "---------------------------- | ----------------------------- |",
    ]
    for r in runs:
        build = f"{r['index_build_ms']} ms" if r["index_build_ms"] is not None else "—"
        lines.append(
            f"| `{r['retriever']}` | **{r['hits']}/{r['total']}** ({r['hit_rate_at_k']:.0%}) | "
            f"{r['p50_latency_ms']} ms | {r['p95_latency_ms']} ms | {build} | "
            f"{r['mean_distinct_forms']} | {r['mean_redundancy']} |"
        )
    lines += [
        "",
        f"_Same 12 questions, same chunker (`{runs[0]['strategy']}`), same embedding model "
        f"(`{runs[0]['embed_model']}`), k={runs[0]['k']}. The only variable changed is the retriever._",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrievers", nargs="+", default=["dense"], choices=list(config.RETRIEVERS))
    ap.add_argument("--strategy", choices=config.STRATEGIES, default=config.BASELINE_STRATEGY)
    ap.add_argument("--k", type=int, default=config.EVAL_K)
    ap.add_argument("--mmr", action="store_true", help="bonus: MMR over the fused candidates")
    ap.add_argument("--lambda", dest="lambda_", type=float, default=config.MMR_LAMBDA)
    ap.add_argument("--repeats", type=int, default=5, help="latency samples per question")
    ap.add_argument("--markdown", action="store_true")
    a = ap.parse_args()

    questions = load_golden_set()
    runs = [
        run(r, questions, a.strategy, a.k, a.mmr, a.lambda_, a.repeats) for r in a.retrievers
    ]

    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for r in runs:
        name = r["retriever"].replace("+", "_").replace("(", "").replace(")", "").replace("λ=", "l")
        path = config.RUNS_DIR / f"{name}_{stamp}.json"
        path.write_text(json.dumps(r, indent=2))
        print(
            f"{r['retriever']}: hit-rate@{r['k']} = {r['hits']}/{r['total']} "
            f"({r['hit_rate_at_k']:.0%})  p50={r['p50_latency_ms']}ms  ->  "
            f"{path.relative_to(config.ROOT)}"
        )

    if a.markdown:
        md = markdown_report(runs)
        (config.RUNS_DIR / f"hitrate_{stamp}.md").write_text(md)
        print("\n" + md)
