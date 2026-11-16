"""Slice the request log. The drill tool: no LLM, logs only.

    python -m app.obs.find                                   # everything, one line each
    python -m app.obs.find --day 2026-11-15 --position COVERED
    python -m app.obs.find --user ADJ-207 --from 13:00 --to 17:00
    python -m app.obs.find --prompt-version claims-summary-v1 --input-type condo
    python -m app.obs.find --cost-outlier                    # requests above p90 cost
    python -m app.obs.find --text "sewer|flood"              # regex over input AND output
    python -m app.obs.find --show req_ab12cd34ef56           # the full trace

Slices map to the brief: time (--day/--from/--to), user (--user), prompt version
(--prompt-version), input type (--input-type), cost outlier (--cost-outlier),
plus the output itself (--position, --text). Inputs and outputs are both searchable.
"""
import argparse
import json
import re
import statistics

from .app import read_all


def _p90(xs):
    xs = sorted(xs)
    return xs[max(0, int(0.9 * len(xs)) - 1)] if xs else 0


def select(rows, a):
    out = rows
    if a.day:
        out = [r for r in out if r["ts"].startswith(a.day)]
    if a.frm:
        out = [r for r in out if r["ts"][11:16] >= a.frm]
    if a.to:
        out = [r for r in out if r["ts"][11:16] <= a.to]
    if a.user:
        out = [r for r in out if r["user"] == a.user]
    if a.prompt_version:
        out = [r for r in out if r["prompt_version"] == a.prompt_version]
    if a.input_type:
        out = [r for r in out if a.input_type in r["input_type"]]
    if a.position:
        out = [r for r in out if (r["output"]["coverage_position"] or "").startswith(a.position.upper())]
    if a.text:
        rx = re.compile(a.text, re.I)
        out = [r for r in out if rx.search(r["input"]["notes"]) or rx.search(r["output"]["text"])]
    if a.cost_outlier:
        cut = _p90([r["totals"]["cost_usd"] for r in rows])
        out = [r for r in out if r["totals"]["cost_usd"] > cut]
    if getattr(a, "ignored_exclusions", False):
        out = [r for r in out if r.get("exclusions_retrieved_not_applied")]
    return out


def line(r) -> str:
    o = r["output"]
    excl = (o["exclusions_applied"] or "")[:18]
    extra = f"  ignored={r['exclusions_retrieved_not_applied']}" if r.get("exclusions_retrieved_not_applied") else ""
    return (f"{r['ts'][:16]}  {r['request_id']}  {r['user']}  {r['input_type']:<28} {r['prompt_version']:<18} "
            f"{(o['coverage_position'] or '?'):<13} excl={excl:<18} ${r['totals']['cost_usd']:.5f}{extra}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day")
    ap.add_argument("--from", dest="frm", help="HH:MM")
    ap.add_argument("--to", help="HH:MM")
    ap.add_argument("--user")
    ap.add_argument("--prompt-version")
    ap.add_argument("--input-type")
    ap.add_argument("--position", help="COVERED | DENIED | PARTIAL | UNDETERMINED")
    ap.add_argument("--text", help="regex over the (redacted) input notes and the output")
    ap.add_argument("--cost-outlier", action="store_true")
    ap.add_argument("--ignored-exclusions", action="store_true",
                    help="requests whose retrieved context held an exclusion the output did not apply")
    ap.add_argument("--show", help="print one request's full record")
    a = ap.parse_args()
    rows = read_all()
    if a.show:
        r = next((r for r in rows if r["request_id"] == a.show), None)
        print(json.dumps(r, indent=2, ensure_ascii=False) if r else f"no request {a.show}")
        return
    hits = select(rows, a)
    for r in hits:
        print(line(r))
    print(f"-- {len(hits)} of {len(rows)} requests")


if __name__ == "__main__":
    main()
