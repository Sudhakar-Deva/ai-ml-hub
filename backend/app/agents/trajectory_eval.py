"""Week 8: score the PATH, not just the payout.

    python -m app.agents.trajectory_eval run --tag before              # 10 claims, LLM
    python -m app.agents.trajectory_eval run --tag after --mitigation <name>
    python -m app.agents.trajectory_eval score --tag before            # offline, re-scorable
    python -m app.agents.trajectory_eval compare before after          # regression table

`run` saves every agent record (with its step-by-step trajectory) to
evals/w8/runs/<tag>.jsonl. Everything else is pure scoring over that file, so a
change to the scorer never needs another paid run and never changes the runs.

A claim passes the OUTCOME eval when contract.grade() passes it: decision, codes
and payable amount. It passes the TRAJECTORY eval only when it also has none of
the failure modes in MODES:
  - its tool sequence is one of the accepted paths in EXPECTED (a set, not one
    sequence, wherever more than one path is legitimate)
  - every argument it sent was real, meaning the right claim number and the claim's
    policy line, and an excess or limit it had actually read
  - every exclusion code it cited exists for that policy line AND was in a search
    result it received
  - the clause the decision turns on (`must_see`) was actually retrieved
"""
import argparse
import json
import re
import statistics
from datetime import datetime, timezone
from functools import lru_cache

from .. import config
from .budget import Budget
from .contract import grade
from .runlog import RunLog
from .tools import CLAIM_STATUSES, _claims, compute_payout, search_policy

G, S, P = "get_claim", "search_policy", "compute_payout"

# --- 1. the expected tool sequences -----------------------------------------
#
# Why the accepted sets look like this:
#   * The claim file is the only source of the policy line and the notes, so
#     get_claim is always first. Every decided claim ends in compute_payout,
#     because contract rule 5 says payable_amount comes from compute_payout,
#     and that includes a DENIED 0.
#   * ALTERNATE PATH, one vs two searches. The agent writes its own queries and
#     Week 7 measured that a notes-worded query misses the governing clause on
#     10001 (E-17) and 10002 (E-15). A reformulated second search is correct
#     behaviour, not waste, so G>S>S>P is accepted beside G>S>P on every
#     decided claim. A third search is not accepted, except on 10005.
#   * ALTERNATE PATH, 10005. It needs two different things from CO-0715: the
#     coverage grant with its own $250 deductible, and the exclusions (E-31 and
#     E-34 are the ones the notes rule out). Finding them in one, two or three
#     searches, in either order, are all correct, so the evidence is asserted
#     as a SET (`must_see`) and never as a search order.
#   * ALTERNATE PATH, 10009. It has no notes, so rule 4 makes it UNDETERMINED
#     with payable 0. Stopping after get_claim and calling
#     compute_payout("undetermined") both honour the rules. A search is not
#     accepted: no wording can settle a loss nobody has described.
#   * The order of the evidence is never asserted. `must_see` is a set of clause
#     groups; each group is satisfied by ANY retrieved clause in it.
#
# must_see entries are (form, clause-heading regex). A group is a tuple of them.
TWO_WAYS = frozenset({(G, S, P), (G, S, S, P)})

EXPECTED = {
    "CLM-2026-10001": {"paths": TWO_WAYS, "why": "clean burst: E-17 is where HO-0304 says a sudden burst is NOT excluded",
                       "must_see": [(("HO-0304", r"E-17\b"),)]},
    "CLM-2026-10002": {"paths": TWO_WAYS, "why": "river overtopped its bank: flood",
                       "must_see": [(("HO-0304", r"E-15\b"),)]},
    "CLM-2026-10003": {"paths": TWO_WAYS, "why": "3 weeks of weeping: the 14-day seepage clause",
                       "must_see": [(("HO-0304", r"E-19\b"),)]},
    "CLM-2026-10004": {"paths": TWO_WAYS, "why": "dwelling-fire form excludes ALL supply-line bursts",
                       "must_see": [(("DP-0110", r"E-17\b"),)]},
    "CLM-2026-10005": {"paths": frozenset({(G, S, P), (G, S, S, P), (G, S, S, S, P)}),
                       "why": "loss assessment: $250 form deductible, and the exclusions checked before paying",
                       "must_see": [(("CO-0715", r"LOSS ASSESSMENT COVERAGE"),),
                                    (("CO-0715", r"EXCLUSIONS APPLICABLE"),)]},
    "CLM-2026-10006": {"paths": TWO_WAYS, "why": "assessment funds the association's deductible",
                       "must_see": [(("CO-0715", r"E-31\b"),)]},
    "CLM-2026-10007": {"paths": TWO_WAYS, "why": "sewer backup",
                       "must_see": [(("HO-0304", r"E-20\b"),)]},
    "CLM-2026-10008": {"paths": TWO_WAYS, "why": "jewelry theft: $2,500 special limit",
                       "must_see": [(("HO-0521", r"^B\. Other special limits"),)]},
    "CLM-2026-10009": {"paths": frozenset({(G,), (G, P)}), "why": "no notes: UNDETERMINED, nothing to look up",
                       "must_see": []},
    "CLM-2026-10010": {"paths": TWO_WAYS, "why": "association never maintained the riser",
                       "must_see": [(("CO-0715", r"E-33\b"),)]},
}

