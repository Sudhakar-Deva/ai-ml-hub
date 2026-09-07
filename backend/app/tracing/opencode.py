"""The open-coding pass: one honest sentence per trace, and nothing else.

    python -m app.tracing.opencode --start          # pins the code you are reading
    python -m app.tracing.opencode --next           # print the next uncoded trace
    python -m app.tracing.opencode --code tr_x "..." # record one sentence
    python -m app.tracing.opencode --status         # progress + the zero-fix check

Three rules this enforces rather than suggests:

1. ONE sentence per trace, describing what you SAW. Not the category it belongs
   to, not the fix. "I don't know why this failed" is permitted and valuable —
   it is an honest observation and it is graded as one.
2. Diagnosis words are refused at the point of entry. "hallucination",
   "retrieval issue", "bug in the reranker" are conclusions wearing an
   observation's clothes, and once one is written down the remaining traces get
   read into it.
3. ZERO code changes while coding. --start records the git SHA and the working
   tree hash; --status compares them. The zero is graded, so it is measured
   rather than asserted.
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone

from .. import config
from .trace import by_id

# Words that turn an observation into a diagnosis. Not a style rule — the whole
# week fails if the categories are decided before the reading.
DIAGNOSIS_WORDS = {
    "hallucination", "hallucinated", "hallucinates",
    "retrieval issue", "retrieval problem", "retrieval failure",
    "chunking issue", "chunking problem",
    "embedding issue", "prompt issue", "prompt problem",
    "should fix", "we should", "need to fix", "fix by", "the fix is",
    "root cause", "because the retriever", "because the model",
    "bug", "regression",
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=config.ROOT, capture_output=True, text=True
    ).stdout.strip()


def tree_fingerprint() -> str:
    """HEAD plus the diff of the working tree — changes either and this moves."""
    head = _git("rev-parse", "HEAD")
    diff = _git("diff", "HEAD", "--", "backend", "frontend")
    return hashlib.sha256(f"{head}\n{diff}".encode()).hexdigest()[:16]


def load() -> dict:
    if config.CODING_FILE.exists():
        return json.loads(config.CODING_FILE.read_text())
    return {"started_at": None, "fingerprint_at_start": None, "codes": []}


def save(state: dict) -> None:
    config.CODING_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.CODING_FILE.write_text(json.dumps(state, indent=2))


def sample_ids() -> list[str]:
    if not config.SAMPLE_FILE.exists():
        raise SystemExit(
            f"no sample at {config.SAMPLE_FILE} — draw one first:\n"
            "  python -m app.tracing.sample"
        )
    return json.loads(config.SAMPLE_FILE.read_text())["trace_ids"]


def start() -> dict:
    state = load()
    state["started_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state["fingerprint_at_start"] = tree_fingerprint()
    state["head_at_start"] = _git("rev-parse", "--short", "HEAD")
    save(state)
    return state


def check_sentence(text: str) -> list[str]:
    low = text.lower()
    return sorted({w for w in DIAGNOSIS_WORDS if w in low})


def code(trace_id: str, sentence: str, force: bool = False) -> dict:
    if by_id(trace_id) is None:
        raise SystemExit(f"no trace {trace_id}")
    smells = check_sentence(sentence)
    if smells and not force:
        raise SystemExit(
            f"That reads as a diagnosis, not an observation — it contains {smells}.\n"
            "Describe what you saw in the output, not why it happened or what to change.\n"
            "Pass --force if you are sure the word is being used descriptively."
        )
    state = load()
    state["codes"] = [c for c in state["codes"] if c["trace_id"] != trace_id]
    state["codes"].append(
        {
            "trace_id": trace_id,
            "sentence": sentence.strip(),
            "coded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "diagnosis_words_flagged": smells,
        }
    )
    state["codes"].sort(key=lambda c: c["trace_id"])
    save(state)
    return state


def status() -> dict:
    state = load()
    ids = sample_ids()
    coded = {c["trace_id"] for c in state["codes"]}
    now = tree_fingerprint()
    return {
        "sample_size": len(ids),
        "coded": len(coded & set(ids)),
        "remaining": [i for i in ids if i not in coded],
        "started_at": state.get("started_at"),
        "head_at_start": state.get("head_at_start"),
        "fingerprint_at_start": state.get("fingerprint_at_start"),
        "fingerprint_now": now,
        "zero_fixes_during_coding": state.get("fingerprint_at_start") == now,
    }


def show(trace: dict) -> str:
    r = trace.get("retrieval", {})
    lines = [
        "=" * 78,
        f"trace_id   {trace['trace_id']}   ({trace['ts']}, source={trace.get('source')})",
        f"model      {trace['model']}  {trace['params']}  prompt={trace['prompt_version']}",
        f"retrieval  {r.get('retriever')} · {r.get('strategy')} · k={r.get('k')}",
        "-" * 78,
        f"QUESTION\n{trace['question']}",
        "-" * 78,
        "RETRIEVED",
    ]
    for h in r.get("retrieved", []):
        lines.append(
            f"  {h['rank']}. {h['form_number']} ed.{h.get('edition_date')} "
            f"[{h.get('policy_line')}]  {h.get('clause')}"
        )
        lines.append(f"     {h['chunk_id']}  {h.get('score_kind')}={h.get('score')}")
    lines += ["-" * 78, f"OUTPUT\n{trace['output']}"]
    cits = trace.get("citations") or []
    if cits:
        lines.append("-" * 78)
        lines.append("CITATIONS")
        for c in cits:
            lines.append(
                f"  {'ok ' if c.get('resolves') else 'DEAD'} {c['chunk_id']} "
                f"| {c.get('form_number')} | {c.get('clause')}"
            )
    lines.append("=" * 78)
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", action="store_true")
    ap.add_argument("--next", dest="next_", action="store_true")
    ap.add_argument("--show", metavar="TRACE_ID")
    ap.add_argument("--code", nargs=2, metavar=("TRACE_ID", "SENTENCE"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    if a.start:
        s = start()
        print(f"coding started {s['started_at']} at {s['head_at_start']} "
              f"(fingerprint {s['fingerprint_at_start']})")
        print("Do not change code until every trace is coded. --status verifies it.")
    elif a.next_:
        st = status()
        if not st["remaining"]:
            print("all sampled traces are coded.")
        else:
            print(show(by_id(st["remaining"][0])))
            print(f"\n{st['coded']}/{st['sample_size']} coded · "
                  f"{len(st['remaining'])} to go · next: {st['remaining'][0]}")
    elif a.show:
        t = by_id(a.show)
        print(show(t) if t else f"no trace {a.show}")
    elif a.code:
        code(a.code[0], a.code[1], a.force)
        st = status()
        print(f"recorded. {st['coded']}/{st['sample_size']} coded.")
    else:
        print(json.dumps(status(), indent=2))
