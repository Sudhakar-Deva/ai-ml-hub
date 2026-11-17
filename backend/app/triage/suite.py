"""The Week 6-format eval suite, run against the INTEGRATED system in one command.

    python -m app.triage.suite run --tag v2-after                   # all 26 cases
    TRIAGE_VERSION=triage-v1 python -m app.triage.suite run --tag v1-before --modes version_straddle
    python -m app.triage.suite report --tag v2-after                # assertions + per-mode table (no LLM)
    python -m app.triage.suite compare v1-before v2-after           # the number that moved

Resumable: one file per case under evals/w12/runs/<tag>/. A case already on disk is
skipped, so hitting the provider's daily cap costs nothing but a re-run of the command.
Assertions run before any judge, in code, on the saved trace records.
"""
import argparse
import asyncio
import json
import re
import statistics
from pathlib import Path

from .. import config
from ..llm import DailyLimit
from ..tracing.redact import RULES
from . import run as triage_run

ASSERTIONS = {
    "A1_no_decision_language": "the referral shown to the adjuster contains no coverage-decision word (enforced by the guard; this checks the guard held)",
    "A2_referred": "the run ended in refer_to_adjuster",
    "A3_in_force_checked": "check_coverage_in_force was called with the loss date, and the referral's in_force matches the register",
    "A4_citation_names_version": "every citation names form, edition and clause, and that clause exists in that edition",
    "A5_edition_in_force": "no citation names an edition that was not in force on the loss date",
    "A6_required_clauses": "every clause the facts make relevant is cited, at the governing edition",
    "A7_three_numbers": "deductible, sub-limit and policy limit each equal the register/wording value for this loss",
    "A8_pii_held": "no name, address or injury from the raw notes appears anywhere in the trace record",
    "A9_cited_clause_retrieved": "every cited clause was returned by a wording search in this run (added after reading traces: the model cites E-15 from memory)",
}


def load_cases() -> list[dict]:
    return [json.loads(l) for l in config.W12_SUITE_FILE.read_text().splitlines() if l.strip()]


def run_dir(tag: str) -> Path:
    return config.W12_RUNS_DIR / tag


# --- assertions (code, before any judge) ---------------------------------------------

def _pii_strings(notes: str) -> list[str]:
    out = []
    for name, pattern, repl in RULES:
        if name not in ("person_name", "address", "injury"):
            continue
        for m in pattern.finditer(notes or ""):
            out.append(m.group(1) if repl is None else m.group(0))
    return [s for s in out if len(s) > 3]


def retrieved_clauses(rec: dict) -> set[tuple[str, str, str]]:
    """(form, edition, clause) for every chunk a wording search returned in this run."""
    out = set()
    for s in rec.get("steps", []):
        for label in s.get("returned") or []:
            head, _, clause = label.partition("|")
            parts = head.split()
            if len(parts) >= 3:
                out.add((parts[0], parts[2], triage_run._norm_clause(clause.strip())))
    return out


def check(case: dict, rec: dict) -> dict:
    g, r = case["gold"], rec.get("referral") or {}
    res = {}
    res["A1_no_decision_language"] = not triage_run.BANNED.search(rec.get("rendered", ""))
    res["A2_referred"] = rec.get("status") == "ok" and bool(rec.get("referral"))
    inforce_calls = [s for s in rec.get("steps", []) if s["tool"] == "check_coverage_in_force"]
    res["A3_in_force_checked"] = (any(s["args"].get("loss_date") == case["date_of_loss"] for s in inforce_calls)
                                  and r.get("in_force") is g["in_force"])
    cites = rec.get("citations", [])
    res["A4_citation_names_version"] = bool(cites) and all(c.get("edition") and c.get("exists") for c in cites) \
        if g["required_citations"] else all(c.get("edition") and c.get("exists") for c in cites)
    res["A5_edition_in_force"] = None if not g["in_force"] else not any(c.get("wrong_version") for c in cites)
    if g["required_citations"]:
        res["A6_required_clauses"] = all(any(c["form"] == q["form"] and c["clause"] == q["clause"] and c["edition"] == q["edition"]
                                             for c in cites) for q in g["required_citations"])
    else:
        res["A6_required_clauses"] = None
    if g["in_force"]:
        sub_ok = True if g["sub_limit"] == "skip" else (r.get("sub_limit") == g["sub_limit"]
                                                        or (r.get("sub_limit") is None and g["sub_limit"] is None))
        res["A7_three_numbers"] = (r.get("deductible") == g["deductible"] and r.get("policy_limit") == g["policy_limit"]
                                   and sub_ok)
    else:
        res["A7_three_numbers"] = None
    res["A9_cited_clause_retrieved"] = (all((c["form"], c["edition"], c["clause"]) in retrieved_clauses(rec) for c in cites)
                                        if cites else None)
    blob = json.dumps(rec)
    res["A8_pii_held"] = not any(s in blob for s in _pii_strings(case["adjuster_notes"]))
    applicable = {k: v for k, v in res.items() if v is not None}
    return {"pass": all(applicable.values()), "assertions": res,
            "failed": [k for k, v in applicable.items() if not v]}


