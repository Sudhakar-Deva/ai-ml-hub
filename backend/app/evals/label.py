"""Hand-labelling the 25 summaries — blind, and provably before the judge.

    python -m app.evals.label --start
    python -m app.evals.label --next
    python -m app.evals.label --set w6-004 pass "the position is right and cited"
    python -m app.evals.label --status

You label ONE thing, the judge's single binary criterion: does the summary's
coverage position rest on the wording that actually governs this claim? PASS or
FAIL. No 1-10, no "mostly", no "within one".

Blindness is enforced, not requested:

  * `--next` prints the notes, the retrieved chunk headers and the summary. It
    never prints a judge verdict, and it will not start if a judge run already
    exists for the current summaries.sha — once you have seen the judge you can
    no longer produce a blind label, and pretending otherwise is the failure the
    whole exercise is built to prevent.
  * every label records the sha256 of summaries.json it was made against, so a
    label can be shown to be about the summary that was actually judged.
  * the ordering evidence is a git commit, not a sentence: commit labels_25.json
    before running the judge, and app.evals.judge refuses to run until you have.
"""
import argparse
import json

from .. import config
from . import store
from .cases import by_id as case_by_id
from .cases import load as load_cases

VALID = {"pass": True, "fail": False}


def _judge_already_run() -> list[str]:
    """Any judge run against the CURRENT summaries. If one exists, labelling
    from here is no longer blind."""
    if not config.W6_RUNS_DIR.exists():
        return []
    sha = store.summaries_sha()
    seen = []
    for p in sorted(config.W6_RUNS_DIR.glob("judge_*.json")):
        try:
            if json.loads(p.read_text()).get("summaries_sha") == sha:
                seen.append(p.name)
        except json.JSONDecodeError:
            continue
    return seen


def load() -> dict:
    if config.W6_LABELS_FILE.exists():
        return json.loads(config.W6_LABELS_FILE.read_text())
    return {
        "criterion": (
            "Does the summary's coverage position rest on the wording that actually "
            "governs this claim? PASS only if the position is right for the policy line "
            "and form edition in the notes AND every policy statement is supported by "
            "the chunk cited for it."
        ),
        "scale": "binary — pass | fail. No numeric score, no tolerance band.",
        "labeller": "human, blind to every judge verdict",
        "started_at": None,
        "summaries_sha": None,
        "labels": {},
    }


def save(state: dict) -> None:
    config.W6_DIR.mkdir(parents=True, exist_ok=True)
    config.W6_LABELS_FILE.write_text(json.dumps(state, indent=2) + "\n")


def guard() -> None:
    seen = _judge_already_run()
    if seen:
        raise SystemExit(
            "A judge run already exists for these summaries: " + ", ".join(seen) + "\n"
            "Labels written after a judge run are not blind labels, whether or not you "
            "opened the file. Re-generate the summaries and start over, or keep the "
            "labels you already committed."
        )


def start() -> dict:
    guard()
    state = load()
    state["started_at"] = store.now()
    state["summaries_sha"] = store.summaries_sha()
    save(state)
    return state


def set_label(case_id: str, verdict: str, reason: str) -> dict:
    guard()
    if verdict.lower() not in VALID:
        raise SystemExit(f"verdict must be one of {sorted(VALID)} — got {verdict!r}")
    case_by_id(case_id)
    store.summary_for(case_id)
    state = load()
    if state.get("summaries_sha") is None:
        state["summaries_sha"] = store.summaries_sha()
    state["labels"][case_id] = {
        "label": verdict.lower(),
        "passed": VALID[verdict.lower()],
        "reason": reason.strip(),
        "labelled_at": store.now(),
    }
    save(state)
    return state


def status() -> dict:
    state = load()
    ids = [c["id"] for c in load_cases()]
    done = set(state["labels"])
    return {
        "criterion": state["criterion"],
        "summaries_sha_at_labelling": state.get("summaries_sha"),
        "summaries_sha_now": store.summaries_sha(),
        "labelled": len(done),
        "target": config.LABEL_N,
        "remaining": [i for i in ids if i not in done],
        "judge_runs_against_these_summaries": _judge_already_run(),
        "committed": store.committed_at(config.W6_LABELS_FILE),
    }


def show(case_id: str) -> str:
    case = case_by_id(case_id)
    entry = store.load_summaries()["summaries"][case_id]
    lines = [
        "=" * 78,
        f"{case['id']}   mode={case['mode']}   kind={case['kind']}",
    ]
    if case.get("source_trace_id"):
        lines.append(f"replayed verbatim from trace {case['source_trace_id']}")
    lines += [
        "-" * 78, "ADJUSTER NOTES", case["notes"],
        "-" * 78, "RETRIEVED (what the app was handed)",
    ]
    for r in entry.get("retrieved", []):
        lines.append(
            f"  {r['rank']}. {r['form_number']} [{r['policy_line']}]  {r['chunk_id']}  "
            f"score={r['score']}"
        )
    lines += ["-" * 78, "SUMMARY", entry["summary"], "=" * 78]
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", action="store_true")
    ap.add_argument("--next", dest="next_", action="store_true")
    ap.add_argument("--show", metavar="CASE_ID")
    ap.add_argument("--set", nargs=3, metavar=("CASE_ID", "PASS_OR_FAIL", "REASON"))
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    if a.start:
        s = start()
        print(f"labelling started {s['started_at']} against summaries sha {s['summaries_sha']}")
        print(f"criterion: {s['criterion']}")
    elif a.next_:
        st = status()
        if not st["remaining"]:
            print(f"all {st['labelled']} cases labelled. Commit the file BEFORE running the judge:")
            print("  git add evals/w6/labels_25.json && git commit -m 'week 6: 25 blind hand labels'")
        else:
            print(show(st["remaining"][0]))
            print(f"\n{st['labelled']}/{len(st['remaining']) + st['labelled']} labelled · "
                  f"next: {st['remaining'][0]}")
    elif a.show:
        print(show(a.show))
    elif a.set:
        set_label(*a.set)
        st = status()
        print(f"recorded. {st['labelled']} labelled, {len(st['remaining'])} to go.")
    else:
        print(json.dumps(status(), indent=2))
