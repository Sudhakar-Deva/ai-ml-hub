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


# --- Week 6 · evals -----------------------------------------------------------
# The claim-summary path is a SECOND prompt with its own version. Week 5's
# question-answering prompt is untouched: mixing the two would make every Week 5
# trace unreplayable and every Week 6 number un-attributable.
SUMMARY_PROMPT_VERSION = "claims-summary-v1"

WEEK6_DIR = ROOT / "week6"
W6_DIR = EVALS_DIR / "w6"
W6_CASES_FILE = W6_DIR / "eval_set.jsonl"
W6_SUMMARIES_FILE = W6_DIR / "summaries.json"
W6_LABELS_FILE = W6_DIR / "labels_25.json"
W6_RUNS_DIR = W6_DIR / "runs"
JUDGE_DIR = W6_DIR / "judges"

# The judge reads a prompt FILE, never a string in the source. Two reasons: the
# v1 -> v2 change has to be diffable by the grader, and a prompt edited in code
# is a prompt whose version nobody can name afterwards.
JUDGE_VERSIONS = ("v0", "v1", "v2")
JUDGE_DEFAULT = "v1"

# The judge is a different model call from the app's. Same model family is fine;
# what is not fine is the judge silently inheriting a change made for the app.
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude-sonnet-5")
JUDGE_PARAMS = {"temperature": 0, "max_tokens": 512}

# How many summaries get hand-labelled. The brief says 25 and the number is
# load-bearing: it is the whole basis of the agreement figure.
LABEL_N = 25


# --- Week 7 · agent vs fixed workflow ----------------------------------------
# Both systems run on the SAME model, the SAME tools and the SAME output
# contract. The only variable in the race is who decides the next step: the
# model (agent) or the code (workflow).
WEEK7_DIR = ROOT / "week7"
W7_DIR = EVALS_DIR / "w7"
W7_CLAIMS_FILE = W7_DIR / "claims.jsonl"
W7_RUNS_DIR = W7_DIR / "runs"
W7_RACE_FILE = W7_DIR / "race.csv"
W7_RACE_CLAIMS_FILE = W7_DIR / "race_claims.csv"
W7_LOGS_DIR = WEEK7_DIR / "logs"
TOOLS_V1_FILE = WEEK7_DIR / "tools_v1.json"   # the two-tool loop as it shipped
TOOLS_V2_FILE = WEEK7_DIR / "tools_v2.json"   # sharpened + the third tool

AGENT_MODEL = os.getenv("AGENT_MODEL", LLM_MODEL)
AGENT_MAX_TOKENS_PER_CALL = 4096

# The four budgets. Every one of them is checked inside the loop — see
# app/agents/budget.py. A budget that is only a constant is a comment.
MAX_ITERS = int(os.getenv("AGENT_MAX_ITERS", "8"))
MAX_TOKENS = int(os.getenv("AGENT_MAX_TOKENS", "60000"))      # summed over EVERY lap
MAX_COST_USD = float(os.getenv("AGENT_MAX_COST_USD", "0.25"))
WALL_CLOCK_S = float(os.getenv("AGENT_WALL_CLOCK_S", "90"))

# USD per 1M tokens (input, output), Anthropic first-party list price.
PRICING = {
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
