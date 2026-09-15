"""The criteria that were taken OUT of the judge.

    python -m app.evals.assertions --case w6-004        # run them on one summary

Four facts about a claim summary are mechanically decidable, so a model never
sees them:

  A1 claim_number_echoed      the claim number from the notes, in CLM-YYYY-NNNNN
                              form, appears on the CLAIM line
  A2 date_of_loss_parseable   a DATE OF LOSS is present and is a real calendar
                              date, not "last Tuesday" and not 2024-02-30
  A3 excess_amount_numeric    the deductible/excess is a number, not "standard
                              deductible applies"
  A4 exclusion_cited_on_denial  if the summary denies the claim ANYWHERE — the
                              position field or the prose — an exclusion code is
                              named

These were criteria 2, 3, 5 and 6 of judges/judge_v0.txt and are deleted from
judge_v1.txt. See week6/assertion_split.md for the diff.

A4 is the one that earns its place. The other three are format; A4 is the
internal consistency between what the summary decided and the authority it
cited, and a denial with no code is the single sentence in a claims file that
becomes a bad-faith exhibit. It is still not a judgement call, so it is still
not a model's job.
"""
import argparse
import json
import re
from datetime import date

from ..generation.summarize import parse

# CLM-YYYY-NNNNN — four-digit year, five-digit sequence. Anchored on both ends
# so CLM-2024-884312 fails rather than matching a prefix.
CLAIM_FORM_RE = re.compile(r"\bCLM-(\d{4})-(\d{5})\b")
ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
MONEY_RE = re.compile(r"\$?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d{2}))?\b")
EXCLUSION_CODE_RE = re.compile(r"\bE-\d{2}\b")
# Denial stated in prose rather than in the position field. Kept narrow: "is not
# covered" counts, "the tear-out is not covered" also counts, but "this
# exclusion does not apply" must not.
DENIAL_PROSE_RE = re.compile(
    r"\b(?:we\s+deny|claim\s+is\s+denied|is\s+denied|denying\s+the\s+claim|"
    r"no\s+coverage\s+(?:is\s+)?(?:available|afforded)|"
    r"(?:loss|claim|damage)\s+is\s+not\s+covered|not\s+covered\s+under)\b",
    re.I,
)
NON_NUMERIC_DEDUCTIBLE = re.compile(r"\b(?:n/?a|none|unknown|not\s+stated|standard|tbd)\b", re.I)


def _real_date(y: int, m: int, d: int) -> bool:
    try:
        date(y, m, d)
        return True
    except ValueError:
        return False


def a1_claim_number_echoed(summary: str, fields: dict, case: dict) -> dict:
    """The claim number from the notes, in CLM-YYYY-NNNNN form, on the CLAIM line."""
    expected = case.get("claim_number")
    line = fields.get("CLAIM")
    if line is None:
        return _fail("A1", "claim_number_echoed", "no CLAIM line in the summary")
    found = CLAIM_FORM_RE.findall(line)
    if not found:
        return _fail("A1", "claim_number_echoed", f"CLAIM line {line!r} is not CLM-YYYY-NNNNN")
    got = f"CLM-{found[0][0]}-{found[0][1]}"
    if expected and got != expected:
        return _fail("A1", "claim_number_echoed", f"echoed {got}, notes say {expected}")
    return _pass("A1", "claim_number_echoed", got)


def a2_date_of_loss_parseable(summary: str, fields: dict, case: dict) -> dict:
    """A date of loss is present and is a real calendar date."""
    line = fields.get("DATE OF LOSS")
    if not line:
        return _fail("A2", "date_of_loss_parseable", "no DATE OF LOSS line")
    m = ISO_DATE_RE.search(line)
    if not m:
        return _fail("A2", "date_of_loss_parseable", f"{line!r} is not an ISO date")
    y, mo, d = (int(x) for x in m.groups())
    if not _real_date(y, mo, d):
        return _fail("A2", "date_of_loss_parseable", f"{m.group(0)} is not a real date")
    got = m.group(0)
    expected = case.get("date_of_loss")
    if expected and got != expected:
        return _fail("A2", "date_of_loss_parseable", f"reports {got}, notes say {expected}")
    return _pass("A2", "date_of_loss_parseable", got)


