"""The claim-summary request, instrumented. One request = one log line.

    python -m app.obs.app --notes-file notes.txt --user ADJ-114
    python -m app.obs.app --notes "..." --user ADJ-207 --ts 2026-11-15T14:03:00+00:00

The line holds what the drill needs to find a bad answer from a vague complaint,
and nothing it must not hold:

  request_id, ts, user, input_type, prompt_version, model   the slices
  spans[]   retrieval / generation / tools: latency_ms, tokens, cost_usd each
  retrieved_context_ids[] + clause per id                     what the model was shown
  output.coverage_position / exclusions_applied / governing_form   the OUTPUT, indexed
  input.notes (redacted on write) + notes_sha                 the input, searchable without PII

Redaction runs inside write() before the bytes exist (app.tracing.redact), the
same rule as Week 5. Claim numbers, policy numbers and names never reach disk.

`ts` is the request's business timestamp. Simulated traffic sets it to a time
"yesterday"; `ran_at` is always the wall clock, so a replayed day can't be
mistaken for a live one.
"""
import argparse
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone

from .. import config
from ..agents.budget import price
from ..llm import complete
from ..retrieval.search import get_chunk
from ..tracing.redact import redact_deep


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def handle(notes: str, user: str, input_type: str = "claim_summary", ts: str | None = None,
           log_path=None, write_log: bool = True) -> dict:
    from ..generation import summarize as S          # read at call time: a prompt fix applies immediately

    spans = []

    # --- retrieval: local embedder + Chroma + BM25, no API cost ---------------------
    t0 = time.perf_counter()
    hits = S.retrieve(notes)
    spans.append({"name": "retrieval", "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                  "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                  "detail": f"{config.SHIPPED_RETRIEVER} k={len(hits)} embed={config.EMBEDDING_MODEL} (local)"})

    # --- generation: the one paid call ---------------------------------------------
    rendered = S.PROMPT.format(context=S._format_context(hits), notes=notes)
    params = {"temperature": 0, "max_tokens": 1024}
    t0 = time.perf_counter()
    text, usage = complete(model=config.LLM_MODEL, system=S.SYSTEM, user=rendered, params=params)
    spans.append({"name": "generation", "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                  "tokens_in": usage["input_tokens"], "tokens_out": usage["output_tokens"],
                  "cost_usd": round(price(config.LLM_MODEL, usage["input_tokens"], usage["output_tokens"]), 7),
                  "detail": f"{config.LLM_MODEL} {params}"})

    # --- tools: citation resolution against the index, no API cost ------------------
    t0 = time.perf_counter()
    cites = [(cid.strip(), get_chunk(cid.strip(), "structure_aware") is not None)
             for cid, _, _ in S.CITATION_RE.findall(text)]
    spans.append({"name": "tools", "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                  "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                  "detail": f"resolve_citations x{len(cites)}"})

    f = S.parse(text)
    rec = {
        "request_id": f"req_{uuid.uuid4().hex[:12]}",
        "ts": ts or _now(),
        "ran_at": _now(),
        "user": user,
        "input_type": input_type,
        "prompt_version": config.SUMMARY_PROMPT_VERSION,
        "model": config.LLM_MODEL,
        "input": {"notes": notes, "notes_sha": hashlib.sha256(notes.encode()).hexdigest()[:12],
                  "notes_chars": len(notes)},
        "retrieved_context_ids": [h["chunk_id"] for h in hits],
        "retrieved": [{"rank": h.get("rank"), "chunk_id": h["chunk_id"], "form": h["form_number"],
                       "policy_line": h.get("policy_line"), "clause": h["clause"]} for h in hits],
        "spans": spans,
        "totals": {"latency_ms": round(sum(s["latency_ms"] for s in spans), 1),
                   "tokens": sum(s["tokens_in"] + s["tokens_out"] for s in spans),
                   "cost_usd": round(sum(s["cost_usd"] for s in spans), 7)},
        "output": {"coverage_position": (f["COVERAGE POSITION"] or "").upper() or None,
                   "exclusions_applied": f["EXCLUSIONS APPLIED"], "governing_form": f["GOVERNING FORM"],
                   "policy_line": f["POLICY LINE"], "deductible": f["DEDUCTIBLE"],
                   "citations": [{"chunk_id": c, "resolves": ok} for c, ok in cites], "text": text},
    }
    return write(rec, log_path) if write_log else rec


def write(rec: dict, path=None) -> dict:
    """Redact, then append. There is no writer that skips redaction."""
    path = path or config.W11_LOG_FILE
    clean, hits = redact_deep(rec)
    clean["redaction"] = {"applied": True, "when": "pre-write", "rules_fired": hits}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(clean, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return clean


def read_all(path=None) -> list[dict]:
    path = path or config.W11_LOG_FILE
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


if __name__ == "__main__":
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("--notes")
    ap.add_argument("--notes-file")
    ap.add_argument("--user", required=True)
    ap.add_argument("--input-type", default="claim_summary")
    ap.add_argument("--ts", help="business timestamp (ISO 8601); default now")
    a = ap.parse_args()
    notes = Path(a.notes_file).read_text() if a.notes_file else a.notes
    if not notes:
        raise SystemExit("give --notes or --notes-file")
    r = handle(notes, a.user, a.input_type, a.ts)
    print(json.dumps({k: r[k] for k in ("request_id", "ts", "user", "prompt_version", "totals")}, indent=1))
    print(r["output"]["text"])
