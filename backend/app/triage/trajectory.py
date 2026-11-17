"""Week 8's trajectory eval, on the integrated agent. Offline: reads the suite's traces.

    python -m app.triage.trajectory --tag v2-after

The expected path for every claim, in any order before the last step:
  check_coverage_in_force(policy, loss_date)   the loss date from the FNOL, exactly
  lookup_policy(policy, loss_date)             same
  policy-docs__search_policy(...)              at least once; under v2 with that loss date
  refer_to_adjuster                            last, exactly once
A call is a CORRECT TOOL CHOICE when it is one of these with the right arguments and is
not a repeat; anything else (a repeat, a wrong date, an error, an unknown tool) is not.

Outcome = the case passes every applicable suite assertion. Trajectory = the path above
held. The gap is outcome rate minus trajectory rate; both off-diagonal cells are listed.
"""
import argparse

from . import suite

SEARCH = "policy-docs__search_policy"


def score(row: dict) -> dict:
    c, steps = row["case"], row["rec"].get("steps", [])
    pn, d, v2 = c["policy_number"], c["date_of_loss"], row["rec"]["date_filter"]
    seen, correct, notes = set(), 0, []
    for i, s in enumerate(steps):
        a, t = s["args"], s["tool"]
        ok = False
        if s.get("error"):
            notes.append(f"{t} error")
        elif t in ("check_coverage_in_force", "lookup_policy"):
            ok = a.get("policy_number") == pn and a.get("loss_date") == d and t not in seen
            if not ok:
                notes.append(f"{t} args {a.get('policy_number')}/{a.get('loss_date')}" if t not in seen else f"{t} repeated")
        elif t == SEARCH:
            ok = a.get("policy_line") == c["policy_line"] and (not v2 or a.get("loss_date") == d)
            if not ok:
                notes.append(f"search line={a.get('policy_line')} date={a.get('loss_date')}")
        elif t == "refer_to_adjuster":
            ok = i == len(steps) - 1 and t not in seen
        else:
            notes.append(f"unexpected tool {t}")
        correct += ok
        seen.add(t)
    tools = [s["tool"] for s in steps]
    # Not in force on the loss date: there is no wording or limit to look up, so the
    # expected path is in-force check -> refer (fixed after the first report scored the
    # two correct short paths as failures).
    needed = ("check_coverage_in_force", "lookup_policy", SEARCH) if c["gold"]["in_force"] else ("check_coverage_in_force",)
    path_ok = (all(any(s["tool"] == need and not s.get("error") for s in steps)
                   for need in needed)
               and tools[-1:] == ["refer_to_adjuster"] and correct == len(steps))
    return {"id": row["id"], "mode": row["mode"], "calls": len(steps), "correct": correct, "trajectory_ok": path_ok,
            "outcome_ok": row["pass"], "path": tools, "notes": notes, "trace_id": row["rec"]["trace_id"]}


def report(tag: str) -> str:
    rows = [score(r) for r in suite.scored(tag)]
    n = len(rows)
    calls, correct = sum(r["calls"] for r in rows), sum(r["correct"] for r in rows)
    t_ok, o_ok = sum(r["trajectory_ok"] for r in rows), sum(r["outcome_ok"] for r in rows)
    right_wrong_path = [r for r in rows if r["outcome_ok"] and not r["trajectory_ok"]]
    wrong_right_path = [r for r in rows if not r["outcome_ok"] and r["trajectory_ok"]]
    L = [f"## Trajectory eval on `{tag}` (n={n})", "",
         f"- **Tool-choice accuracy: {correct}/{calls} = {100 * correct / calls:.1f}%** of tool calls were the right tool with the right arguments",
         f"- Trajectory pass (whole expected path held): **{t_ok}/{n} = {100 * t_ok / n:.1f}%**",
         f"- Outcome pass (every suite assertion): **{o_ok}/{n} = {100 * o_ok / n:.1f}%**",
         f"- **Outcome-vs-trajectory gap: {100 * (o_ok - t_ok) / n:+.1f} points**",
         f"- Right outcome, wrong path: {len(right_wrong_path)} · wrong outcome, right path: {len(wrong_right_path)}", "",
         "| case | mode | path | tool choices | trajectory | outcome | notes |", "|---|---|---|---|---|---|---|"]
    short = {"check_coverage_in_force": "inforce", "lookup_policy": "lookup", SEARCH: "search", "refer_to_adjuster": "refer"}
    for r in rows:
        L.append(f"| {r['id']} | {r['mode']} | {' → '.join(short.get(t, t) for t in r['path'])} | {r['correct']}/{r['calls']} | "
                 f"{'ok' if r['trajectory_ok'] else 'FAIL'} | {'ok' if r['outcome_ok'] else 'FAIL'} | {'; '.join(r['notes'])} |")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.triage.trajectory")
    ap.add_argument("--tag", required=True)
    print(report(ap.parse_args().tag))


if __name__ == "__main__":
    main()