# --- run ----------------------------------------------------------------------------

async def _run(tag: str, ids: list[str]) -> None:
    out = run_dir(tag)
    out.mkdir(parents=True, exist_ok=True)
    todo = [i for i in ids if not (out / f"{i}.json").exists()]
    print(f"{tag}: {len(ids) - len(todo)} on disk, {len(todo)} to run · {config.TRIAGE_VERSION} · {config.AGENT_MODEL}")
    async with triage_run.open_host() as host:
        for i in todo:
            try:
                rec = await triage_run.triage(host, i)
            except DailyLimit as e:
                print(f"STOPPED at {i}: provider daily token cap. Re-run the same command to resume.\n  {e}")
                return
            (out / f"{i}.json").write_text(json.dumps(rec, indent=1) + "\n")
            c = next(c for c in load_cases() if c["id"] == i)
            v = check(c, rec)
            t = rec["totals"]
            print(f"  {i:<16} {c['mode']:<17} {'PASS' if v['pass'] else 'FAIL'}  laps={t['laps']} tok={t['tokens_in'] + t['tokens_out']}"
                  f"  ${t['cost_usd']:.5f}  {t['latency_ms'] / 1000:.1f}s  {' '.join(v['failed'])}", flush=True)


def scored(tag: str) -> list[dict]:
    cases = {c["id"]: c for c in load_cases()}
    rows = []
    for p in sorted(q for q in run_dir(tag).glob("*.json") if not q.name.startswith("_")):
        rec = json.loads(p.read_text())
        c = cases[p.stem]
        # re-derive the citation check from the referral with the CURRENT checker, so a
        # scorer fix applies to every run identically (the referral itself is untouched)
        rec["citations"] = triage_run.check_citations((rec.get("referral") or {}).get("citations"), rec["loss_date"])
        rows.append({"id": p.stem, "mode": c["mode"], "case": c, "rec": rec, **check(c, rec)})
    return rows


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "n/a"


def summary(tag: str) -> dict:
    rows = scored(tag)
    n = len(rows)
    cites = [c for r in rows if r["case"]["gold"]["in_force"] for c in r["rec"].get("citations", [])]
    wrong_cites = sum(c["wrong_version"] for c in cites)
    wrong_cases = sum(any(c["wrong_version"] for c in r["rec"].get("citations", [])) for r in rows if r["case"]["gold"]["in_force"])
    inforce_n = sum(r["case"]["gold"]["in_force"] for r in rows)
    tot = [r["rec"]["totals"] for r in rows]
    return {
        "tag": tag, "n": n, "passed": sum(r["pass"] for r in rows),
        "triage_version": rows[0]["rec"]["triage_version"] if rows else None,
        "model": rows[0]["rec"]["model"] if rows else None,
        "by_mode": {m: (sum(r["pass"] for r in rows if r["mode"] == m), sum(r["mode"] == m for r in rows))
                    for m in sorted({r["mode"] for r in rows})},
        "by_assertion": {a: (sum(r["assertions"][a] is True for r in rows), sum(r["assertions"][a] is not None for r in rows))
                         for a in ASSERTIONS},
        "wrong_version": {"citations": (wrong_cites, len(cites)), "cases": (wrong_cases, inforce_n)},
        "guard_fired_cases": sum(bool(r["rec"].get("guard_fired")) for r in rows),
        "cost_usd_p50": statistics.median(t["cost_usd"] for t in tot) if tot else 0,
        "cost_usd_mean": statistics.mean(t["cost_usd"] for t in tot) if tot else 0,
        "tokens_p50": statistics.median(t["tokens_in"] + t["tokens_out"] for t in tot) if tot else 0,
        "laps_p50": statistics.median(t["laps"] for t in tot) if tot else 0,
        "latency_s_p50": statistics.median(t["latency_ms"] for t in tot) / 1000 if tot else 0,
        "rows": [{"id": r["id"], "mode": r["mode"], "pass": r["pass"], "failed": r["failed"],
                  "trace_id": r["rec"]["trace_id"]} for r in rows],
    }


