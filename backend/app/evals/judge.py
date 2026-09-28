"""The LLM judge — one call, one binary criterion, and a prompt kept in a file.

    python -m app.evals.judge --version v1            # run it over the eval set
    python -m app.evals.judge --version v2
    python -m app.evals.judge --diff v1 v2

Three things this refuses to do, each of them a way the week goes wrong:

1. It will not run before the hand labels are COMMITTED. `--version v1` checks
   git for evals/w6/labels_25.json and stops if it is missing, uncommitted, or
   dirty. Running the judge, reading its verdicts and then writing 25 labels is
   agreeing with yourself with extra steps, and the gate is in code because a
   rule that lives only in a runbook is a rule you break at 11pm.

2. It will not score 1-10. The verdict is PASS or FAIL. A model cannot tell a 6
   from a 7, neither can a human, and "within 1 counts as agreement" inflates the
   agreement figure into meaninglessness.

3. It will not carry the criteria that assertions took over. If a judge prompt
   file still mentions the claim-number format, the date, the deductible amount
   or the exclusion-on-denial rule, loading it fails — otherwise the split is a
   sentence in a write-up rather than a fact about the system.
"""
import argparse
import json
import re

from ..llm import complete

from .. import config
from . import store
from .cases import by_id as case_by_id
from .cases import load as load_cases

VERDICT_RE = re.compile(r"^\s*VERDICT:\s*(PASS|FAIL)\b", re.I | re.M)
REASON_RE = re.compile(r"^\s*REASON:\s*(.+)$", re.I | re.M)

# Phrases that mean an assertable criterion has crept back into the judge.
# Checked on load, so the split cannot rot.
LEAKED_CRITERIA = (
    "clm-yyyy-nnnnn",
    "claim number is echoed",
    "date of loss is present",
    "numeric amount",
    "stated as a numeric",
)


def prompt_path(version: str):
    return config.JUDGE_DIR / f"judge_{version}.txt"


def load_prompt(version: str) -> str:
    path = prompt_path(version)
    if not path.exists():
        raise SystemExit(f"no judge prompt at {path}")
    text = path.read_text()
    if version != "v0":
        low = text.lower()
        leaked = [p for p in LEAKED_CRITERIA if p in low]
        if leaked:
            raise SystemExit(
                f"{path.name} still carries criteria that assertions own: {leaked}\n"
                "Delete them from the judge prompt — see week6/assertion_split.md."
            )
        if not VERDICT_RE.search(text.replace("<", "").replace(">", "")) and "VERDICT:" not in text:
            raise SystemExit(f"{path.name} does not ask for a VERDICT: line")
    return text


# --- the gate ----------------------------------------------------------------

def check_blind_protocol() -> dict:
    """Labels must exist, be committed, be clean, and be about THESE summaries."""
    ev = store.committed_at(config.W6_LABELS_FILE)
    if not config.W6_LABELS_FILE.exists():
        raise SystemExit(
            "BLIND PROTOCOL: evals/w6/labels_25.json does not exist.\n"
            "Label the summaries first, then commit them, then run the judge:\n"
            "  python -m app.evals.label --next\n"
            "  git add evals/w6/labels_25.json && git commit -m 'week 6: 25 blind hand labels'"
        )
    if ev is None:
        raise SystemExit(
            "BLIND PROTOCOL: labels_25.json exists but has never been committed.\n"
            "An uncommitted file has no ordering evidence — the rubric scores that 0.\n"
            "  git add evals/w6/labels_25.json && git commit -m 'week 6: 25 blind hand labels'"
        )
    if not ev["clean"]:
        raise SystemExit(
            f"BLIND PROTOCOL: labels_25.json has uncommitted changes since {ev['short']}.\n"
            "Labels edited after a judge run are not labels. Commit or restore them."
        )
    labels = json.loads(config.W6_LABELS_FILE.read_text())
    have, want = labels.get("summaries_sha"), store.summaries_sha()
    if have != want:
        raise SystemExit(
            f"BLIND PROTOCOL: the labels were made against summaries sha {have}, "
            f"but summaries.json is now {want}.\n"
            "Those labels are about different summaries. Re-label, or restore the summaries."
        )
    n = len(labels.get("labels", {}))
    if n < config.LABEL_N:
        raise SystemExit(f"BLIND PROTOCOL: {n} labels, the brief asks for {config.LABEL_N}.")
    return {"labels_commit": ev["short"], "labels_committed_at": ev["committed_at"],
            "summaries_sha": want, "labelled": n}


# --- the call ----------------------------------------------------------------

def _context(entry: dict) -> str:
    return "\n".join(
        f"[{r['chunk_id']} | {r['form_number']} | policy_line={r['policy_line']}]"
        for r in entry.get("retrieved", [])
    ) or "(none recorded)"


def judge_one(case: dict, entry: dict, template: str) -> dict:
    rendered = (
        template.replace("{notes}", case["notes"])
        .replace("{context}", _context(entry))
        .replace("{summary}", entry["summary"])
    )
    text, _ = complete(model=config.JUDGE_MODEL, user=rendered, params=config.JUDGE_PARAMS)
    m = VERDICT_RE.search(text)
    r = REASON_RE.search(text)
    return {
        "case_id": case["id"],
        "mode": case["mode"],
        "verdict": m.group(1).upper() if m else None,
        "reason": r.group(1).strip() if r else text[:300],
        "raw": text,
        "parsed": bool(m),
    }


def run(version: str = config.JUDGE_DEFAULT, gate: bool = True) -> dict:
    evidence = check_blind_protocol() if gate else {"gate": "SKIPPED"}
    template = load_prompt(version)
    if not config.LLM_API_KEY:
        raise SystemExit("LLM_API_KEY is not set — the judge is a model call.")

    summaries = store.load_summaries()["summaries"]
    cases = [c for c in load_cases() if c["id"] in summaries]
    verdicts = {}
    for i, c in enumerate(cases, start=1):
        v = judge_one(c, summaries[c["id"]], template)
        verdicts[c["id"]] = v
        print(f"  {i:3d}/{len(cases)}  {c['id']}  {v['verdict'] or 'UNPARSED'}  {c['mode']}")

    payload = {
        "ran_at": store.now(),
        "judge_version": version,
        "judge_prompt_sha": store.sha_file(prompt_path(version)),
        "judge_model": config.JUDGE_MODEL,
        "judge_params": config.JUDGE_PARAMS,
        "summaries_sha": store.summaries_sha(),
        "blind_protocol": evidence,
        "verdicts": verdicts,
    }
    path = store.save_run("judge", version, payload)
    print(f"\n-> {path.relative_to(config.ROOT)}")
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=config.JUDGE_VERSIONS, default=config.JUDGE_DEFAULT)
    ap.add_argument("--case", help="judge a single case, for debugging")
    ap.add_argument("--diff", nargs=2, metavar=("A", "B"), help="diff two judge prompts")
    ap.add_argument(
        "--no-gate", dest="gate", action="store_false",
        help="skip the blind-protocol check. Only legitimate for cases outside the labelled 25.",
    )
    a = ap.parse_args()

    if a.diff:
        import difflib

        left, right = (prompt_path(v).read_text().splitlines() for v in a.diff)
        print("\n".join(difflib.unified_diff(
            left, right,
            fromfile=f"judge_{a.diff[0]}.txt", tofile=f"judge_{a.diff[1]}.txt", lineterm="",
        )))
    elif a.case:
        entry = store.load_summaries()["summaries"][a.case]
        print(json.dumps(judge_one(case_by_id(a.case), entry, load_prompt(a.version)), indent=2))
    else:
        run(a.version, a.gate)