# --- 2. the failure-mode taxonomy (the Week 8 zoo, as this agent shows it) ---
MODES = {
    "hallucinated_tool":   "called a tool that does not exist (gpt-oss: a tool named 'json')",
    "skipped_evidence":    "decided without ever retrieving the clause the decision turns on",
    "missing_step":        "a tool every accepted path calls was never called (no search / no payout)",
    "extra_steps":         "more calls than the longest accepted path, or the same call repeated",
    "out_of_order":        "right tools, wrong order (e.g. payout before the policy was read)",
    "invalid_argument":    "a tool argument that is not real: wrong claim number / policy line, "
                           "an excess or limit it never read, a tool error",
    "fabricated_citation": "cited an exclusion code that does not exist on this line or was never retrieved",
    "contradicts_tool":    "final decision or amount disagrees with the compute_payout call it made",
    "budget_exhausted":    "terminated by one of the four budgets",
    "no_contract":         "final reply was not a parseable contract object",
}


# --- the corpus: which exclusion codes really exist on which policy line -----

@lru_cache
def real_codes() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for f in config.DOCS_DIR.glob("*-ed-*.md"):
        text = f.read_text()
        m = re.search(r"^Policy_line:\s*(\w+)", text, re.M)
        if m:
            out.setdefault(m.group(1), set()).update(re.findall(r"^\|\s*(E-\d+)\s*\|", text, re.M))
    return out


def _norm_code(c) -> str:
    return str(c).strip().upper().replace("‑", "-")


def _codes_in(clause: str) -> set[str]:
    return set(re.findall(r"\bE-\d+\b", clause))


# --- 3. scoring one run -------------------------------------------------------

def _lcs(a: tuple, b: tuple) -> int:
    t = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            t[i + 1][j + 1] = t[i][j] + 1 if x == y else max(t[i][j + 1], t[i + 1][j])
    return t[-1][-1]


