"""Assemble notes.md from the artifacts, never from memory.

    python -m app.tracing.notes --write

Everything in the output is read back out of a file that was produced by a run:
the seed and the 20 ids from week5/sample.json, the sentences from
week5/open_coding.jsonl, the replay evidence from week5/replay.json, the
prediction from week5/prediction.md. If a section is missing, it says so rather
than being quietly dropped — a gap you can see is worth more than a page that
looks complete.
"""
import argparse
import json
from datetime import datetime, timezone

from .. import config
from .trace import by_id, read_all

REPLAY_FILE = config.WEEK5_DIR / "replay.json"
PREDICTION_FILE = config.WEEK5_DIR / "prediction.md"
BENCHMARK_FILE = config.WEEK5_DIR / "benchmark_note.md"


def _read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def _read_text(path):
    return path.read_text().strip() if path.exists() else None


def _missing(what: str, how: str) -> str:
    return f"> **MISSING — {what}.** Produce it with:\n>\n> ```\n> {how}\n> ```"


def build() -> str:
    sample = _read_json(config.SAMPLE_FILE)
    coding = _read_json(config.CODING_FILE)
    replay = _read_json(REPLAY_FILE)
    prediction = _read_text(PREDICTION_FILE)
    benchmark = _read_text(BENCHMARK_FILE)
    traces = read_all()

    out = [
        "# Week 5 notes — error analysis on the claims assistant",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} from the "
        "artifacts in `week5/` and `traces/`. Nothing here is typed by hand into this file._",
        "",
        "---",
        "",
        "## 1. Redaction happens before the write",
        "",
    ]

    red_rules = sorted({r for t in traces for r in (t.get("redaction") or {}).get("rules_fired", [])})
    out += [
        "Claimant names and claim numbers are removed inside the trace writer, before the "
        "line is serialised — `tracing.write()` calls `redact_deep()` and there is no code "
        "path to the file handle that skips it. A trace file scrubbed afterwards has "
        "already existed unscrubbed on disk and in whatever backed it up.",
        "",
        f"- Traces written: **{len(traces)}**",
        f"- Redaction rules that fired across the log: "
        f"**{', '.join(red_rules) if red_rules else 'none — no identifiers appeared in this traffic'}**",
        "- Form numbers, edition dates and exclusion codes (`HO-0304`, `ed. 03-24`, `E-17`) "
        "are deliberately *not* redacted; they are corpus vocabulary, not identifiers. "
        "Pinned by `test_corpus_vocabulary_survives`.",
        "",
        "---",
        "",
        "## 2. The seeded random sample",
        "",
    ]

    if not sample:
        out.append(_missing("week5/sample.json", "python -m app.tracing.sample"))
    else:
        out += [
            f"- **Seed:** `{sample['seed']}`",
            f"- **n:** {sample['n']}",
            f"- **Population:** {sample['population']} traces"
            + (f" with `source={sample['source_filter']}`" if sample.get("source_filter") else ""),
            f"- **Population fingerprint:** `{sample['population_sha']}`",
            f"- **Drawn at:** {sample['drawn_at']}",
            "",
            "Redraw and verify:",
            "",
            "```",
            f"python -m app.tracing.sample --seed {sample['seed']} --n {sample['n']}"
            + (f" --source {sample['source_filter']}" if sample.get("source_filter") else ""),
            "```",
            "",
            "| # | trace_id | question |",
            "| - | -------- | -------- |",
        ]
        for i, tid in enumerate(sample["trace_ids"], start=1):
            t = by_id(tid)
            q = (t["question"][:88] + "…") if t and len(t["question"]) > 88 else (t or {}).get("question", "—")
            out.append(f"| {i} | `{tid}` | {q} |")

    out += ["", "---", "", "## 3. Replay evidence — one trace, from the trace alone", ""]
    if not replay:
        out.append(_missing(
            "week5/replay.json",
            "python -m app.tracing.replay <trace_id> --json > week5/replay.json",
        ))
    else:
        a = replay["audit"]
        out += [
            f"- **trace_id:** `{a['trace_id']}`",
            f"- **prompt version:** `{replay['prompt_version']}`",
            f"- **model / params:** `{replay['model']}` · `{replay['params']}`",
            f"- **replayable from the trace alone:** {a['replayable']}",
            f"- **outputs identical:** {replay['identical']} (similarity {replay['similarity']})",
            "",
        ]
        if a["missing_fields"]:
            out += ["**Fields that had to be added to make replay possible:**", ""]
            out += [f"- `{m['field']}` — {m['why_it_matters']}" for m in a["missing_fields"]]
            out.append("")
        else:
            out += [
                "No field had to be added: the trace schema was built with replay as the "
                "requirement, so prompt version, system prompt, rendered prompt, model, "
                "params, retrieved chunk_ids with scores, and raw output were all present "
                "on the first read.",
                "",
            ]
        if a["gaps"]:
            out += ["**What still cannot be reconstructed:**", ""] + [f"- {g}" for g in a["gaps"]] + [""]
        out += [
            "**Original output**", "", "```", replay["original"], "```", "",
            "**Replayed output**", "", "```", replay["replayed"], "```", "",
        ]
        if replay.get("diff"):
            out += ["**Diff**", "", "```diff", replay["diff"], "```", ""]

    out += ["", "---", "", "## 4. Open coding — one sentence per trace, what I saw", ""]
    if not coding or not coding.get("codes"):
        out.append(_missing(
            "week5/open_coding.jsonl",
            "python -m app.tracing.opencode --start\npython -m app.tracing.opencode --next",
        ))
    else:
        fp_start = coding.get("fingerprint_at_start")
        from .opencode import tree_fingerprint

        same = fp_start == tree_fingerprint()
        out += [
            f"Coding began {coding.get('started_at')} at `{coding.get('head_at_start')}`. "
            f"No code was changed while coding: the working-tree fingerprint at the start "
            f"(`{fp_start}`) still matches now — **{same}**. The tooling refuses sentences "
            "containing diagnosis words, so a category cannot be smuggled in as an observation.",
            "",
            "| # | trace_id | What I saw |",
            "| - | -------- | ---------- |",
        ]
        order = sample["trace_ids"] if sample else [c["trace_id"] for c in coding["codes"]]
        byid = {c["trace_id"]: c for c in coding["codes"]}
        for i, tid in enumerate(order, start=1):
            c = byid.get(tid)
            out.append(f"| {i} | `{tid}` | {c['sentence'] if c else '— not coded —'} |")

    out += ["", "---", "", "## 5. The dated prediction", ""]
    out.append(prediction or _missing("week5/prediction.md", "write it, then commit it"))

    out += ["", "---", "", "## 6. Why a public benchmark would have missed these", ""]
    out.append(benchmark or _missing("week5/benchmark_note.md", "write the 3 sentences"))

    return "\n".join(out) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--out", default=str(config.ROOT / "notes.md"))
    a = ap.parse_args()

    md = build()
    if a.write:
        from pathlib import Path

        Path(a.out).write_text(md)
        print(f"-> {Path(a.out).relative_to(config.ROOT)}  ({len(md.splitlines())} lines)")
    else:
        print(md)
