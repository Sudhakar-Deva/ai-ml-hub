"""Shared helpers both chunkers use, so the ONLY difference between them is
the splitting policy — not the metadata they attach."""
from ..ingestion.loader import Document


def chunk_id(doc: Document, strategy: str, idx: int) -> str:
    """Stable and resolvable — citations are checked against this."""
    return f"{strategy}:{doc.form_number}:{doc.source_file}:{idx:04d}"


def pack(doc: Document, strategy: str, idx: int, text: str, clause: str) -> dict:
    return {
        "text": text.strip(),
        "metadata": {
            **doc.metadata(),
            "clause": clause,
            "strategy": strategy,
            "chunk_id": chunk_id(doc, strategy, idx),
        },
    }
