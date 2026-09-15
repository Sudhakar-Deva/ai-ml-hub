"""How often the judge and the human said the same thing.

    python -m app.evals.agreement --version v1
    python -m app.evals.agreement --before v1 --after v2 --markdown

Agreement is the plain percentage: of the 25 labelled summaries, how many did
the judge and I both call PASS or both call FAIL. That is the number the brief
asks for, so it is the number reported first.

Cohen's kappa is reported next to it and is not decoration. If 22 of 25
summaries are passes, a judge that answers PASS every single time scores 88%
agreement while knowing nothing at all. Kappa subtracts the agreement you would
get by chance from the marginals, so a judge that has learned to say PASS is
visibly worth about zero. Where the two numbers disagree, kappa is the one
telling the truth.

The confusion matrix is split the way it has to be for a claims file: a
judge_pass / human_fail cell is a summary the judge waved through that a human
would not, and that is a payout that should not happen. The other error cell is
an adjuster reading a summary that was fine. They are not the same cost and the
report never averages them.
"""
import argparse
import json

from .. import config
from . import store
from .cases import load as load_cases


def load_labels() -> dict:
    if not config.W6_LABELS_FILE.exists():
        raise SystemExit(f"no labels at {config.W6_LABELS_FILE}")
    return json.loads(config.W6_LABELS_FILE.read_text())


def compare(version: str) -> dict:
    labels = load_labels()
    run = store.latest_run("judge", version)
    if run is None:
        raise SystemExit(f"no judge run for {version} — python -m app.evals.judge --version {version}")
    if run["summaries_sha"] != labels.get("summaries_sha"):
        raise SystemExit(
            f"judge run is against summaries {run['summaries_sha']}, labels are about "
            f"{labels.get('summaries_sha')}. Comparing them would be comparing two different runs."
        )

    modes = {c["id"]: c["mode"] for c in load_cases()}
    rows, unparsed = [], []
    for cid, lab in sorted(labels["labels"].items()):
        v = run["verdicts"].get(cid)
        if v is None:
            continue
        if v["verdict"] is None:
            unparsed.append(cid)
            continue
        jp = v["verdict"] == "PASS"
        rows.append(
            {
                "case_id": cid,
                "mode": modes.get(cid, "?"),
                "human": "pass" if lab["passed"] else "fail",
                "judge": "pass" if jp else "fail",
                "agree": jp == lab["passed"],
                "human_reason": lab["reason"],
                "judge_reason": v["reason"],
            }
        )

    n = len(rows)
    agree = sum(r["agree"] for r in rows)
    cm = {
        "both_pass": sum(1 for r in rows if r["human"] == "pass" and r["judge"] == "pass"),
        "both_fail": sum(1 for r in rows if r["human"] == "fail" and r["judge"] == "fail"),
        "judge_pass_human_fail": sum(1 for r in rows if r["judge"] == "pass" and r["human"] == "fail"),
        "judge_fail_human_pass": sum(1 for r in rows if r["judge"] == "fail" and r["human"] == "pass"),
    }
    return {
        "judge_version": version,
        "judge_prompt_sha": run["judge_prompt_sha"],
        "judge_ran_at": run["ran_at"],
        "labels_commit": run["blind_protocol"].get("labels_commit"),
        "n": n,
        "agree": agree,
        "agreement_pct": round(100 * agree / n, 1) if n else None,
        "kappa": kappa(rows),
        "confusion": cm,
        "unparsed_verdicts": unparsed,
        "rows": rows,
        "disagreements": [r for r in rows if not r["agree"]],
    }


def kappa(rows: list[dict]) -> float | None:
    """Cohen's kappa. 1.0 is perfect, 0.0 is what guessing from the marginals
    already buys you, below 0 is worse than guessing."""
    n = len(rows)
    if not n:
        return None
    po = sum(r["agree"] for r in rows) / n
    hp = sum(1 for r in rows if r["human"] == "pass") / n
    jp = sum(1 for r in rows if r["judge"] == "pass") / n
    pe = hp * jp + (1 - hp) * (1 - jp)
    if pe == 1:
        return None
    return round((po - pe) / (1 - pe), 3)


def markdown(before: dict, after: dict | None = None) -> str:
    out = [
        "### Judge vs human — agreement on the single binary criterion",
        "",
        f"Labels committed at `{before['labels_commit']}`, before either judge run. "
        f"n = {before['n']}.",
        "",
        "| Judge | Agreement | Cohen's κ | both pass | both fail | judge PASS / human FAIL | judge FAIL / human PASS |",
        "| ----- | --------: | --------: | --------: | --------: | ----------------------: | ----------------------: |",
    ]
    for r in [x for x in (before, after) if x]:
        c = r["confusion"]
        out.append(
            f"| `{r['judge_version']}` | **{r['agreement_pct']}%** ({r['agree']}/{r['n']}) | "
            f"{r['kappa']} | {c['both_pass']} | {c['both_fail']} | "
            f"{c['judge_pass_human_fail']} | {c['judge_fail_human_pass']} |"
        )
    if after:
        delta = round(after["agreement_pct"] - before["agreement_pct"], 1)
        out += [
            "",
            f"**agreement_before = {before['agreement_pct']}%  ->  "
            f"agreement_after = {after['agreement_pct']}%**  ({delta:+} points, "
            f"κ {before['kappa']} -> {after['kappa']})",
        ]
    out += ["", "#### Disagreements", ""]
    target = after or before
    if not target["disagreements"]:
        out.append("_None._")
    else:
        out += [
            "| Case | Mode | Human | Judge | Judge's reason |",
            "| ---- | ---- | ----- | ----- | -------------- |",
        ]
        for d in target["disagreements"]:
            out.append(
                f"| `{d['case_id']}` | {d['mode']} | {d['human']} | {d['judge']} | "
                f"{d['judge_reason'][:110]} |"
            )
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=None)
    ap.add_argument("--before", default=None)
    ap.add_argument("--after", default=None)
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.before:
        b, aft = compare(a.before), (compare(a.after) if a.after else None)
    else:
        b, aft = compare(a.version or config.JUDGE_DEFAULT), None

    if a.json:
        print(json.dumps({"before": b, "after": aft}, indent=2))
    else:
        print(markdown(b, aft))
