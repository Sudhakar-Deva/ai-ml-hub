"""The one command. Runs the whole eval and prints pass rate BY MODE.

    python -m app.evals.run --markdown                 # the table that gets graded
    python -m app.evals.run --judge v2 --markdown
    python -m app.evals.run --generate                 # write the summaries once

A case passes only if BOTH halves pass: every applicable deterministic assertion,
and the judge's single binary criterion. They are also reported separately,
because "the eval went from 68% to 72%" is useless if you cannot say whether a
format regression or a coverage regression moved it.

The table is broken out by mode and there is no overall-only view, on purpose.
One headline pass rate is how a regression on the mode that wrongly denies
claims gets carried by the mode that answers straightforward summaries. The
overall figure is printed last and labelled as the least informative row.

Summaries are generated ONCE and frozen. Re-running this does not re-generate
them: the hand labels are pinned to a sha of summaries.json, and regenerating
would silently invalidate every agreement number computed so far. `--regenerate`
exists and says so loudly.
"""
import argparse
import json
from collections import defaultdict

from .. import config
from . import assertions as asserts
from . import store
from .cases import check as check_cases
from .cases import load as load_cases


def generate(force: bool = False) -> dict:
    """Run the app over every case and freeze the summaries."""
    from ..generation.summarize import summarize

    if config.W6_SUMMARIES_FILE.exists() and not force:
        raise SystemExit(
            f"{config.W6_SUMMARIES_FILE.relative_to(config.ROOT)} already exists.\n"
            "Regenerating invalidates every hand label pinned to its sha. Pass "
            "--regenerate if that is genuinely what you want."
        )
    cases = load_cases()
    out = {}
    for i, c in enumerate(cases, start=1):
        r = summarize(c["notes"], source="eval-w6", case_id=c["id"])
        out[c["id"]] = {
            "summary": r["summary"],
            "retrieved": r["retrieved"],
            "citations": r["citations"],
            "unresolvable_citations": r["unresolvable_citations"],
            "trace_id": r["trace_id"],
            "latency_ms": r["latency_ms"],
        }
        print(f"  {i:3d}/{len(cases)}  {c['id']}  trace={r['trace_id']}  {c['mode']}")

    payload = {
        "generated_at": store.now(),
        "app_prompt_version": config.SUMMARY_PROMPT_VERSION,
        "model": config.LLM_MODEL,
        "strategy": "structure_aware",
        "retriever": config.SHIPPED_RETRIEVER,
        "k": config.TOP_K,
        "n": len(out),
        "summaries": out,
    }
    store.save_summaries(payload)
    print(f"\n-> {config.W6_SUMMARIES_FILE.relative_to(config.ROOT)}  sha {store.summaries_sha()}")
    return payload


def evaluate(judge_version: str, reuse_judge: bool, gate: bool) -> dict:
    from . import judge as judge_mod

    cases = load_cases()
    summaries = store.load_summaries()["summaries"]

    if reuse_judge:
        run = store.latest_run("judge", judge_version)
        if run is None:
            raise SystemExit(f"no cached judge run for {judge_version}")
        print(f"reusing judge run {judge_version} from {run['ran_at']}")
    else:
        run = judge_mod.run(judge_version, gate=gate)

    rows = []
    for c in cases:
        entry = summaries.get(c["id"])
        if entry is None:
            continue
        a = asserts.run(entry["summary"], c)
        v = run["verdicts"].get(c["id"], {})
        judged = v.get("verdict") == "PASS"
        rows.append(
            {
                "case_id": c["id"],
                "mode": c["mode"],
                "kind": c["kind"],
                "assertions_passed": a["passed"],
                "assertions_applicable": a["applicable"],
                "assertions_failed": a["failed"],
                "judge_verdict": v.get("verdict"),
                "judge_passed": judged,
                "judge_reason": v.get("reason"),
                "passed": a["passed"] and judged,
            }
        )
    return {"judge_version": judge_version, "judge_run": run, "rows": rows}


