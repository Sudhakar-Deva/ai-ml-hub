"""The trace record, and the only way to write one.

A trace is worth keeping only if it can be replayed without the app that
produced it. That sets the field list — not "what was easy to log":

  trace_id                a stable handle to argue about
  ts                      when
  prompt_version + sha    WHICH prompt, provably
  model + params          model, temperature, max_tokens, seed if any
  retriever config        strategy, retriever, k — retrieval is half the system
  retrieved[]             chunk_id AND score AND rank, per chunk
  rendered_prompt         the exact user message that was sent
  system_prompt           the exact system message that was sent
  output                  raw model text, unparsed
  redaction               which rules fired, and that they fired BEFORE write

Everything that reaches this module goes through redact_deep on the way to the
file. There is no writer that skips it.
"""
import hashlib
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone

from .. import config
from .redact import redact_deep

SCHEMA_VERSION = 2


def new_trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def sha(text: str, n: int = 12) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:n]


def _git_sha() -> str:
    """Which build produced this trace. A taxonomy is only about the app that
    was running when the traces were written."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=config.ROOT, capture_output=True, text=True, timeout=5,
        ).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def build_trace(
    *,
    question: str,
    output: str,
    system_prompt: str,
    rendered_prompt: str,
    retrieved: list[dict],
    model: str,
    params: dict,
    strategy: str,
    retriever: str,
    k: int,
    latency_ms: float | None = None,
    refused: bool | None = None,
    citations: list[dict] | None = None,
    source: str = "api",
    trace_id: str | None = None,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "trace_id": trace_id or new_trace_id(),
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "app_git_sha": _git_sha(),
        "question": question,
        "prompt_version": config.PROMPT_VERSION,
        "system_prompt_sha": sha(system_prompt),
        "rendered_prompt_sha": sha(rendered_prompt),
        "system_prompt": system_prompt,
        "rendered_prompt": rendered_prompt,
        "model": model,
        "params": params,
        "retrieval": {
            "strategy": strategy,
            "retriever": retriever,
            "k": k,
            "embed_model": config.EMBEDDING_MODEL,
            "retrieved": [
                {
                    "rank": r.get("rank"),
                    "chunk_id": r.get("chunk_id"),
                    "score": r.get("score"),
                    "score_kind": r.get("score_kind", "cosine"),
                    "dense_rank": r.get("dense_rank"),
                    "bm25_rank": r.get("bm25_rank"),
                    "form_number": r.get("form_number"),
                    "edition_date": r.get("edition_date"),
                    "policy_line": r.get("policy_line"),
                    "clause": r.get("clause"),
                }
                for r in retrieved
            ],
        },
        "output": output,
        "refused": refused,
        "citations": citations or [],
        "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
    }


def write(trace: dict, path=None) -> dict:
    """Redact, then append one JSON line. Returns the record as written.

    Redaction happens HERE, before the bytes exist on disk — not in a cleanup
    pass over the file later, by which time the unredacted version has already
    been written, backed up and read.
    """
    path = path or config.TRACE_FILE
    clean, hits = redact_deep(trace)
    clean["redaction"] = {
        "applied": True,
        "when": "pre-write",
        "rules_fired": hits,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(clean, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return clean


def read_all(path=None) -> list[dict]:
    path = path or config.TRACE_FILE
    if not path.exists():
        return []
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path}:{i} is not valid JSON — {e}") from e
    return out


def by_id(trace_id: str, path=None) -> dict | None:
    return next((t for t in read_all(path) if t["trace_id"] == trace_id), None)
