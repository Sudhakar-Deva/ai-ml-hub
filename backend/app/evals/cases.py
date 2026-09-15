"""The Week 6 eval set: 25+ mode-tagged claim-summary cases.

    python -m app.evals.cases --list
    python -m app.evals.cases --show w6-004
    python -m app.evals.cases --check

Every case carries exactly one mode from Week 5's taxonomy (`week5/modes.json`),
because a single overall pass rate is the mistake this week exists to prevent:
the average will happily hide a regression on the wrong-form mode while the
straightforward-summary mode carries the number.

Two kinds of case:

  synthetic   adjuster notes written to exercise a mode. The claim numbers,
              names and dates in them are invented — no real claim file is in
              this repo.
  regression  notes replayed VERBATIM out of a real failed trace in
              traces/traces.jsonl. `source_trace_id` names it. These are not
              rewritten to read better; a regression case that has been tidied
              up is a different case.

`gold` is what the eval designer says the right coverage position is, written
from the corpus before any summary existed. It is not the hand label — the hand
label is a judgement about a specific summary, and it is made blind, later.
"""
import argparse
import json

from .. import config


def load() -> list[dict]:
    if not config.W6_CASES_FILE.exists():
        raise SystemExit(f"no eval set at {config.W6_CASES_FILE}")
    out = []
    for i, line in enumerate(config.W6_CASES_FILE.read_text().splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{config.W6_CASES_FILE}:{i} is not valid JSON — {e}") from e
    return out


def by_id(case_id: str) -> dict:
    c = next((c for c in load() if c["id"] == case_id), None)
    if c is None:
        raise SystemExit(f"no case {case_id}")
    return c


def modes() -> list[str]:
    """The mode keys the Week 5 taxonomy defined. Read from modes.json, never
    retyped here — an eval tagged with a mode that no longer exists is an eval
    reporting on a taxonomy nobody has."""
    path = config.WEEK5_DIR / "modes.json"
    if not path.exists():
        raise SystemExit(f"no Week 5 taxonomy at {path} — Week 6 tags cases with its modes")
    return [m["key"] for m in json.loads(path.read_text())["modes"]]


REQUIRED = ("id", "mode", "kind", "claim_number", "date_of_loss", "policy_line", "notes", "gold")


def check() -> list[str]:
    cases = load()
    known = set(modes())
    problems = []

    if len(cases) < 25:
        problems.append(f"{len(cases)} cases — the brief asks for 25 or more")

    seen = set()
    for c in cases:
        for f in REQUIRED:
            if not c.get(f):
                problems.append(f"{c.get('id', '?')}: missing {f}")
        if c["id"] in seen:
            problems.append(f"{c['id']}: duplicate id")
        seen.add(c["id"])
        if c.get("mode") not in known:
            problems.append(f"{c['id']}: mode {c.get('mode')!r} is not in week5/modes.json")
        if c.get("kind") == "regression" and not c.get("source_trace_id"):
            problems.append(f"{c['id']}: regression case with no source_trace_id")
        if c.get("kind") not in ("synthetic", "regression"):
            problems.append(f"{c['id']}: kind {c.get('kind')!r}")
        if c.get("claim_number") and c["claim_number"] not in c.get("notes", ""):
            problems.append(f"{c['id']}: claim_number is not in the notes it claims to come from")

    regressions = [c for c in cases if c.get("kind") == "regression"]
    if len(regressions) < 2:
        problems.append(f"{len(regressions)} regression cases — the brief asks for at least 2")

    # A regression case has to be traceable back to the trace it came from, or
    # it is a synthetic case wearing a badge.
    if regressions:
        from ..tracing.trace import by_id as trace_by_id

        for c in regressions:
            if trace_by_id(c["source_trace_id"]) is None:
                problems.append(f"{c['id']}: source_trace_id {c['source_trace_id']} is not in the trace file")

    uncovered = known - {c.get("mode") for c in cases}
    if uncovered:
        problems.append(f"modes with no eval case: {sorted(uncovered)}")
    return problems


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    if a.show:
        print(json.dumps(by_id(a.show), indent=2))
    elif a.check:
        problems = check()
        if problems:
            print("EVAL SET NOT VALID:")
            for p in problems:
                print(f"  - {p}")
            raise SystemExit(1)
        cases = load()
        print(f"ok — {len(cases)} cases, "
              f"{sum(1 for c in cases if c['kind'] == 'regression')} replayed from real traces, "
              f"{len(set(c['mode'] for c in cases))} modes covered")
    else:
        for c in load():
            tag = "REGRESSION" if c["kind"] == "regression" else "synthetic "
            print(f"{c['id']}  {tag}  {c['mode']:<34}  {c['notes'].splitlines()[0][:60]}")