def a3_excess_amount_numeric(summary: str, fields: dict, case: dict) -> dict:
    """The deductible / excess is a number."""
    line = fields.get("DEDUCTIBLE")
    if not line:
        return _fail("A3", "excess_amount_numeric", "no DEDUCTIBLE line")
    if NON_NUMERIC_DEDUCTIBLE.search(line) and not MONEY_RE.search(line.replace(",", "")):
        return _fail("A3", "excess_amount_numeric", f"{line!r} names no amount")
    m = MONEY_RE.search(line)
    if not m:
        return _fail("A3", "excess_amount_numeric", f"{line!r} contains no numeric amount")
    return _pass("A3", "excess_amount_numeric", m.group(0).strip())


def a4_exclusion_cited_on_denial(summary: str, fields: dict, case: dict) -> dict:
    """A denial anywhere in the summary requires an exclusion code."""
    position = (fields.get("COVERAGE POSITION") or "").upper()
    prose = fields.get("SUMMARY") or ""
    denies = "DENIED" in position or bool(DENIAL_PROSE_RE.search(prose))
    if not denies:
        return _na("A4", "exclusion_cited_on_denial", "no denial stated")
    # The code must be on the EXCLUSIONS APPLIED line, which exists for exactly
    # this. Scanning the prose instead passes a summary that denies the claim
    # while its only E-code appears in "E-17 does not apply here" — a sentence
    # that grants coverage. Prose is read only when the line is absent
    # altogether, so a model that drops the label is still caught on substance.
    line = fields.get("EXCLUSIONS APPLIED")
    codes = EXCLUSION_CODE_RE.findall(line) if line is not None else EXCLUSION_CODE_RE.findall(prose)
    if not codes:
        where = "COVERAGE POSITION" if "DENIED" in position else "the prose"
        missing = "EXCLUSIONS APPLIED names none" if line is not None else "no EXCLUSIONS APPLIED line"
        return _fail("A4", "exclusion_cited_on_denial", f"denial stated in {where}; {missing}")
    return _pass("A4", "exclusion_cited_on_denial", ", ".join(sorted(set(codes))))


ASSERTIONS = (
    a1_claim_number_echoed,
    a2_date_of_loss_parseable,
    a3_excess_amount_numeric,
    a4_exclusion_cited_on_denial,
)
ASSERTION_COUNT = len(ASSERTIONS)


def _pass(aid, name, detail):
    return {"id": aid, "name": name, "applicable": True, "passed": True, "detail": str(detail)}


def _fail(aid, name, detail):
    return {"id": aid, "name": name, "applicable": True, "passed": False, "detail": str(detail)}


def _na(aid, name, detail):
    return {"id": aid, "name": name, "applicable": False, "passed": None, "detail": str(detail)}


def run(summary: str, case: dict | None = None) -> dict:
    """-> {results: [...], passed: bool, failed: [ids]}.

    `passed` is True only when every APPLICABLE assertion passed. A
    non-applicable assertion is not a pass and is not counted as one — a run
    where A4 never applied has three assertions behind it, not four, and the
    report says so."""
    case = case or {}
    fields = parse(summary)
    results = [fn(summary, fields, case) for fn in ASSERTIONS]
    applicable = [r for r in results if r["applicable"]]
    return {
        "results": results,
        "applicable": len(applicable),
        "passed": all(r["passed"] for r in applicable),
        "failed": [r["id"] for r in applicable if not r["passed"]],
        "fields": fields,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", help="case id — reads its summary from the last run")
    ap.add_argument("--file", help="a file containing one summary")
    a = ap.parse_args()

    if a.file:
        from pathlib import Path

        text, case = Path(a.file).read_text(), {}
    elif a.case:
        from .cases import by_id
        from .store import summary_for

        case = by_id(a.case)
        text = summary_for(a.case)
    else:
        raise SystemExit("give --case or --file")

    out = run(text, case)
    for r in out["results"]:
        mark = "  n/a" if not r["applicable"] else ("PASS" if r["passed"] else "FAIL")
        print(f"{mark}  {r['id']} {r['name']:<28} {r['detail']}")
    print(f"\n{out['applicable']} applicable · passed={out['passed']} · failed={out['failed']}")
    raise SystemExit(0 if out["passed"] else 1)
