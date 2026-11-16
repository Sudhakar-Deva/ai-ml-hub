"""Week 10: race the squad against the single agent on the same 10 cases.

    python -m app.squad.race run                 # both arms, interleaved per claim (paid)
    python -m app.squad.race fail                # inject a 500 into the exclusions worker (paid, 1 claim)
    python -m app.squad.race report              # offline -> week10/race_table.md, handoffs.log, multiplier.md

Eval set and judge: the 10 cases in evals/w7/claims.jsonl, graded by
contract.grade for BOTH arms (decision, exclusion codes, payable within $1).
The Week-6 eval file the brief names was never committed to this repo (see
week10/README.md); these are the 10 cases the single agent was already raced
on in Weeks 7 and 8, unchanged.

Both arms: same model, same rules text, same output contract, same budgets
(wall-clock raised to config.W8_WALL_CLOCK_S for both, because the free-tier
rate limit would otherwise fire it). Claims run interleaved, single then squad,
so both arms see the same API conditions. Latency is reported net of 429 sleeps.
"""
import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone

from .. import config
from ..agents import agent
from ..agents.budget import Budget
from ..agents.contract import grade
from ..agents.runlog import RunLog
from ..agents.tools import load_claims, search_policy
from . import orchestrator

RUNS = config.W10_RUNS_DIR
FAIL_CLAIM = "CLM-2026-10002"     # flood: the exclusions check IS the answer (DENIED, E-15)


class Collect(RunLog):
    """A RunLog that also keeps the single agent's LAP lines, so its per-lap tokens
    land in handoffs.log next to the squad's hand-offs."""

    def __init__(self, path):
        super().__init__(path, echo=False)
        self.laps = []

    def __call__(self, event, **fields):
        super().__call__(event, **fields)
        if event.startswith("LAP"):
            self.laps.append({"handoff": f"single agent lap {event.split()[1]}",
                              "in": fields["lap_in"], "out": fields["lap_out"]})


def _done(path):
    return {(json.loads(l)["system"], json.loads(l)["claim_number"]) for l in path.read_text().splitlines()
            if l.strip()} if path.exists() else set()


def run_race() -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    f = RUNS / "race.jsonl"
    done = _done(f)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logpath = config.WEEK10_DIR / "logs" / f"race_{ts}.log"
    search_policy("warm-up", "homeowners", 1)
    for c in load_claims():
        cn = c["claim_number"]
        for system in ("single", "squad"):
            if (system, cn) in done:
                continue
            log = Collect(logpath)
            b = Budget(wall_clock_s=config.W8_WALL_CLOCK_S)
            if system == "single":
                r = agent.run(cn, b, log)
                r["system"], r["handoffs"] = "single", [{"claim": cn, **lap} for lap in log.laps]
            else:
                r = orchestrator.run(cn, b, log)
            ok, why = grade(r["output"], c["gold"])
            r.update(pass_=ok, why="; ".join(why), model=config.AGENT_MODEL, ts=ts)
            with f.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(f"{cn}  {system:<6}  {'PASS' if ok else 'FAIL'}  {r['tokens']:>6} tok  ${r['cost_usd']:.5f}  "
                  f"{(r['latency_ms'] - r['rate_wait_ms']) / 1000:5.1f}s net  {'; '.join(why)}", flush=True)


def run_fail() -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    search_policy("warm-up", "homeowners", 1)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log = RunLog(config.WEEK10_DIR / "logs" / f"failure_{ts}.log", echo=True)
    claim = next(c for c in load_claims() if c["claim_number"] == FAIL_CLAIM)
    r = orchestrator.run(FAIL_CLAIM, Budget(wall_clock_s=config.W8_WALL_CLOCK_S), log, fail_worker="exclusions")
    ok, why = grade(r["output"], claim["gold"])
    r.update(system="squad", pass_=ok, why="; ".join(why), model=config.AGENT_MODEL, ts=ts)
    (RUNS / "failure.jsonl").write_text(json.dumps(r) + "\n")
    print(json.dumps({k: r[k] for k in ("output", "events", "finding", "pass_", "why")}, indent=1))


# --- the numbers ------------------------------------------------------------------

