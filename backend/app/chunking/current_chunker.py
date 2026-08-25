"""Strategy A — the chunker the app already had.

Fixed-size character window with overlap. Structure-blind on purpose: this is
what splits exclusion row E-17 away from its table header and form number.
That split is the failure the measurement is meant to expose. Do not "improve"
it — it is the control.
"""
from ..ingestion.loader import Document
from .common import pack

STRATEGY = "current"


def chunk(doc: Document, size: int = 1000, overlap: int = 150) -> list[dict]:
    text = doc.text
    out, idx, start = [], 0, 0
    step = size - overlap
    while start < len(text):
        window = text[start : start + size]
        if window.strip():
            out.append(pack(doc, STRATEGY, idx, window, clause="n/a"))
            idx += 1
        start += step
    return out
