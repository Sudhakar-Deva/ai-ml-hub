"""Push a question bank through the app so it leaves traces behind.

    python -m app.tracing.traffic --bank traffic       # the natural stream
    python -m app.tracing.traffic --bank demo          # the curated review set

This is the app answering questions, not a simulator: every trace it writes came
out of the same answer() path the API uses, with the same prompt, the same
retriever and the same model. That is the only reason the taxonomy built on
these traces describes the real system.

The banks in evals/traffic/ were written as adjuster traffic, before any of it
was run. None of the questions were chosen because they break the app — picking
those is how you get frequencies that are fiction.
"""
import argparse
import sys
import time

from .. import config
from .trace import read_all

BANKS = {
    "traffic": config.TRAFFIC_DIR / "questions_traffic.txt",
    "demo": config.TRAFFIC_DIR / "questions_demo.txt",
}


def load_bank(name: str) -> list[str]:
    path = BANKS[name]
    if not path.exists():
        raise SystemExit(f"no question bank at {path}")
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def already_asked(source: str) -> set[str]:
    """Questions this source has already traced — reruns append, they don't
    duplicate, so an interrupted run can be resumed without skewing the
    population with near-identical rows."""
    return {t["question"] for t in read_all() if t.get("source") == source}


def run(bank: str, limit: int | None = None, sleep: float = 0.0, resume: bool = True) -> dict:
    from ..generation.answer import MissingAPIKey, answer

    questions = load_bank(bank)
    seen = already_asked(bank) if resume else set()
    todo = [q for q in questions if q not in seen][:limit]

    print(f"bank={bank}  questions={len(questions)}  already traced={len(seen)}  to run={len(todo)}")
    if not todo:
        return {"bank": bank, "ran": 0, "failed": 0, "skipped": len(seen)}

    ran = failed = 0
    for i, q in enumerate(todo, start=1):
        try:
            r = answer(q, source=bank)
            ran += 1
            flag = "REFUSED" if r["refused"] else "answered"
            bad = " !!unresolvable-citation" if r["unresolvable_citations"] else ""
            print(f"  {i:3d}/{len(todo)}  {r['trace_id']}  {flag}{bad}  {q[:64]}")
        except MissingAPIKey as e:
            raise SystemExit(str(e)) from e
        except Exception as e:  # keep the run going; a dropped call is a gap, not a stop
            failed += 1
            print(f"  {i:3d}/{len(todo)}  FAILED  {type(e).__name__}: {e}", file=sys.stderr)
        if sleep:
            time.sleep(sleep)

    return {"bank": bank, "ran": ran, "failed": failed, "skipped": len(seen)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", choices=sorted(BANKS), default="traffic")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between calls")
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    a = ap.parse_args()

    stats = run(a.bank, a.limit, a.sleep, a.resume)
    print(f"\n{stats}")
    print(f"trace file: {config.TRACE_FILE.relative_to(config.ROOT)} "
          f"({len(read_all())} traces total)")
