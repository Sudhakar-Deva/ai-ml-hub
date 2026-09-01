"""Single place for every knob.

Change ONE thing per run — never the chunker and the embedding model together,
or the number you report tells you nothing about which one moved it.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]   # repo root (app/ -> backend/ -> repo)
BACKEND = ROOT / "backend"
load_dotenv(ROOT / ".env")

DOCS_DIR = ROOT / "data" / "endorsements"
EVALS_DIR = ROOT / "evals"
QUESTIONS_FILE = EVALS_DIR / "questions.json"
EXPECTED_FILE = EVALS_DIR / "expected.json"
DUMPS_DIR = EVALS_DIR / "search-dumps"

# Week 4: the 12-question golden set and the before/after runs it produces.
GOLDEN_SET_FILE = EVALS_DIR / "golden_set.jsonl"
RUNS_DIR = EVALS_DIR / "w4-runs"
LABELS_FILE = EVALS_DIR / "failure_labels.json"

VECTOR_DB_PATH = ROOT / os.getenv("VECTOR_DB_PATH", "backend/.chroma")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))

TOP_K = 5  # Week 3: hit-in-top-5 is the metric; keep fixed across strategies

STRATEGIES = ("current", "structure_aware")

# --- Week 4 · retrieval debugging -------------------------------------------
# The ONE variable that changes between the before and the after run is
# `retriever`. Everything below it is held fixed across both runs.
EVAL_K = 3                       # hit-rate@3 — the Week 4 metric
BASELINE_STRATEGY = "structure_aware"   # Week 3's winner is what Week 4 starts from
RETRIEVERS = ("dense", "hybrid")
# What the app answers with. Moved to "hybrid" on the strength of §5/§7 of
# results.md (8/12 -> 11/12 for +1.3 ms p50). The eval harness always passes an
# explicit retriever, so no measured number depends on this default.
SHIPPED_RETRIEVER = "hybrid"

CANDIDATE_K = 25   # depth each arm contributes to the fusion
RRF_K = 60         # Reciprocal Rank Fusion constant: 1 / (RRF_K + rank)
MMR_LAMBDA = 0.7   # bonus only — 1.0 is pure relevance, 0.0 pure diversity


def collection_name(strategy: str) -> str:
    return f"endorsements_{strategy}"
