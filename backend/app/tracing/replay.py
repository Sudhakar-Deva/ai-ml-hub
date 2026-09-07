"""Replay a trace from the trace alone.

    python -m app.tracing.replay tr_abc123           # replay + diff
    python -m app.tracing.replay tr_abc123 --audit   # just check completeness

"From the trace alone" is the test that matters, so this module never calls
search(), never reads the vector store, and never reads today's prompt. It sends
the stored system prompt and the stored rendered prompt to the stored model with
the stored params. If a field is missing, replay fails loudly and names it —
which is how you find out your logging was decorative.
"""
import argparse
import difflib
import json

from .. import config
from .trace import by_id

REQUIRED = [
    ("trace_id", "the handle"),
    ("prompt_version", "which prompt produced this"),
    ("system_prompt", "the exact system message"),
    ("rendered_prompt", "the exact user message, context included"),
    ("model", "which model"),
    ("params", "temperature / max_tokens"),
    ("output", "the raw model text"),
    ("retrieval", "chunk_ids + scores"),
]


def audit(trace: dict) -> dict:
    """What is present, what is missing, what cannot be reconstructed."""
    missing = [(f, why) for f, why in REQUIRED if not trace.get(f)]
    retrieval = trace.get("retrieval") or {}
    retrieved = retrieval.get("retrieved") or []
    gaps = []
    if not retrieved:
        gaps.append("retrieval.retrieved is empty — chunk_ids and scores are unrecoverable")
    if retrieved and any(r.get("score") is None for r in retrieved):
        gaps.append("at least one retrieved chunk has no score")
    if not trace.get("app_git_sha") or trace.get("app_git_sha") == "unknown":
        gaps.append("app_git_sha unknown — cannot say which build answered")
    return {
        "trace_id": trace.get("trace_id"),
        "replayable": not missing,
        "missing_fields": [{"field": f, "why_it_matters": w} for f, w in missing],
        "gaps": gaps,
        "redaction": trace.get("redaction"),
        "retrieved_count": len(retrieved),
    }


def replay(trace: dict) -> dict:
    """Re-send the stored prompt to the stored model. No app state involved."""
    import anthropic

    report = audit(trace)
    if not report["replayable"]:
        raise SystemExit(
            "Not replayable from the trace alone. Missing: "
            + ", ".join(m["field"] for m in report["missing_fields"])
        )
    if not config.LLM_API_KEY:
        raise SystemExit("LLM_API_KEY is not set — replay needs the same model the trace names.")

    client = anthropic.Anthropic(api_key=config.LLM_API_KEY)
    msg = client.messages.create(
        model=trace["model"],
        system=trace["system_prompt"],
        messages=[{"role": "user", "content": trace["rendered_prompt"]}],
        **trace["params"],
    )
    replayed = msg.content[0].text.strip()
    original = trace["output"]

    return {
        "audit": report,
        "model": trace["model"],
        "params": trace["params"],
        "prompt_version": trace["prompt_version"],
        "original": original,
        "replayed": replayed,
        "identical": replayed == original,
        "similarity": round(
            difflib.SequenceMatcher(None, original, replayed).ratio(), 4
        ),
        "diff": "\n".join(
            difflib.unified_diff(
                original.splitlines(), replayed.splitlines(),
                fromfile="original", tofile="replayed", lineterm="",
            )
        ),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("trace_id")
    ap.add_argument("--audit", action="store_true", help="completeness check only, no model call")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    t = by_id(a.trace_id)
    if t is None:
        raise SystemExit(f"no trace {a.trace_id} in {config.TRACE_FILE}")

    if a.audit:
        print(json.dumps(audit(t), indent=2))
        raise SystemExit(0)

    r = replay(t)
    if a.json:
        print(json.dumps(r, indent=2))
    else:
        print(f"trace_id     {t['trace_id']}")
        print(f"prompt       {r['prompt_version']}  ·  model {r['model']}  ·  {r['params']}")
        print(f"identical    {r['identical']}   similarity {r['similarity']}")
        print(f"\n--- ORIGINAL ---\n{r['original']}")
        print(f"\n--- REPLAYED ---\n{r['replayed']}")
        if r["diff"]:
            print(f"\n--- DIFF ---\n{r['diff']}")
