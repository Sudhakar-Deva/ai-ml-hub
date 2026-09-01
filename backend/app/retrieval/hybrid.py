"""Hybrid retrieval — dense + BM25 fused with RRF. This is the ONE change.

RRF fuses RANKS, never scores:

    rrf(chunk) = Σ over arms of  1 / (k + rank_in_that_arm)

A cosine similarity lives in roughly [0.2, 0.8] and a BM25 score is unbounded
and corpus-dependent — adding or averaging them lets whichever arm happens to
have the larger numbers decide every query. Rank is the only thing the two arms
report on a shared scale, which is exactly why RRF uses it. k=60 is the constant
from the original Cormack et al. formulation: large enough that no single arm's
#1 can dominate outright, small enough that the top of each list still matters.
"""
from .. import config
from .lexical import lexical_search
from .store import get_collection


def rrf_fuse(rankings: list[list[str]], k: int = config.RRF_K) -> list[tuple[str, float]]:
    """[[chunk_id ordered by arm 1], [ordered by arm 2], …] -> fused order."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])


def _dense_candidates(
    query: str,
    strategy: str,
    n: int,
    where: dict | None,
) -> list[dict]:
    col = get_collection(strategy)
    res = col.query(
        query_texts=[query],
        n_results=min(n, col.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    return [
        {"chunk_id": m["chunk_id"], "cosine": round(1 - d, 4), "text": doc, "meta": m}
        for doc, m, d in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


def hybrid_search(
    query: str,
    strategy: str,
    k: int,
    where: dict | None = None,
    candidate_k: int = config.CANDIDATE_K,
    rrf_k: int = config.RRF_K,
) -> list[dict]:
    dense = _dense_candidates(query, strategy, candidate_k, where)

    # The lexical arm must see the same filtered universe as the dense arm, or
    # the filter would silently apply to half the pipeline.
    allowed = None
    if where:
        col = get_collection(strategy)
        allowed = set(col.get(where=where, include=[])["ids"])
    lexical = lexical_search(query, strategy, candidate_k, allowed)

    dense_rank = {h["chunk_id"]: i + 1 for i, h in enumerate(dense)}
    lex_rank = {h["chunk_id"]: i + 1 for i, h in enumerate(lexical)}
    fused = rrf_fuse([list(dense_rank), list(lex_rank)], k=rrf_k)

    by_id = {h["chunk_id"]: h for h in dense}
    for h in lexical:  # BM25-only candidates carry no cosine
        by_id.setdefault(
            h["chunk_id"],
            {"chunk_id": h["chunk_id"], "cosine": None, "text": h["text"], "meta": h},
        )

    out = []
    for rank, (chunk_id, score) in enumerate(fused[:k], start=1):
        c = by_id[chunk_id]
        m = c["meta"]
        out.append(
            {
                "rank": rank,
                "chunk_id": chunk_id,
                "score": round(score, 6),
                "score_kind": "rrf",
                "dense_rank": dense_rank.get(chunk_id),
                "bm25_rank": lex_rank.get(chunk_id),
                "cosine": c["cosine"],
                "form_number": m.get("form_number", ""),
                "edition_date": m.get("edition_date", ""),
                "policy_line": m.get("policy_line", ""),
                "clause": m.get("clause", ""),
                "source_file": m.get("source_file", ""),
                "text": c["text"],
            }
        )
    return out


def fused_candidates(
    query: str,
    strategy: str,
    where: dict | None = None,
    candidate_k: int = config.CANDIDATE_K,
) -> list[dict]:
    """The full fused candidate list — what MMR reorders in the bonus."""
    return hybrid_search(query, strategy, candidate_k, where, candidate_k)