def p(xs, q):
    """Nearest-rank percentile. With 10 runs, p99 is the slowest run."""
    xs = sorted(xs)
    return xs[max(0, math.ceil(q * len(xs)) - 1)]


def summarise(rows):
    net = [r["latency_ms"] - r["rate_wait_ms"] for r in rows]
    raw = [r["latency_ms"] for r in rows]
    return {"n": len(rows), "passes": sum(r["pass_"] for r in rows),
            "pass_rate": sum(r["pass_"] for r in rows) / len(rows),
            "p50": statistics.median(net), "p99": p(net, 0.99),
            "p50_raw": statistics.median(raw), "p99_raw": p(raw, 0.99),
            "tokens": sum(r["tokens"] for r in rows),
            "cost_per_claim": sum(r["cost_usd"] for r in rows) / len(rows),
            "cost_total": sum(r["cost_usd"] for r in rows)}


def report() -> None:
    rows = [json.loads(l) for l in (RUNS / "race.jsonl").read_text().splitlines() if l.strip()]
    arms = {s: [r for r in rows if r["system"] == s] for s in ("single", "squad")}
    claims = [c["claim_number"] for c in load_claims()]
    assert all(sorted(r["claim_number"] for r in arms[s]) == sorted(claims) for s in arms), "arms ran different cases"
    m = {s: summarise(v) for s, v in arms.items()}
    mult = m["squad"]["tokens"] / m["single"]["tokens"]

    # --- hand-off attribution ----------------------------------------------------
    by = defaultdict(lambda: [0, 0, 0])               # handoff -> [in, out, calls]
    for r in arms["squad"]:
        for h in r["handoffs"]:
            k = "orchestrator -> exclusions worker (all laps)" if "exclusions worker" in h["handoff"] else h["handoff"]
            by[k][0] += h["in"]; by[k][1] += h["out"]; by[k][2] += 1
    lap_by = defaultdict(lambda: [0, 0, 0])
    for r in arms["squad"]:
        for h in r["handoffs"]:
            if "exclusions worker" in h["handoff"]:
                lap_by[h["handoff"]][0] += h["in"]; lap_by[h["handoff"]][1] += h["out"]; lap_by[h["handoff"]][2] += 1
    total = m["squad"]["tokens"]
    top, (tin, tout, _) = max(by.items(), key=lambda kv: kv[1][0] + kv[1][1])
    top_lap, (lin, lout, _) = max(lap_by.items(), key=lambda kv: kv[1][0] + kv[1][1])

    # --- race_table.md ---------------------------------------------------------------
    S, Q = m["single"], m["squad"]
    L = ["# Race: single agent vs claims squad", "",
         f"Same 10 cases (evals/w7/claims.jsonl): {', '.join(c[-5:] for c in claims)}. "
         f"Same judge for both arms: `contract.grade` (decision + exclusion codes + payable within $1). "
         f"Model `{rows[0]['model']}`. Generated by `python -m app.squad.race report`.", "",
         "| metric | single agent | squad (orchestrator + 2 workers) | Δ |", "|---|---|---|---|",
         f"| **pass rate** | **{S['pass_rate']:.0%}** ({S['passes']}/10) | **{Q['pass_rate']:.0%}** ({Q['passes']}/10) "
         f"| {(Q['pass_rate'] - S['pass_rate']) * 100:+.0f} pts |",
         f"| **p50 latency** (net of 429 sleeps) | **{S['p50'] / 1000:.1f} s** | **{Q['p50'] / 1000:.1f} s** "
         f"| {(Q['p50'] - S['p50']) / 1000:+.1f} s |",
         f"| **p99 latency** (net; n=10, so the slowest claim) | **{S['p99'] / 1000:.1f} s** | **{Q['p99'] / 1000:.1f} s** "
         f"| {(Q['p99'] - S['p99']) / 1000:+.1f} s |",
         f"| **total tokens** (10 claims) | **{S['tokens']:,}** | **{Q['tokens']:,}** | ×{mult:.1f} |",
         f"| **cost per claim** | **${S['cost_per_claim']:.5f}** | **${Q['cost_per_claim']:.5f}** "
         f"| ×{Q['cost_per_claim'] / S['cost_per_claim']:.1f} |",
         f"| latency p50 / p99 raw (incl. 429 sleeps) | {S['p50_raw'] / 1000:.1f} s / {S['p99_raw'] / 1000:.1f} s "
         f"| {Q['p50_raw'] / 1000:.1f} s / {Q['p99_raw'] / 1000:.1f} s | |", "",
         f"**Context re-send multiplier: {mult:.1f}** (squad {Q['tokens']:,} / single {S['tokens']:,} tokens). "
         f"Largest share: **{top}, {(tin + tout) / total:.0%} of all squad tokens** "
         f"({tin + tout:,} tokens; its single largest lap is `{top_lap}` at {(lin + lout) / total:.0%}).", "",
         "## Per claim", "", "| claim | class | single | single tok | squad | squad tok | squad failure reason |",
         "|---|---|---|---|---|---|---|"]
    cls = {c["claim_number"]: c["class"] for c in load_claims()}
    for cn in claims:
        s = next(r for r in arms["single"] if r["claim_number"] == cn)
        q = next(r for r in arms["squad"] if r["claim_number"] == cn)
        L.append(f"| {cn[-5:]} | {cls[cn]} | {'PASS' if s['pass_'] else 'FAIL'} | {s['tokens']:,} "
                 f"| {'PASS' if q['pass_'] else 'FAIL'} | {q['tokens']:,} | {q['why'] or (s['why'] and 'single: ' + s['why']) or '—'} |")
    (config.WEEK10_DIR / "race_table.md").write_text("\n".join(L) + "\n")

    # --- handoffs.log ------------------------------------------------------------------
    H = [f"# every model call in the race, booked to the hand-off that caused it",
         f"# claim | arm | handoff | input tokens | output tokens | total | payload chars handed over", ""]
    for cn in claims:
        for s in ("single", "squad"):
            r = next(r for r in arms[s] if r["claim_number"] == cn)
            for h in r["handoffs"]:
                H.append(f"{cn} | {s:<6} | {h['handoff']:<44} | in {h['in']:>6} | out {h['out']:>5} | "
                         f"{h['in'] + h['out']:>6} | {h.get('payload_chars', '-')}")
            H.append(f"{cn} | {s:<6} | {'TOTAL':<44} | {'':>9} | {'':>9} | {r['tokens']:>6} |")
        H.append("")
    H += ["# squad totals by hand-off (10 claims)"]
    for k, (i, o, n) in sorted(by.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
        H.append(f"{k:<46} calls {n:>3} | in {i:>7} | out {o:>6} | {i + o:>7} tok | {(i + o) / total:6.1%} of squad tokens")
    H += ["", "# exclusions worker, by lap (each lap re-sends the whole worker conversation)"]
    for k, (i, o, n) in sorted(lap_by.items()):
        H.append(f"{k:<46} calls {n:>3} | in {i:>7} | out {o:>6} | {i + o:>7} tok | {(i + o) / total:6.1%} of squad tokens")
    H += ["", f"# single agent: {S['tokens']:,} tokens   squad: {Q['tokens']:,} tokens   multiplier {mult:.1f}"]
    (config.WEEK10_DIR / "handoffs.log").write_text("\n".join(H) + "\n")

    (config.WEEK10_DIR / "multiplier.md").write_text(
        f"Context re-send multiplier = squad tokens / single-agent tokens = {Q['tokens']:,} / {S['tokens']:,} = "
        f"**{mult:.1f}**. Largest token share: **{top}, {(tin + tout) / total:.0%} of all squad tokens**; "
        f"its biggest single hand-off is `{top_lap}` ({(lin + lout) / total:.0%}), where the worker re-sends its own "
        f"conversation including every policy chunk its earlier searches returned.\n")
    print("\n".join(L[:14]))
    print(f"\n-> week10/race_table.md, week10/handoffs.log, week10/multiplier.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "fail", "report"])
    a = ap.parse_args()
    config.WEEK10_DIR.mkdir(parents=True, exist_ok=True)
    {"run": run_race, "fail": run_fail, "report": report}[a.cmd]()


if __name__ == "__main__":
    main()
