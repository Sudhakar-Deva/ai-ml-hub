"""Race the agent against the fixed workflow over the SAME 10 claims.

    python -m app.agents.race

Writes:
  evals/w7/race.csv           the 8 numbers (4 per system) — the deliverable
  evals/w7/race_claims.csv    per claim, per system: pass, why, path, latency, tokens, cost
  evals/w7/runs/race_<ts>.jsonl   every run record, outputs included
  week7/logs/race_<ts>.log    every lap and step

Claims are interleaved (workflow then agent, claim by claim) so both systems see
the same API conditions, and the retriever is warmed first so the embedding-model
load is not charged to whichever system happens to go first.
"""
import argparse
import csv
import json
import statistics
from datetime import datetime, timezone

from .. import config
from . import agent, workflow
from .budget import Budget
from .contract import grade
from .runlog import RunLog
from .tools import load_claims, search_policy

SYSTEMS = {"workflow": workflow.run, "agent": agent.run}


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "claims": n,
        "pass_rate": round(sum(r["pass"] for r in rows) / n, 3),
        "p50_latency_ms": round(statistics.median(r["latency_ms"] for r in rows)),
        "total_tokens": sum(r["tokens"] for r in rows),
        "cost_per_claim_usd": round(sum(r["cost_usd"] for r in rows) / n, 5),
    }


def main(claim_filter: list[str] | None = None) -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log = RunLog(config.W7_LOGS_DIR / f"race_{ts}.log")
    claims = [c for c in load_claims() if not claim_filter or c["claim_number"] in claim_filter]

    search_policy("warm-up", "homeowners", 1)  # load the embedder outside the clock

    rows = []
    for c in claims:
        for name, fn in SYSTEMS.items():
            r = fn(c["claim_number"], Budget(), log)
            ok, why = grade(r["output"], c["gold"])
            rows.append({**r, "class": c["class"], "pass": ok, "why": "; ".join(why),
                         "gold": c["gold"]})
            print(f"{c['claim_number']}  {name:<8}  {'PASS' if ok else 'FAIL'}  "
                  f"{r['latency_ms']:>8.0f} ms  {r['tokens']:>6} tok  ${r['cost_usd']:.4f}  "
                  f"{'  ' + '; '.join(why) if why else ''}", flush=True)

    config.W7_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    runs_file = config.W7_RUNS_DIR / f"race_{ts}.jsonl"
    runs_file.write_text("".join(json.dumps(r) + "\n" for r in rows))

    with config.W7_RACE_CLAIMS_FILE.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["claim_number", "class", "system", "pass", "why", "decision", "payable_amount",
                    "exclusion_codes", "path", "laps", "latency_ms", "tokens", "cost_usd", "status"])
        for r in rows:
            o = r["output"] or {}
            w.writerow([r["claim_number"], r["class"], r["system"], int(r["pass"]), r["why"],
                        o.get("decision"), o.get("payable_amount"), " ".join(o.get("exclusion_codes") or []),
                        ">".join(r["path"]), r["iters"], r["latency_ms"], r["tokens"],
                        f"{r['cost_usd']:.6f}", r["status"]])

    summary = {s: summarise([r for r in rows if r["system"] == s]) for s in SYSTEMS}
    with config.W7_RACE_FILE.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["system", "claims", "pass_rate", "p50_latency_ms", "total_tokens",
                    "cost_per_claim_usd", "model", "run"])
        for s, m in summary.items():
            w.writerow([s, m["claims"], m["pass_rate"], m["p50_latency_ms"], m["total_tokens"],
                        m["cost_per_claim_usd"], config.AGENT_MODEL, ts])

    # --- the decision rule: does the path vary by input? ----------------------
    by_claim = {}
    for r in rows:
        by_claim.setdefault(r["claim_number"], {})[r["system"]] = r
    print("\n| system | pass rate | p50 latency | total tokens | cost / claim |")
    print("|---|---|---|---|---|")
    for s, m in summary.items():
        print(f"| {s} | {m['pass_rate']:.0%} ({round(m['pass_rate'] * m['claims'])}/{m['claims']}) "
              f"| {m['p50_latency_ms']} ms | {m['total_tokens']:,} | ${m['cost_per_claim_usd']:.4f} |")

    print("\nAgent paths (does the path vary by input?):")
    paths = {}
    for cn, d in by_claim.items():
        a = d.get("agent")
        if a:
            p = ">".join(a["path"]) or "(none)"
            paths.setdefault(p, []).append(f"{cn} [{a['class']}]")
    for p, cns in sorted(paths.items(), key=lambda x: -len(x[1])):
        print(f"  {len(cns)}x  {p}\n        {', '.join(cns)}")

    print("\nDisagreements (only these can justify the agent):")
    for cn, d in by_claim.items():
        if "agent" in d and "workflow" in d and d["agent"]["pass"] != d["workflow"]["pass"]:
            win = "agent" if d["agent"]["pass"] else "workflow"
            print(f"  {cn} [{d['agent']['class']}] -> {win} wins;  "
                  f"agent searches={d['agent']['path'].count('search_policy')};  "
                  f"loser: {d['workflow' if win == 'agent' else 'agent']['why']}")

    print(f"\n-> {config.W7_RACE_FILE.relative_to(config.ROOT)}\n-> "
          f"{config.W7_RACE_CLAIMS_FILE.relative_to(config.ROOT)}\n-> {runs_file.relative_to(config.ROOT)}"
          f"\n-> {log.path.relative_to(config.ROOT)}")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", nargs="*", help="subset of claim numbers (default: all 10)")
    a = ap.parse_args()
    main(a.claims)