def score_run(r: dict) -> dict:
    cn = r["claim_number"]
    exp = EXPECTED[cn]
    claim = _claims()[cn]
    path = tuple(r["path"])
    steps = r.get("steps") or []
    out = r.get("output") or {}
    accepted = exp["paths"]

    # tool choice: align to the closest accepted path; a call that aligns is a
    # right choice, and an omitted or surplus call counts against it.
    best = max(accepted, key=lambda p: (_lcs(path, p), -abs(len(p) - len(path))))
    right = _lcs(path, best)
    choice_den = max(len(path), len(best))
    needed = min(len(p) for p in accepted)

    # arguments: each checked against what was real AT THAT POINT in the run
    checks, seen_clauses, seen_amounts, payout = [], [], set(), None
    claim_amounts = {float(claim["claimed_amount"])} | {
        float(x.replace(",", "")) for x in re.findall(r"\$\s?([\d,]+(?:\.\d+)?)", claim.get("adjuster_notes") or "")}
    for st in steps:
        a, t = st.get("args") or {}, st["tool"]
        if st.get("error"):
            checks.append((f"{t} error", False, st["error"]))
        if t == G:
            checks.append(("get_claim.claim_number", a.get("claim_number") == cn, a.get("claim_number")))
        elif t == S:
            checks.append(("search_policy.policy_line", a.get("policy_line") == claim["policy_line"],
                           f"{a.get('policy_line')} (claim is {claim['policy_line']})"))
            seen_clauses += st.get("clauses", [])
            seen_amounts |= set(st.get("amounts", []))
        elif t == P:
            ex, lim, cov = a.get("excess"), a.get("special_limit"), a.get("covered_amount")
            real_excess = {float(claim["policy_excess"])} | seen_amounts
            checks.append(("compute_payout.claim_status", a.get("claim_status") in CLAIM_STATUSES,
                           a.get("claim_status")))
            if a.get("claim_status") in ("covered", "partial"):
                checks.append(("compute_payout.excess", _num(ex) in real_excess,
                               f"{ex} (claim file / retrieved: {sorted(real_excess)})"))
                checks.append(("compute_payout.special_limit", lim is None or _num(lim) in seen_amounts,
                               f"{lim} (retrieved: {sorted(seen_amounts)})"))
                # the covered amount is a figure off the claim file (the claimed total,
                # or a line of the estimate in the notes), never a limit read elsewhere
                checks.append(("compute_payout.covered_amount", _num(cov) in claim_amounts,
                               f"{cov} (claim file: {sorted(claim_amounts)})"))
            payout = (a, st) if not st.get("error") else payout
    if out:
        checks.append(("output.claim_number", out.get("claim_number") == cn, out.get("claim_number")))

    # does the answer agree with the arithmetic the agent itself asked for?
    contradicts = []
    if out and payout:
        a = payout[0]
        tool_amt = compute_payout(**{k: a.get(k) for k in ("claim_status", "covered_amount", "excess", "special_limit")}
                                  ).get("payable_amount") if a.get("claim_status") in CLAIM_STATUSES else None
        if str(a.get("claim_status")).upper() != str(out.get("decision")).upper():
            contradicts.append(f"compute_payout said {a.get('claim_status')}, answer says {out.get('decision')}")
        if tool_amt is not None and abs((_num(out.get("payable_amount")) or 0) - tool_amt) > 1:
            contradicts.append(f"compute_payout returned {tool_amt}, answer says {out.get('payable_amount')}")

    # citations: does the code exist on this line, and was it ever in front of the agent?
    retrieved_codes = set().union(*(_codes_in(c) for c in seen_clauses)) if seen_clauses else set()
    cites = []
    for c in out.get("exclusion_codes") or []:
        c = _norm_code(c)
        real = c in real_codes().get(claim["policy_line"], set())
        cites.append((c, real and c in retrieved_codes,
                      "ok" if real and c in retrieved_codes else ("not on this line" if not real else "never retrieved")))

    # evidence: was the clause the decision turns on ever retrieved?
    def hit(group):
        return any(c.split(" | ")[0] == form and re.search(rx, c.split(" | ", 1)[1])
                   for c in seen_clauses for form, rx in group)
    missing_evidence = [g for g in exp["must_see"] if not hit(g)]

    modes = set()
    if any(t not in (G, S, P) for t in path):
        modes.add("hallucinated_tool")
    if r["status"] == "budget_exhausted":
        modes.add("budget_exhausted")
    if r["status"] == "no_contract":
        modes.add("no_contract")
    if r["status"] == "ok" and missing_evidence:
        modes.add("skipped_evidence")
    # structure is judged on the real tools; a call to a tool that does not exist
    # is its own mode above, not also a missing, surplus or misordered step
    real_path = tuple(t for t in path if t in (G, S, P))
    if real_path not in accepted:
        min_s = min(p.count(S) for p in accepted)
        required = set.intersection(*(set(p) for p in accepted))
        real_steps = [s for s in steps if s["tool"] in (G, S, P)]
        dup = len({json.dumps([s["tool"], s["args"]], sort_keys=True) for s in real_steps}) < len(real_steps)
        if any(t not in real_path for t in required) or real_path.count(S) < min_s:
            modes.add("missing_step")
        if len(real_path) > max(len(p) for p in accepted) or dup:
            modes.add("extra_steps")
        if not modes & {"missing_step", "extra_steps", "budget_exhausted", "no_contract"}:
            modes.add("out_of_order")
    if not all(ok for _, ok, _ in checks):
        modes.add("invalid_argument")
    if not all(ok for _, ok, _ in cites):
        modes.add("fabricated_citation")
    if contradicts:
        modes.add("contradicts_tool")

    outcome_ok, why = grade(r.get("output"), claim["gold"])
    arg_total = len(checks) + len(cites)
    return {
        "claim_number": cn,
        "class": claim["class"],
        "path": ">".join(path) or "(none)",
        "accepted": sorted(">".join(p) for p in accepted),
        "outcome_pass": outcome_ok,
        "outcome_why": "; ".join(why),
        "trajectory_pass": outcome_ok and not modes,
        "modes": sorted(modes),
        "tool_choice": (right, choice_den),
        "args": (sum(ok for _, ok, _ in checks) + sum(ok for _, ok, _ in cites), arg_total),
        "bad_args": [f"{n}={v}" for n, ok, v in checks if not ok] + [f"cited {c}: {v}" for c, ok, v in cites if not ok]
                    + contradicts,
        "steps_taken": len(path),
        "steps_needed": needed,
        "missing_evidence": [" or ".join(f"{f} {rx}" for f, rx in g) for g in missing_evidence],
        "cost_usd": r["cost_usd"],
        "tokens": r["tokens"],
        "laps": r["iters"],
        "latency_net_ms": r["latency_ms"] - r.get("rate_wait_ms", 0.0),
    }


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# --- 4. the numbers -----------------------------------------------------------

