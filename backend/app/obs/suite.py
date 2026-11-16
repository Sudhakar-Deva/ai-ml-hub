"""The coverage suite: every case through the real app, pass counts every time.

    python -m app.obs.suite build                  # (once) the 10 base cases -> evals/w11/coverage_suite.jsonl
    python -m app.obs.suite run --tag before-fix   # all cases, prints per-case + pass count

A case passes only when ALL hold:
  position    COVERAGE POSITION == gold.position
  exclusions  every gold exclusion code appears on EXCLUSIONS APPLIED, and nothing
              outside gold + optional does
  A4          Week 6's assertion: a denial anywhere in the summary names an exclusion code

The whole suite runs every time. The new case passing while an old one breaks is
exactly the regression this exists to catch.
"""
import argparse
import json
import re
from datetime import datetime, timezone

from .. import config
from ..agents.tools import load_claims
from ..evals import assertions
from .app import handle
from .traffic import notes_for

CODE_RE = re.compile(r"\bE-\d{2}\b")


def build() -> None:
    config.W11_SUITE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = ["// Week 11 coverage suite, in the Week 6 case format. Base cases w11-001..010 are the 10 fixed "
             "claims of evals/w7/claims.jsonl; drill cases are appended below them, never edited."]
    for i, c in enumerate(load_claims(), 1):
        lines.append(json.dumps({
            "id": f"w11-{i:03d}", "mode": c["class"], "kind": "synthetic", "claim_number": c["claim_number"],
            "date_of_loss": c["date_of_loss"], "policy_line": c["policy_line"], "notes": notes_for(c),
            "gold": {"position": c["gold"]["decision"], "exclusion_codes": c["gold"]["exclusion_codes"],
                     "optional_codes": c["gold"].get("optional_codes", [])}}))
    config.W11_SUITE_FILE.write_text("\n".join(lines) + "\n")
    print(f"{len(lines) - 1} cases -> {config.W11_SUITE_FILE.relative_to(config.ROOT)}")


def load() -> list[dict]:
    return [json.loads(l) for l in config.W11_SUITE_FILE.read_text().splitlines()
            if l.strip() and not l.startswith("//")]


def check(case: dict, rec: dict) -> tuple[bool, list[str]]:
    o, gold, why = rec["output"], case["gold"], []
    pos = (o["coverage_position"] or "").split()[0] if o["coverage_position"] else None
    if pos != gold["position"]:
        why.append(f"position {pos} != {gold['position']}")
    applied = set(CODE_RE.findall(o["exclusions_applied"] or ""))
    req, opt = set(gold["exclusion_codes"]), set(gold.get("optional_codes", []))
    if not req <= applied:
        why.append(f"missing exclusion {sorted(req - applied)}")
    if applied - req - opt:
        why.append(f"unsupported exclusion {sorted(applied - req - opt)}")
    a4 = assertions.a4_exclusion_cited_on_denial(o["text"], assertions.parse(o["text"]), case)
    if a4["applicable"] and a4["passed"] is False:
        why.append(f"A4: {a4.get('detail')}")
    return not why, why


def run(tag: str) -> dict:
    from ..generation.summarize import retrieve

    retrieve("warm-up")
    cases = load()
    rows = []
    for c in cases:
        rec = handle(c["notes"], "eval-suite", f"eval:{c['id']}", write_log=False)
        ok, why = check(c, rec)
        rows.append({"id": c["id"], "mode": c["mode"], "pass": ok, "why": why,
                     "position": rec["output"]["coverage_position"], "exclusions": rec["output"]["exclusions_applied"],
                     "prompt_version": rec["prompt_version"], "context_ids": rec["retrieved_context_ids"],
                     "tokens": rec["totals"]["tokens"], "cost_usd": rec["totals"]["cost_usd"],
                     "text": rec["output"]["text"]})
        print(f"{c['id']}  {c['mode']:<26} {'PASS' if ok else 'FAIL'}  {rec['output']['coverage_position'] or '?':<13} "
              f"excl={rec['output']['exclusions_applied']}  {'; '.join(why)}", flush=True)
    n_pass = sum(r["pass"] for r in rows)
    pv = rows[0]["prompt_version"]
    print(f"\nSUITE {tag}: {n_pass}/{len(rows)} passed  (prompt_version={pv}, model={config.LLM_MODEL})")
    out = {"tag": tag, "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "prompt_version": pv,
           "passed": n_pass, "total": len(rows), "rows": rows}
    config.W11_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (config.W11_RUNS_DIR / f"{tag}.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    r = sub.add_parser("run")
    r.add_argument("--tag", required=True)
    a = ap.parse_args()
    build() if a.cmd == "build" else run(a.tag)
