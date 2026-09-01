"""Shared shapes: chunk metadata contract + API request/response bodies."""
from typing import Literal

from pydantic import BaseModel, Field

# Requirement 1: a chunk missing any of these is a FAILED ingest.
REQUIRED_METADATA = ("source_file", "form_number", "policy_line", "edition_date")

Strategy = Literal["current", "structure_aware"]
Retriever = Literal["dense", "hybrid"]


class ChunkMeta(BaseModel):
    source_file: str
    form_number: str
    policy_line: str
    edition_date: str
    clause: str = ""
    strategy: str = ""
    chunk_id: str = ""
    exclusion_code: str | None = None


class Chunk(BaseModel):
    text: str
    metadata: ChunkMeta


class SearchRequest(BaseModel):
    query: str
    strategy: Strategy = "structure_aware"
    k: int = 5
    policy_line: str | None = None
    form_number: str | None = None
    retriever: Retriever = "dense"


class InspectRequest(BaseModel):
    """Drives the inspection view. `answers=True` costs an LLM call per
    question — it is what makes a G label decidable rather than assumed."""

    retriever: Retriever = "dense"
    strategy: Strategy = "structure_aware"
    k: int = 3
    answers: bool = False


class SearchHit(BaseModel):
    rank: int
    chunk_id: str
    score: float = Field(description="cosine for dense, RRF score for hybrid — see score_kind")
    score_kind: str = "cosine"
    dense_rank: int | None = None
    bm25_rank: int | None = None
    form_number: str
    edition_date: str
    policy_line: str
    clause: str
    source_file: str
    text: str


class AskRequest(BaseModel):
    question: str
    strategy: Strategy = "structure_aware"
    retriever: Retriever = "hybrid"   # the shipped one — see results.md §7
