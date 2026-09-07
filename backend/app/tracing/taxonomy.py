"""Turn coded sentences into a ranked, one-screen taxonomy.

    python -m app.tracing.taxonomy --write        # -> taxonomy.md

Reads week5/modes.json — the clustering decision, which is a human one — and
checks the things that are easy to get wrong and fatal to the write-up:

  * 4 to 7 modes. Three is a shrug; ten is a list of traces with headings.
  * Every sampled trace accounted for exactly once, failures and clean runs both.
    A taxonomy that quietly drops traces reports a frequency of nothing.
  * A severity per mode, from a fixed vocabulary, because "wrongly denies a
    claim" and "annoys the adjuster" are not the same queue.
  * A mode name a stranger could act on. Names that are bare diagnoses
    ("retrieval issue") are rejected here, for the same reason they are rejected
    during coding.
  * The example trace_id actually belongs to the mode.

Ranking is by severity first, then frequency. The most common mode is not
automatically the one to fix — a 10% mode that wrongly denies a claim outranks a
40% mode that makes an adjuster sigh.
"""
import argparse
import json
from collections import Counter

from .. import config

MODES_FILE = config.WEEK5_DIR / "modes.json"

SEVERITY = {
    "wrongly-denies": ("Wrongly denies a claim", 0),
    "wrongly-pays": ("Wrongly pays a claim", 1),
    "annoys-adjuster": ("Merely annoys the adjuster", 2),
    "none": ("No failure observed", 3),
}

BANNED_NAME_WORDS = {
    "retrieval issue", "hallucination", "bug", "bad output", "wrong answer",
    "model issue", "prompt issue", "misc", "other", "various",
}


def load_modes() -> dict:
    if not MODES_FILE.exists():
        raise SystemExit(
            f"no clustering at {MODES_FILE}.\n"
            "Cluster the coded sentences by hand first — that judgement is the deliverable."
        )
    return json.loads(MODES_FILE.read_text())


def load_codes() -> dict[str, str]:
    if not config.CODING_FILE.exists():
        raise SystemExit(f"no open coding at {config.CODING_FILE}")
    state = json.loads(config.CODING_FILE.read_text())
    return {c["trace_id"]: c["sentence"] for c in state["codes"]}


def sample_ids() -> list[str]:
    return json.loads(config.SAMPLE_FILE.read_text())["trace_ids"]


def validate(modes: dict, ids: list[str]) -> list[str]:
    problems = []
    failure_modes = [m for m in modes["modes"] if m["severity"] != "none"]

    if not 4 <= len(failure_modes) <= 7:
        problems.append(f"{len(failure_modes)} failure modes — the brief asks for 4 to 7")

    assigned = Counter()
    for m in modes["modes"]:
        if m["severity"] not in SEVERITY:
            problems.append(f"{m['name']!r}: unknown severity {m['severity']!r}")
        low = m["name"].lower()
        if any(b in low for b in BANNED_NAME_WORDS):
            problems.append(f"{m['name']!r} is a diagnosis, not something a manager can act on")
        if len(m["name"].split()) < 3:
            problems.append(f"{m['name']!r} is too short to be legible to a stranger")
        for tid in m["trace_ids"]:
            assigned[tid] += 1
        if m["trace_ids"] and m.get("example") not in m["trace_ids"]:
            problems.append(f"{m['name']!r}: example {m.get('example')} is not in this mode")

    for tid in ids:
        if assigned[tid] == 0:
            problems.append(f"{tid} is in the sample but in no mode")
        elif assigned[tid] > 1:
            problems.append(f"{tid} is in {assigned[tid]} modes — one trace, one mode")
    for tid in assigned:
        if tid not in ids:
            problems.append(f"{tid} is in a mode but not in the sample")
    return problems


def build(modes: dict, ids: list[str]) -> list[dict]:
    n = len(ids)
    rows = []
    for m in modes["modes"]:
        count = len(m["trace_ids"])
        label, order = SEVERITY[m["severity"]]
        rows.append(
            {
                "name": m["name"],
                "count": count,
                "pct": round(100 * count / n, 1),
                "severity": m["severity"],
                "severity_label": label,
                "severity_order": order,
                "example": m.get("example"),
                "note": m.get("note", ""),
                "trace_ids": m["trace_ids"],
            }
        )
    rows.sort(key=lambda r: (r["severity_order"], -r["count"]))
    return rows


def markdown(rows: list[dict], ids: list[str], sample: dict) -> str:
    n = len(ids)
    failures = sum(r["count"] for r in rows if r["severity"] != "none")
    out = [
        "# Failure taxonomy — claims assistant",
        "",
        f"20 traces, drawn at random with seed `{sample['seed']}` from a population of "
        f"{sample['population']}. {failures} of {n} showed a failure. Ranked by severity "
        "first, then frequency: a mode that wrongly denies a claim outranks a more common "
        "mode that only costs the adjuster a minute.",
        "",
        "| Mode | Count | % of 20 | Severity | Example trace_id |",
        "| ---- | ----: | ------: | -------- | ---------------- |",
    ]
    for r in rows:
        out.append(
            f"| {r['name']} | {r['count']} | {r['pct']}% | {r['severity_label']} | "
            f"`{r['example'] or '—'}` |"
        )
    out += [
        "",
        f"_Sample: seed `{sample['seed']}`, n={sample['n']}, population {sample['population']} "
        f"(sha `{sample['population_sha']}`). Every sampled trace is in exactly one row._",
    ]
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write taxonomy.md")
    ap.add_argument("--out", default=str(config.ROOT / "taxonomy.md"))
    a = ap.parse_args()

    modes = load_modes()
    ids = sample_ids()
    problems = validate(modes, ids)
    if problems:
        print("TAXONOMY NOT VALID:")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)

    rows = build(modes, ids)
    sample = json.loads(config.SAMPLE_FILE.read_text())
    md = markdown(rows, ids, sample)
    print(md)
    if a.write:
        from pathlib import Path

        Path(a.out).write_text(md + "\n")
        print(f"\n-> {Path(a.out).relative_to(config.ROOT)}")
