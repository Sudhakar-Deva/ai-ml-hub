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

VECTOR_DB_PATH = ROOT / os.getenv("VECTOR_DB_PATH", "backend/.chroma")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))

TOP_K = 5  # hit-in-top-5 is the metric; keep fixed across strategies

STRATEGIES = ("current", "structure_aware")


def collection_name(strategy: str) -> str:
    return f"endorsements_{strategy}"