def _p(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(q * (len(xs) - 1)))]


def summarise(scored: list[dict]) -> dict:
    n = len(scored)
    tc = [s["tool_choice"] for s in scored]
    av = [s["args"] for s in scored]
    cost = [s["cost_usd"] for s in scored]
    return {
        "runs": n,
        "outcome_pass_rate": sum(s["outcome_pass"] for s in scored) / n,
        "trajectory_pass_rate": sum(s["trajectory_pass"] for s in scored) / n,
        "tool_choice_accuracy": sum(a for a, _ in tc) / sum(b for _, b in tc),
        "arg_validity_rate": sum(a for a, _ in av) / max(1, sum(b for _, b in av)),
        "arg_counts": (sum(a for a, _ in av), sum(b for _, b in av)),
        "step_efficiency": sum(s["steps_taken"] for s in scored) / sum(s["steps_needed"] for s in scored),
        "step_eff_max": max(s["steps_taken"] / s["steps_needed"] for s in scored),
        "cost_p50": statistics.median(cost),
        "cost_max": max(cost),
        "cost_mean": statistics.mean(cost),
        "tokens_p50": statistics.median(s["tokens"] for s in scored),
        "tokens_max": max(s["tokens"] for s in scored),
        "laps_p50": statistics.median(s["laps"] for s in scored),
        "laps_max": max(s["laps"] for s in scored),
        "latency_p50_ms": statistics.median(s["latency_net_ms"] for s in scored),
        "latency_max_ms": max(s["latency_net_ms"] for s in scored),
        "modes": {m: sum(m in s["modes"] for s in scored) for m in MODES},
    }


def load_runs(tag: str) -> list[dict]:
    f = config.W8_RUNS_DIR / f"{tag}.jsonl"
    return [json.loads(line) for line in f.read_text().splitlines() if line.strip()]


