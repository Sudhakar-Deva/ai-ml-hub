"""Ingest the 6 NEW endorsements only — do not re-index the whole wording
library. The ingest is plumbing; the measurement is the deliverable.

    python -m app.ingestion.ingest --strategy current --reset
    python -m app.ingestion.ingest --strategy structure_aware --reset
"""
import argparse

from .. import config
from ..chunking import CHUNKERS
from ..models.schemas import REQUIRED_METADATA
from ..retrieval.store import get_collection
from .loader import load_all


OPEN_ENDED = 99991231


def effective_windows(docs) -> dict[str, tuple[int, int]]:
    """An edition is in force from its Effective date to the day before the NEXT
    edition of the same form took effect (open-ended for the latest edition)."""
    from datetime import date, timedelta

    out = {}
    by_form: dict[str, list] = {}
    for d in docs:
        by_form.setdefault(d.form_number, []).append(d)
    for eds in by_form.values():
        eds.sort(key=lambda d: d.effective_from)
        for cur, nxt in zip(eds, eds[1:] + [None]):
            end = OPEN_ENDED
            if nxt is not None:
                n = str(nxt.effective_from)
                end = int((date(int(n[:4]), int(n[4:6]), int(n[6:])) - timedelta(days=1)).strftime("%Y%m%d"))
            out[cur.source_file] = (cur.effective_from, end)
    return out


def ingest(strategy: str, reset: bool = True) -> dict:
    docs = load_all(config.DOCS_DIR)
    chunk_fn = CHUNKERS[strategy]
    windows = effective_windows(docs)

    chunks = []
    for doc in docs:
        for c in chunk_fn(doc):
            # Week 12: every chunk carries the window its edition was in force,
            # [effective_from, effective_to], so a loss date can filter it in code.
            c["metadata"]["effective_from"], c["metadata"]["effective_to"] = windows[doc.source_file]
            chunks.append(c)

    # A chunk with no source_file is a FAILED ingest. Hard stop, not a warning —
    # a silently unattributed chunk cannot be cited later.
    bad = [c for c in chunks if not all(c["metadata"].get(f) for f in REQUIRED_METADATA)]
    if bad:
        raise SystemExit(
            f"FAILED INGEST: {len(bad)}/{len(chunks)} chunks missing required metadata. "
            f"First offender: {bad[0]['metadata']}"
        )

    col = get_collection(strategy, reset=reset)
    col.add(
        ids=[c["metadata"]["chunk_id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )

    stats = {
        "strategy": strategy,
        "documents": len(docs),
        "chunks": len(chunks),
        "avg_chars": round(sum(len(c["text"]) for c in chunks) / len(chunks)),
        "forms": sorted({d.form_number for d in docs}),
        "policy_lines": sorted({d.policy_line for d in docs}),
    }
    print(stats)
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", choices=config.STRATEGIES, required=True)
    ap.add_argument("--reset", action="store_true", help="drop and rebuild this collection")
    a = ap.parse_args()
    ingest(a.strategy, reset=a.reset)