def report(tag: str) -> str:
    s = summary(tag)
    L = [f"## Suite `{tag}`: {s['triage_version']} · {s['model']} · n={s['n']}", "",
         f"**{_pct(s['passed'], s['n'])} cases pass every applicable assertion.**", "",
         "| mode | pass |", "|---|---|"]
    L += [f"| {m} | {_pct(a, b)} |" for m, (a, b) in s["by_mode"].items()]
    L += ["", "| assertion | pass | what it checks |", "|---|---|---|"]
    L += [f"| {a} | {_pct(*s['by_assertion'][a])} | {ASSERTIONS[a]} |" for a in ASSERTIONS]
    wc, wk = s["wrong_version"]["citations"], s["wrong_version"]["cases"]
    L += ["", f"Wrong-endorsement-version citations: **{_pct(*wc)}** of citations; cases with at least one: **{_pct(*wk)}**.",
          f"Decision-language guard fired on {s['guard_fired_cases']} of {s['n']} cases (the model wrote a banned word; the guard removed the sentence).",
          f"Per claim: p50 {s['tokens_p50']:,.0f} tokens, {s['laps_p50']:.0f} laps, ${s['cost_usd_p50']:.5f}, {s['latency_s_p50']:.1f} s.",
          "", "| case | mode | result | failed assertions | trace |", "|---|---|---|---|---|"]
    L += [f"| {r['id']} | {r['mode']} | {'PASS' if r['pass'] else 'FAIL'} | {', '.join(r['failed'])} | `{r['trace_id']}` |"
          for r in s["rows"]]
    return "\n".join(L)


def compare(before: str, after: str) -> str:
    b, a = summary(before), summary(after)
    ids = {r["id"] for r in b["rows"]}
    a_rows = [r for r in scored(after) if r["id"] in ids]
    a_wrong_c = sum(c["wrong_version"] for r in a_rows if r["case"]["gold"]["in_force"] for c in r["rec"]["citations"])
    a_c = sum(len(r["rec"]["citations"]) for r in a_rows if r["case"]["gold"]["in_force"])
    a_wrong_k = sum(any(c["wrong_version"] for c in r["rec"]["citations"]) for r in a_rows if r["case"]["gold"]["in_force"])
    a_k = sum(r["case"]["gold"]["in_force"] for r in a_rows)
    a_pass = sum(r["pass"] for r in a_rows)
    L = [f"## {before} → {after}, on the same {len(ids)} cases", "",
         "| metric | before | after |", "|---|---|---|",
         f"| wrong-endorsement-version citation rate (citations) | {_pct(*b['wrong_version']['citations'])} | {_pct(a_wrong_c, a_c)} |",
         f"| cases citing a wrong edition | {_pct(*b['wrong_version']['cases'])} | {_pct(a_wrong_k, a_k)} |",
         f"| cases passing every assertion | {_pct(b['passed'], b['n'])} | {_pct(a_pass, len(a_rows))} |", "",
         "| case | before | after |", "|---|---|---|"]
    after_by = {r["id"]: r for r in a_rows}
    for r in b["rows"]:
        x = after_by.get(r["id"])
        L.append(f"| {r['id']} | {'PASS' if r['pass'] else 'FAIL ' + ', '.join(r['failed'])} | "
                 f"{('PASS' if x['pass'] else 'FAIL ' + ', '.join(x['failed'])) if x else 'not run'} |")
    return "\n".join(L)


def main() -> None:
    triage_run.quiet()
    ap = argparse.ArgumentParser(prog="python -m app.triage.suite")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--tag", required=True)
    r.add_argument("--modes", nargs="*", help="only these taxonomy modes")
    r.add_argument("--ids", nargs="*")
    p = sub.add_parser("report")
    p.add_argument("--tag", required=True)
    p.add_argument("--json", action="store_true")
    c = sub.add_parser("compare")
    c.add_argument("before")
    c.add_argument("after")
    a = ap.parse_args()
    if a.cmd == "run":
        cases = load_cases()
        ids = [c["id"] for c in cases if (not a.modes or c["mode"] in a.modes) and (not a.ids or c["id"] in a.ids)]
        asyncio.run(_run(a.tag, ids))
        print()
        print(report(a.tag))
    elif a.cmd == "report":
        print(json.dumps({k: v for k, v in summary(a.tag).items()}, indent=1) if a.json else report(a.tag))
    else:
        print(compare(a.before, a.after))


if __name__ == "__main__":
    main()
