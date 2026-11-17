"""The validated judge, re-checked on the INTEGRATED system's outputs.

    python -m app.triage.judge run --tag v2-after        # one call per case, temp 0
    python -m app.triage.judge agreement --tag v2-after  # vs evals/w12/labels.json (no LLM)

Refuses to run before the hand labels exist for every case in the run: labelling after
reading the judge's verdicts is agreeing with yourself (the Week 6 rule, kept in code).
"""
import argparse
import hashlib
import json
import re

from .. import config
from ..evals.judge import LEAKED_CRITERIA, REASON_RE, VERDICT_RE
from ..llm import complete
from . import suite

PROMPT_FILE = config.W12_DIR / "judge_v3.txt"


def load_prompt() -> str:
    text = PROMPT_FILE.read_text()
    leaked = [p for p in LEAKED_CRITERIA if p in text.lower()]
    if leaked:
        raise SystemExit(f"judge_v3 carries assertable criteria {leaked}: delete them, assertions own them")
    return text.split("-" * 80, 1)[1].strip()


def _editions(rec: dict) -> str:
    from ..mcp_servers.policy_server import FORMS, edition_in_force

    out = []
    for form, eds in FORMS.items():
        if eds[0]["policy_line"] == rec["policy_line"]:
            e = edition_in_force(form, rec["loss_date"])
            out.append(f"- {form}: {e['edition'] if e else 'no edition in force'}")
    return "\n".join(out)


def _context(rec: dict) -> str:
    from ..retrieval.store import get_collection

    ids = list(dict.fromkeys(i for s in rec["steps"] for i in s.get("chunk_ids", [])))
    if not ids:
        return "(no wording was retrieved)"
    got = get_collection("structure_aware").get(ids=ids, include=["documents"])
    by = dict(zip(got["ids"], got["documents"]))
    return "\n\n".join(f"[{i}]\n{by.get(i, '(missing)')}" for i in ids)


def judge_one(rec: dict, template: str) -> dict:
    prompt = template.format(fnol=rec["fnol_redacted"], loss_date=rec["loss_date"], editions=_editions(rec),
                             context=_context(rec), referral=rec["rendered"])
    text, usage = complete(model=config.JUDGE_MODEL, user=prompt, params=config.JUDGE_PARAMS, timeout=120)
    v, why = VERDICT_RE.search(text or ""), REASON_RE.search(text or "")
    return {"verdict": v.group(1).upper() if v else "UNPARSED", "reason": why.group(1).strip() if why else text[:200],
            "usage": usage}


def labels() -> dict:
    if not config.W12_LABELS_FILE.exists():
        raise SystemExit(f"no hand labels at {config.W12_LABELS_FILE}: label first, then judge")
    return json.loads(config.W12_LABELS_FILE.read_text())


def run(tag: str) -> None:
    lab = labels()
    rows = suite.scored(tag)
    missing = [r["id"] for r in rows if r["id"] not in lab["labels"]]
    if missing:
        raise SystemExit(f"hand labels missing for {missing}: label every case before the judge runs")
    template = load_prompt()
    out_path = config.W12_RUNS_DIR / tag / "_judge.json"
    done = json.loads(out_path.read_text())["verdicts"] if out_path.exists() else {}
    for r in rows:
        if r["id"] in done:
            continue
        done[r["id"]] = judge_one(r["rec"], template)
        print(f"  {r['id']:<16} {done[r['id']]['verdict']}  {done[r['id']]['reason'][:110]}", flush=True)
        out_path.write_text(json.dumps({"judge": "v3", "model": config.JUDGE_MODEL, "params": config.JUDGE_PARAMS,
                                        "labels_sha": hashlib.sha256(config.W12_LABELS_FILE.read_bytes()).hexdigest()[:12],
                                        "verdicts": done}, indent=1))
    print(agreement(tag))


def agreement(tag: str) -> str:
    lab = labels()["labels"]
    j = json.loads((config.W12_RUNS_DIR / tag / "_judge.json").read_text())
    v = j["verdicts"]
    ids = [i for i in v if i in lab]
    agree = [i for i in ids if v[i]["verdict"] == lab[i]["label"]]
    tp = sum(v[i]["verdict"] == "FAIL" and lab[i]["label"] == "FAIL" for i in ids)
    fn = sum(v[i]["verdict"] != "FAIL" and lab[i]["label"] == "FAIL" for i in ids)
    tn = sum(v[i]["verdict"] == "PASS" and lab[i]["label"] == "PASS" for i in ids)
    fp = sum(v[i]["verdict"] != "PASS" and lab[i]["label"] == "PASS" for i in ids)
    pct = 100 * len(agree) / len(ids) if ids else 0
    L = [f"## Judge v3 vs hand labels on `{tag}` ({j['model']}, temp 0)", "",
         f"**Agreement: {len(agree)}/{len(ids)} = {pct:.1f}%** (gate: 85%) → {'CLEARS' if pct >= 85 else 'DOES NOT CLEAR'}", "",
         "| | label FAIL | label PASS |", "|---|---|---|",
         f"| judge FAIL | {tp} | {fp} |", f"| judge PASS | {fn} | {tn} |", "",
         f"Catches {tp}/{tp + fn} of the hand-labelled failures; passes {tn}/{tn + fp} of the hand-labelled passes."]
    dis = [i for i in ids if i not in agree]
    if dis:
        L += ["", "Disagreements:", ""] + [f"- {i}: label {lab[i]['label']} ({lab[i]['why']}); judge {v[i]['verdict']} ({v[i]['reason']})" for i in dis]
    return "\n".join(L)


def main() -> None:
    from .run import quiet

    quiet()
    ap = argparse.ArgumentParser(prog="python -m app.triage.judge")
    ap.add_argument("cmd", choices=["run", "agreement"])
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    run(a.tag) if a.cmd == "run" else print(agreement(a.tag))


if __name__ == "__main__":
    main()
