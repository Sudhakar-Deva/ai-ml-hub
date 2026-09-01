"""Bonus — MMR over the FUSED candidate list.

The E-17 query comes back as the same exclusion text repeated across three form
editions: HO-0304's E-17 row, DP-0110's E-17 row, and the HO-0304 chunk whose
table header carries the E-17 row along with it. Three slots, one fact.

MMR trades a little relevance for a little variety:

    mmr(d) = λ · rel(d) − (1 − λ) · max sim(d, already selected)

`rel` here is the RRF score of the fused list, min-max normalised so it shares
a scale with the cosine similarity term. That is a normalisation for a
comparison INSIDE one formula, not a fusion of two rankings — fusion still
happens on ranks upstream, in hybrid.rrf_fuse.

The honest risk, and the thing the bonus asks about: nothing in MMR knows which
edition the adjuster meant. Pushing DP-0110's E-17 out for diversity is a win;
pushing HO-0304's E-17 out is the failure the whole week is about.
"""
import math

from .. import config
from .hybrid import fused_candidates
from .store import get_collection


def _embeddings(chunk_ids: list[str], strategy: str) -> dict[str, list[float]]:
    res = get_collection(strategy).get(ids=chunk_ids, include=["embeddings"])
    return dict(zip(res["ids"], [list(e) for e in res["embeddings"]]))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def mmr_rerank(candidates: list[dict], strategy: str, k: int, lambda_: float) -> list[dict]:
    if len(candidates) <= 1:
        return candidates[:k]

    emb = _embeddings([c["chunk_id"] for c in candidates], strategy)
    scores = [c["score"] for c in candidates]
    lo, hi = min(scores), max(scores)
    span = (hi - lo) or 1.0
    rel = {c["chunk_id"]: (c["score"] - lo) / span for c in candidates}

    pool = list(candidates)
    selected: list[dict] = []
    while pool and len(selected) < k:
        best, best_val = None, -float("inf")
        for c in pool:
            penalty = max(
                (_cosine(emb[c["chunk_id"]], emb[s["chunk_id"]]) for s in selected),
                default=0.0,
            )
            val = lambda_ * rel[c["chunk_id"]] - (1 - lambda_) * penalty
            if val > best_val:
                best, best_val = c, val
        pool.remove(best)
        selected.append({**best, "mmr_score": round(best_val, 6), "rrf_rank": best["rank"]})

    for i, c in enumerate(selected, start=1):
        c["rank"] = i
        c["score_kind"] = f"mmr(λ={lambda_})"
        c["score"] = c["mmr_score"]
    return selected


def mmr_search(
    query: str,
    strategy: str = config.BASELINE_STRATEGY,
    k: int = config.EVAL_K,
    lambda_: float = config.MMR_LAMBDA,
    where: dict | None = None,
) -> list[dict]:
    return mmr_rerank(fused_candidates(query, strategy, where), strategy, k, lambda_)


def top_k_diversity(hits: list[dict]) -> dict:
    """How much of the top-k is actually distinct — the number the bonus wants
    alongside hit-rate, because 'three copies of the same clause' and 'three
    different clauses' both look like a full top-3 otherwise."""
    forms = {h["form_number"] for h in hits}
    clauses = {(h["form_number"], h["clause"]) for h in hits}
    return {
        "distinct_forms": len(forms),
        "distinct_clauses": len(clauses),
        "forms": sorted(forms),
    }


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--strategy", choices=config.STRATEGIES, default=config.BASELINE_STRATEGY)
    ap.add_argument("--k", type=int, default=config.EVAL_K)
    ap.add_argument("--lambda", dest="lambda_", type=float, default=config.MMR_LAMBDA)
    a = ap.parse_args()

    hits = mmr_search(a.query, a.strategy, a.k, a.lambda_)
    print(json.dumps({"hits": hits, "diversity": top_k_diversity(hits)}, indent=2))
