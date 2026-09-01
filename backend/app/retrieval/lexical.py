"""BM25 arm — the half of hybrid search that can actually see 'E-17'.

A dense embedding of 'E-17' and an embedding of 'E-19' land ~0.02 apart: the
model encodes "an exclusion code about water" and throws away the digits, which
are the entire question. BM25 scores the literal token, so a code, a form
number, or an edition date is a high-IDF term instead of noise.

The index is built from the SAME chunks that are already in the Chroma
collection — not a second corpus — so the only thing that differs between the
dense arm and the lexical arm is how a chunk is scored, never which chunks exist.
"""
import re

from rank_bm25 import BM25Okapi

from .store import get_collection

# Keep hyphenated identifiers whole: e-17, ho-0304, 03-24, dp-0110.
# A tokenizer that splits on '-' turns E-17 into ('e', '17') and hands '17' the
# same weight as any other stray number — the exact failure this arm exists to fix.
TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-/][a-z0-9]+)*")

_indexes: dict[str, "LexicalIndex"] = {}


def tokenize(text: str) -> list[str]:
    tokens = TOKEN_RE.findall(text.lower())
    # Also index the parts of a hyphenated code, so 'HO 0304' still finds 'ho-0304'.
    extra = [p for t in tokens if "-" in t or "/" in t for p in re.split(r"[-/]", t) if p]
    return tokens + extra


class LexicalIndex:
    """BM25 over one strategy's chunks. Built once per process, then reused."""

    def __init__(self, strategy: str):
        col = get_collection(strategy)
        raw = col.get(include=["documents", "metadatas"])
        order = sorted(range(len(raw["ids"])), key=lambda i: raw["ids"][i])

        self.strategy = strategy
        self.chunk_ids = [raw["ids"][i] for i in order]
        self.documents = [raw["documents"][i] for i in order]
        self.metadatas = [raw["metadatas"][i] for i in order]
        self.bm25 = BM25Okapi([tokenize(d) for d in self.documents])

    def __len__(self) -> int:
        return len(self.chunk_ids)

    def rank(self, query: str, k: int, allowed: set[str] | None = None) -> list[dict]:
        """Top-k by BM25. `allowed` applies the same metadata filter the dense
        arm gets, so a filtered hybrid run stays a fair comparison."""
        scores = self.bm25.get_scores(tokenize(query))
        idxs = sorted(range(len(scores)), key=lambda i: -scores[i])
        out = []
        for i in idxs:
            if allowed is not None and self.chunk_ids[i] not in allowed:
                continue
            if scores[i] <= 0:  # no query term present — not a candidate, just noise
                break
            out.append(
                {
                    "rank": len(out) + 1,
                    "chunk_id": self.chunk_ids[i],
                    "score": round(float(scores[i]), 4),
                    "text": self.documents[i],
                    **{
                        f: self.metadatas[i].get(f, "")
                        for f in ("form_number", "edition_date", "policy_line", "clause", "source_file")
                    },
                }
            )
            if len(out) >= k:
                break
        return out


def build(strategy: str, force: bool = False) -> LexicalIndex:
    """Build (or rebuild) the index. `force` exists so the harness can time the
    one-time build cost honestly instead of hiding it in the first query."""
    if force or strategy not in _indexes:
        _indexes[strategy] = LexicalIndex(strategy)
    return _indexes[strategy]


def index(strategy: str) -> LexicalIndex:
    return build(strategy)


def lexical_search(query: str, strategy: str, k: int, allowed: set[str] | None = None) -> list[dict]:
    return index(strategy).rank(query, k, allowed)