def by_mode(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for r in rows:
        groups[r["mode"]].append(r)
    out = []
    for mode, rs in groups.items():
        n = len(rs)
        out.append(
            {
                "mode": mode,
                "n": n,
                "regression_cases": sum(1 for r in rs if r["kind"] == "regression"),
                "assert_pass": sum(1 for r in rs if r["assertions_passed"]),
                "judge_pass": sum(1 for r in rs if r["judge_passed"]),
                "pass": sum(1 for r in rs if r["passed"]),
                "pass_pct": round(100 * sum(1 for r in rs if r["passed"]) / n, 1),
            }
        )
    out.sort(key=lambda r: (r["pass_pct"], -r["n"]))
    return out


def markdown(result: dict) -> str:
    rows = result["rows"]
    modes = by_mode(rows)
    n = len(rows)
    total = sum(1 for r in rows if r["passed"])
    run = result["judge_run"]

    out = [
        "### Week 6 eval — pass rate by mode",
        "",
        f"{n} cases · {sum(1 for r in rows if r['kind'] == 'regression')} replayed verbatim "
        f"from real failed traces · judge `{result['judge_version']}` "
        f"(prompt sha `{run['judge_prompt_sha']}`, model `{run['judge_model']}`) · "
        f"{asserts.ASSERTION_COUNT} deterministic assertions vs 1 judged criterion.",
        "",
        "A case passes only if every applicable assertion passes AND the judge returns PASS.",
        "",
        "| Mode | n | regressions | assertions | judge | pass | pass rate |",
        "| ---- | -: | ----------: | ---------: | ----: | ---: | --------: |",
    ]
    for m in modes:
        out.append(
            f"| {m['mode']} | {m['n']} | {m['regression_cases']} | {m['assert_pass']}/{m['n']} | "
            f"{m['judge_pass']}/{m['n']} | {m['pass']}/{m['n']} | **{m['pass_pct']}%** |"
        )
    out += [
        f"| _all cases (the least informative row)_ | {n} | | "
        f"{sum(1 for r in rows if r['assertions_passed'])}/{n} | "
        f"{sum(1 for r in rows if r['judge_passed'])}/{n} | {total}/{n} | "
        f"_{round(100 * total / n, 1)}%_ |",
        "",
        "#### Assertion failures",
        "",
    ]
    failed = [r for r in rows if r["assertions_failed"]]
    if not failed:
        out.append("_None — every applicable assertion passed on every case._")
    else:
        out += ["| Case | Mode | Failed |", "| ---- | ---- | ------ |"]
        for r in failed:
            out.append(f"| `{r['case_id']}` | {r['mode']} | {', '.join(r['assertions_failed'])} |")
    return "\n".join(out)


def table(result: dict) -> str:
    rows, modes = result["rows"], by_mode(result["rows"])
    n = len(rows)
    total = sum(1 for r in rows if r["passed"])
    w = max(len(m["mode"]) for m in modes)
    out = [
        f"{'MODE'.ljust(w)}    n  reg  assert  judge   pass    rate",
        "-" * (w + 42),
    ]
    for m in modes:
        out.append(
            f"{m['mode'].ljust(w)}  {m['n']:3d}  {m['regression_cases']:3d}  "
            f"{m['assert_pass']:3d}/{m['n']:<3d} {m['judge_pass']:3d}/{m['n']:<3d} "
            f"{m['pass']:3d}/{m['n']:<3d} {m['pass_pct']:6.1f}%"
        )
    out += [
        "-" * (w + 42),
        f"{'ALL (least informative)'.ljust(w)}  {n:3d}       "
        f"{sum(1 for r in rows if r['assertions_passed']):3d}/{n:<3d} "
        f"{sum(1 for r in rows if r['judge_passed']):3d}/{n:<3d} "
        f"{total:3d}/{n:<3d} {100 * total / n:6.1f}%",
    ]
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--generate", action="store_true", help="write summaries.json (once)")
    ap.add_argument("--regenerate", action="store_true", help="overwrite it — invalidates labels")
    ap.add_argument("--judge", default=config.JUDGE_DEFAULT, choices=config.JUDGE_VERSIONS)
    ap.add_argument("--reuse-judge", action="store_true", help="use the last cached judge run")
    ap.add_argument("--no-gate", dest="gate", action="store_false")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None, help="also write the markdown here")
    a = ap.parse_args()

    problems = check_cases()
    if problems:
        print("EVAL SET NOT VALID:")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)

    if a.generate or a.regenerate:
        generate(force=a.regenerate)
        raise SystemExit(0)

    result = evaluate(a.judge, a.reuse_judge, a.gate)
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        print()
        print(table(result))
    md = markdown(result)
    if a.markdown:
        print("\n" + md)
    if a.out:
        from pathlib import Path

        Path(a.out).write_text(md + "\n")
        print(f"\n-> {a.out}")
    store.save_run("eval", a.judge, {"ran_at": store.now(), **{k: v for k, v in result.items() if k != "judge_run"}})