def report(tag: str) -> str:
    runs = load_runs(tag)
    scored = [score_run(r) for r in runs]
    m = summarise(scored)
    L = [f"# Trajectory eval: `{tag}`",
         "",
         f"{m['runs']} runs · model `{runs[0].get('model', config.AGENT_MODEL)}` · "
         f"mitigation `{runs[0].get('mitigation') or 'none'}` · "
         f"generated by `python -m app.agents.trajectory_eval score --tag {tag}`",
         "",
         "## Results",
         "",
         "| metric | value |",
         "|---|---|",
         f"| outcome pass rate | {m['outcome_pass_rate']:.0%} ({sum(s['outcome_pass'] for s in scored)}/{m['runs']}) |",
         f"| trajectory pass rate | {m['trajectory_pass_rate']:.0%} ({sum(s['trajectory_pass'] for s in scored)}/{m['runs']}) |",
         f"| **outcome − trajectory gap** | **{(m['outcome_pass_rate'] - m['trajectory_pass_rate']) * 100:+.0f} pts** |",
         f"| tool-choice accuracy | {m['tool_choice_accuracy']:.1%} "
         f"({sum(a for a, _ in (s['tool_choice'] for s in scored))}/{sum(b for _, b in (s['tool_choice'] for s in scored))} calls) |",
         f"| argument validity rate | {m['arg_validity_rate']:.1%} ({m['arg_counts'][0]}/{m['arg_counts'][1]} args) |",
         f"| step efficiency (taken / needed) | {m['step_efficiency']:.2f} (worst claim {m['step_eff_max']:.2f}) |",
         f"| cost / claim p50 · **max** | ${m['cost_p50']:.5f} · **${m['cost_max']:.5f}** (mean ${m['cost_mean']:.5f}) |",
         f"| tokens / claim p50 · max | {m['tokens_p50']:,.0f} · {m['tokens_max']:,} |",
         f"| laps / claim p50 · max | {m['laps_p50']:.0f} · {m['laps_max']} |",
         f"| latency / claim p50 · max (net of 429 sleeps) | {m['latency_p50_ms'] / 1000:.1f} s · {m['latency_max_ms'] / 1000:.1f} s |",
         "",
         "## Per claim",
         "",
         "| claim | class | path taken | accepted | outcome | trajectory | modes | bad args / missing evidence | $ |",
         "|---|---|---|---|---|---|---|---|---|"]
    for s in scored:
        L.append(f"| {s['claim_number'][-5:]} | {s['class']} | `{s['path']}` | {' / '.join(f'`{p}`' for p in s['accepted'])} "
                 f"| {'PASS' if s['outcome_pass'] else 'FAIL'} | {'PASS' if s['trajectory_pass'] else 'FAIL'} "
                 f"| {', '.join(s['modes']) or '—'} | {'; '.join(s['bad_args'] + ['not retrieved: ' + e for e in s['missing_evidence']]) or '—'} "
                 f"| {s['cost_usd']:.5f} |")
    L += ["", "## Failure modes", "", "| mode | runs | what it means |", "|---|---|---|"]
    for k, v in sorted(m["modes"].items(), key=lambda x: -x[1]):
        L.append(f"| {k} | {v} | {MODES[k]} |")

    gap_cases = [(s, r) for s, r in zip(scored, runs) if s["outcome_pass"] and not s["trajectory_pass"]]
    L += ["", f"## Right answer, wrong path ({len(gap_cases)})", ""]
    for s, r in gap_cases:
        L.append(f"### {s['claim_number']} ({s['class']}): {', '.join(s['modes'])}")
        L.append("")
        L.append("```")
        L.extend(trace_lines(r))
        L.append("```")
        L.append("")
    return "\n".join(L)


def trace_lines(r: dict) -> list[str]:
    out = []
    for st in r.get("steps") or []:
        out.append(f"lap {st['lap']}  {st['tool']}({json.dumps(st['args'])})"
                   + (f"  ERROR {st['error']}" if st.get("error") else ""))
        for c in st.get("clauses", []):
            out.append(f"          -> {c}")
    o = r.get("output") or {}
    out.append(f"final   {o.get('decision')}  codes={o.get('exclusion_codes')}  payable={o.get('payable_amount')}")
    out.append(f"        reason: {o.get('reason')}")
    return out


