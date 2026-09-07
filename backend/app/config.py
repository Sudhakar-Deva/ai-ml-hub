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

# Week 5: the trace log, the traffic that produced it, and the open coding.
TRACES_DIR = ROOT / "traces"
TRACE_FILE = TRACES_DIR / "traces.jsonl"
TRAFFIC_DIR = EVALS_DIR / "traffic"
WEEK5_DIR = ROOT / "week5"
CODING_FILE = WEEK5_DIR / "open_coding.jsonl"
SAMPLE_FILE = WEEK5_DIR / "sample.json"

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

# --- Week 5 · error analysis -------------------------------------------------
# The sample is random, and the seed is published so anyone can redraw the exact
# same 20 traces. A sample nobody can reproduce is an anecdote with a count.
SAMPLE_SEED = 20260907
SAMPLE_SIZE = 20
DEMO_SAMPLE_SIZE = 10   # bonus: the curated set shown at the monthly review

# Bumped whenever SYSTEM or PROMPT in generation/answer.py changes. A trace
# without this cannot be replayed — you would be replaying today's prompt
# against last week's output and calling the difference a regression.
PROMPT_VERSION = "claims-grounded-v1"


def collection_name(strategy: str) -> str:
    return f"endorsements_{strategy}"
