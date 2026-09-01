"""Search-only retrieval. The hit-rate numbers must come from retrieval alone,
so this path never touches an LLM.

    python -m app.retrieval.search "does E-17 apply to a burst supply line?"
    python -m app.retrieval.search "..." --policy-line homeowners
    python -m app.retrieval.search "..." --retriever hybrid   # Week 4's one change

`retriever` is the ONE variable Week 4 moves:
  dense  — Chroma cosine only. The Week 3 retriever, untouched.
  hybrid — dense + BM25 over the same chunks, fused with RRF (k=60).
"""
import argparse
import json

from .. import config
from .store import get_collection


def build_where(policy_line: str | None, form_number: str | None) -> dict | None:
    filters = {}
    if policy_line:
        filters["policy_line"] = policy_line
    if form_number:
        filters["form_number"] = form_number
    # Chroma takes a single clause, or an explicit $and for more than one
    return filters if len(filters) <= 1 else {"$and": [{k_: v} for k_, v in filters.items()]}


def search(
    query: str,
    strategy: str = "structure_aware",
    k: int = config.TOP_K,
    policy_line: str | None = None,
    form_number: str | None = None,
    retriever: str = "dense",
) -> list[dict]:
    """`score` is cosine similarity for `dense`, the RRF score for `hybrid` —
    the two are NOT comparable, which is why `score_kind` travels with it."""
    where = build_where(policy_line, form_number)

    if retriever == "hybrid":
        from .hybrid import hybrid_search  # local: dense path must stay import-clean

        return hybrid_search(query, strategy, k, where or None)
    if retriever != "dense":
        raise ValueError(f"unknown retriever {retriever!r}; expected one of {config.RETRIEVERS}")

    col = get_collection(strategy)
    res = col.query(
        query_texts=[query],
        n_results=k,
        where=where or None,
        include=["documents", "metadatas", "distances"],
    )

    return [
        {
            "rank": i + 1,
            "chunk_id": meta["chunk_id"],
            "score": round(1 - dist, 4),
            "score_kind": "cosine",
            "form_number": meta["form_number"],
            "edition_date": meta["edition_date"],
            "policy_line": meta["policy_line"],
            "clause": meta.get("clause", ""),
            "source_file": meta["source_file"],
            "text": doc,
        }
        for i, (doc, meta, dist) in enumerate(
            zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
        )
    ]


def get_chunk(chunk_id: str, strategy: str) -> dict | None:
    """Resolve a citation back to its chunk — the grader will check one."""
    col = get_collection(strategy)
    res = col.get(ids=[chunk_id], include=["documents", "metadatas"])
    if not res["ids"]:
        return None
    return {"chunk_id": chunk_id, "text": res["documents"][0], **res["metadatas"][0]}


def format_results(results: list[dict], width: int = 160) -> str:
    lines = []
    for r in results:
        snippet = " ".join(r["text"].split())[:width]
        arms = ""
        if r.get("score_kind") == "rrf":
            arms = f"  (dense #{r.get('dense_rank') or '-'} · bm25 #{r.get('bm25_rank') or '-'})"
        lines.append(
            f"  {r['rank']}. {r.get('score_kind', 'cosine')}={r['score']:.4f}{arms}  "
            f"{r['form_number']} ed.{r['edition_date']} [{r['policy_line']}]  {r['clause']}\n"
            f"     chunk_id={r['chunk_id']}\n"
            f"     {snippet}…"
        )
    return "\n".join(lines) or "  (no results)"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--strategy", choices=config.STRATEGIES, default="structure_aware")
    ap.add_argument("--k", type=int, default=config.TOP_K)
    ap.add_argument("--policy-line", default=None)
    ap.add_argument("--form-number", default=None)
    ap.add_argument("--retriever", choices=config.RETRIEVERS, default="dense")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    hits = search(a.query, a.strategy, a.k, a.policy_line, a.form_number, a.retriever)
    if a.json:
        print(json.dumps(hits, indent=2))
    else:
        filt = f" filter(policy_line={a.policy_line})" if a.policy_line else " unfiltered"
        print(f"[{a.strategy} · {a.retriever}]{filt}  {a.query!r}")
        print(format_results(hits))