def compare(before: str, after: str) -> str:
    sb = [score_run(r) for r in load_runs(before)]
    sa = [score_run(r) for r in load_runs(after)]
    mb, ma = summarise(sb), summarise(sa)
    top = max(mb["modes"], key=lambda k: mb["modes"][k])
    L = [f"# Regression check: `{before}` -> `{after}`", "",
         "| mode | before | after | Δ | verdict |", "|---|---|---|---|---|"]
    for k in MODES:
        b, a = mb["modes"][k], ma["modes"][k]
        verdict = ("**TOP MODE, targeted**" if k == top else "") + (
            " **WORSE**" if a > b and b > 0 else " **NEW (created)**" if a > b else " better" if a < b else " unchanged")
        L.append(f"| {k} | {b} | {a} | {a - b:+d} | {verdict.strip()} |")
    L += ["", "| metric | before | after | Δ |", "|---|---|---|---|"]
    rows = [("outcome pass rate", "outcome_pass_rate", "{:.0%}"), ("trajectory pass rate", "trajectory_pass_rate", "{:.0%}"),
            ("tool-choice accuracy", "tool_choice_accuracy", "{:.1%}"), ("argument validity", "arg_validity_rate", "{:.1%}"),
            ("step efficiency", "step_efficiency", "{:.2f}"), ("cost / claim p50", "cost_p50", "${:.5f}"),
            ("cost / claim max", "cost_max", "${:.5f}"), ("cost / claim mean", "cost_mean", "${:.5f}"),
            ("tokens / claim p50", "tokens_p50", "{:,.0f}"), ("tokens / claim max", "tokens_max", "{:,.0f}"),
            ("laps / claim p50", "laps_p50", "{:.1f}"), ("latency p50 (net)", "latency_p50_ms", "{:,.0f} ms"),
            ("latency max (net)", "latency_max_ms", "{:,.0f} ms")]
    for label, k, fmt in rows:
        L.append(f"| {label} | {fmt.format(mb[k])} | {fmt.format(ma[k])} | {fmt.format(ma[k] - mb[k]) if '%' not in fmt else f'{(ma[k] - mb[k]) * 100:+.1f} pts'} |")
    gb = mb["outcome_pass_rate"] - mb["trajectory_pass_rate"]
    ga = ma["outcome_pass_rate"] - ma["trajectory_pass_rate"]
    L += ["", f"Gap (outcome − trajectory): {gb * 100:+.0f} pts -> {ga * 100:+.0f} pts",
          f"Top mode `{top}`: {mb['modes'][top]} -> {ma['modes'][top]}"]
    L += ["", "| claim | before path | before modes | after path | after modes |", "|---|---|---|---|---|"]
    for b, a in zip(sb, sa):
        L.append(f"| {b['claim_number'][-5:]} | `{b['path']}` | {', '.join(b['modes']) or '—'} "
                 f"| `{a['path']}` | {', '.join(a['modes']) or '—'} |")
    return "\n".join(L)


# --- 5. running ---------------------------------------------------------------

def run(tag: str, mitigation: str | None, claims: list[str] | None) -> None:
    from . import agent

    config.W8_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    f = config.W8_RUNS_DIR / f"{tag}.jsonl"
    done = {json.loads(x)["claim_number"] for x in f.read_text().splitlines() if x.strip()} if f.exists() else set()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log = RunLog(config.WEEK8_DIR / "logs" / f"{tag}_{ts}.log")
    search_policy("warm-up", "homeowners", 1)   # embedder load stays off the clock
    for cn in claims or list(EXPECTED):
        if cn in done:
            print(f"{cn}  already in {f.name}, skipped")
            continue
        r = agent.run(cn, Budget(wall_clock_s=config.W8_WALL_CLOCK_S), log, mitigation=mitigation)
        r.update(tag=tag, mitigation=mitigation, model=config.AGENT_MODEL, ts=ts)
        with f.open("a") as fh:          # one line per claim: a daily-cap abort keeps what finished
            fh.write(json.dumps(r) + "\n")
        s = score_run(r)
        print(f"== {cn}  outcome {'PASS' if s['outcome_pass'] else 'FAIL'}  trajectory "
              f"{'PASS' if s['trajectory_pass'] else 'FAIL'}  {s['path']}  {s['modes']}  ${r['cost_usd']:.5f}",
              flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--tag", required=True)
    r.add_argument("--mitigation", default=None)
    r.add_argument("--claims", nargs="*")
    s = sub.add_parser("score")
    s.add_argument("--tag", required=True)
    c = sub.add_parser("compare")
    c.add_argument("before")
    c.add_argument("after")
    a = ap.parse_args()

    config.WEEK8_DIR.mkdir(parents=True, exist_ok=True)
    if a.cmd == "run":
        run(a.tag, a.mitigation, a.claims)
        a.cmd = "score"
    if a.cmd == "score":
        text = report(a.tag)
        out = config.WEEK8_DIR / f"results_{a.tag}.md"
    else:
        text = compare(a.before, a.after)
        out = config.WEEK8_DIR / f"regression_{a.before}_vs_{a.after}.md"
    out.write_text(text + "\n")
    print(text)
    print(f"\n-> {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
