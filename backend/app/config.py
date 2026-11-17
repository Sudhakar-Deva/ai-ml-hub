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

# "groq" (default) or "anthropic". All model calls go through app/llm.py, so this
# one value switches every call site. Never switch it between a before and an
# after run — the provider is part of the model.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
_DEFAULT_MODEL = {"groq": "openai/gpt-oss-120b", "anthropic": "claude-sonnet-5"}[LLM_PROVIDER]
LLM_MODEL = os.getenv("LLM_MODEL", _DEFAULT_MODEL)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
# Groq's gpt-oss models reason before answering, and those tokens count against
# max_tokens. Pinned so every call (and every trace) uses the same setting.
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low" if LLM_PROVIDER == "groq" else "")

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
# v1 -> v2 (Week 11, 2026-11-16): retrieval filtered to the notes' policy line + that
# line's full exclusions schedule attached. Fixes the drill case w11-011 (COVERED over
# HO-0304 E-22). System prompt text unchanged; the rendered prompt's context changed,
# so the version moves. Canary/rollback: week11/canary_rollback.md.
SUMMARY_PROMPT_VERSION = "claims-summary-v2"

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
JUDGE_MODEL = os.getenv("JUDGE_MODEL", _DEFAULT_MODEL)
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

# USD per 1M tokens (input, output), provider list price. The Groq figures are
# overridable from .env (GROQ_PRICE_IN / GROQ_PRICE_OUT) — CHECK THEM against
# https://groq.com/pricing before reporting cost per claim; a wrong price here
# makes the Week 7 cost column wrong for both systems.
PRICING = {
    "openai/gpt-oss-120b": (float(os.getenv("GROQ_PRICE_IN", "0.15")), float(os.getenv("GROQ_PRICE_OUT", "0.60"))),
    # Week 12: Groq's listed price for gpt-oss-20b (check https://groq.com/pricing).
    "openai/gpt-oss-20b": (float(os.getenv("GROQ_20B_PRICE_IN", "0.075")), float(os.getenv("GROQ_20B_PRICE_OUT", "0.30"))),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


# --- Week 8 · trajectory evals ------------------------------------------------
# The outcome eval (contract.grade) scores WHAT the agent answered; the trajectory
# eval scores HOW it got there. Same 10 claims as Week 7, same model, same budgets
# — except wall-clock, raised for the eval only: on Groq's free tier (8k tokens a
# minute) a 10k-token run spends most of 90 s asleep on 429s, and a budget that
# fires on the provider's rate limit would be scored as the agent's failure. The
# sleep is measured and subtracted from reported latency (llm.rate_limit_wait_s).
WEEK8_DIR = ROOT / "week8"
W8_DIR = EVALS_DIR / "w8"
W8_RUNS_DIR = W8_DIR / "runs"
W8_WALL_CLOCK_S = float(os.getenv("W8_WALL_CLOCK_S", "400"))


# --- Week 9 · MCP ----------------------------------------------------------------
# The host agent (app/mcphost/agent.py) reads its servers from THIS file and its
# tools from each server's tools/list. Adding a server is an edit here, never in
# the agent module.
WEEK9_DIR = ROOT / "week9"
MCP_CONFIG_FILE = Path(os.getenv("MCP_CONFIG_FILE", str(ROOT / "mcp_servers.json")))


# --- Week 10 · single agent vs squad ----------------------------------------------
# Runs land in evals/w10/runs/ (gitignored like every runs/ dir); the deliverables
# generated from them land in week10/.
WEEK10_DIR = ROOT / "week10"
W10_RUNS_DIR = EVALS_DIR / "w10" / "runs"


# --- Week 11 · observability, cost, failure -> test loop ---------------------------
# One JSON line per production request, redacted on write. Committed (not under a
# logs/ dir) because the drill's evidence IS this file.
WEEK11_DIR = ROOT / "week11"
W11_LOG_FILE = WEEK11_DIR / "obs" / "requests.jsonl"
W11_SUITE_FILE = EVALS_DIR / "w11" / "coverage_suite.jsonl"
W11_RUNS_DIR = EVALS_DIR / "w11" / "runs"


# --- Week 12 · capstone: one entry point, RAG + agent + MCP + evals + logging -------
# TRIAGE_VERSION is the ONE knob the failure -> test loop moves:
#   triage-v1  the parts as they were: policy-docs.search_policy takes no loss date,
#              get_clause returns whichever edition loaded last (seams S2, S3).
#   triage-v2  the wording in force on the loss date, enforced in the store query:
#              search_policy REQUIRES loss_date; get_clause resolves the edition by it.
# The MCP server reads the same variable (passed through mcp_servers.capstone.json),
# so the host and the server can never disagree about which version is running.
TRIAGE_VERSION = os.getenv("TRIAGE_VERSION", "triage-v2")
DATE_FILTER = TRIAGE_VERSION != "triage-v1"
WEEK12_DIR = ROOT / "week12"
W12_DIR = EVALS_DIR / "w12"
W12_SUITE_FILE = W12_DIR / "suite.jsonl"
W12_RUNS_DIR = W12_DIR / "runs"
W12_LABELS_FILE = W12_DIR / "labels.json"
POLICY_REGISTER_FILE = ROOT / "data" / "policies" / "register.json"
PRODUCTS_FILE = ROOT / "data" / "policies" / "products.json"
CAPSTONE_MCP_CONFIG = ROOT / "mcp_servers.capstone.json"
# One trace per request, redacted on write. The MCP server appends its own spans to
# the server-span file under the trace id it receives in the request's _meta.
W12_TRACE_FILE = Path(os.getenv("W12_TRACE_FILE", str(WEEK12_DIR / "obs" / "traces.jsonl")))
W12_MCP_SPAN_FILE = Path(os.getenv("W12_MCP_SPAN_FILE", str(WEEK12_DIR / "obs" / "mcp_server_spans.jsonl")))
TRIAGE_MAX_ITERS = int(os.getenv("TRIAGE_MAX_ITERS", "6"))
# The triage agent's model. gpt-oss-20b, not Weeks 7-11's gpt-oss-120b: on Groq's free
# tier each model has its own ~200k tokens/day, and one 26-case suite run of the
# 4-lap agent costs ~150k. 120b's day goes to the judge (the Week 6 judge model).
TRIAGE_MODEL = os.getenv("TRIAGE_MODEL", "openai/gpt-oss-20b")
TRIAGE_WALL_CLOCK_S = float(os.getenv("TRIAGE_WALL_CLOCK_S", "240"))
