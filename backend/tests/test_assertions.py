"""The assertions are the criteria the judge no longer has, so they are the
criteria that now need to be right. These tests are the reason it is safe to
delete C1-C4 from the judge prompt.

Each test pins a way the check could be wrong in the direction that matters:
passing something a claims file should not carry.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evals import assertions as A  # noqa: E402
from app.generation.summarize import parse  # noqa: E402

CASE = {"claim_number": "CLM-2024-88431", "date_of_loss": "2024-06-14"}

GOOD = """CLAIM: CLM-2024-88431
DATE OF LOSS: 2024-06-14
POLICY LINE: homeowners
GOVERNING FORM: HO-0304 ed. 03-24
COVERAGE POSITION: COVERED
DEDUCTIBLE: $1,000
EXCLUSIONS APPLIED: NONE
SUMMARY: The rupture was sudden and accidental, so E-17 does not exclude the
loss [structure_aware:HO-0304:HO-0304-ed-03-24.md:0004 | HO-0304 | E-17]."""


def run(text, case=CASE):
    return {r["id"]: r for r in A.run(text, case)["results"]}


def test_a_clean_summary_passes_every_assertion():
    out = A.run(GOOD, CASE)
    assert out["passed"] is True
    assert out["failed"] == []


# --- A1 claim number ---------------------------------------------------------

@pytest.mark.parametrize(
    "line,why",
    [
        ("CLAIM: 2024-88431", "no CLM prefix"),
        ("CLAIM: CLM-2024-8843", "four digits, not five"),
        ("CLAIM: CLM-24-88431", "two-digit year"),
        ("CLAIM: not stated in the notes", "absent"),
        ("CLAIM: CLM-2024-99999", "a different claim's number"),
    ],
)
def test_a1_rejects_anything_that_is_not_the_right_claim_number(line, why):
    text = GOOD.replace("CLAIM: CLM-2024-88431", line)
    assert run(text)["A1"]["passed"] is False, why


def test_a1_rejects_a_longer_number_that_merely_starts_correctly():
    """CLM-2024-884312 must not pass by matching a prefix — a claim number that
    is one digit off points at a different file."""
    text = GOOD.replace("CLM-2024-88431\n", "CLM-2024-884312\n")
    assert run(text)["A1"]["passed"] is False


# --- A2 date of loss ---------------------------------------------------------

@pytest.mark.parametrize(
    "line",
    [
        "DATE OF LOSS: last Tuesday",
        "DATE OF LOSS: 14 June",
        "DATE OF LOSS: 2024-02-30",          # parses as digits, is not a real day
        "DATE OF LOSS: not stated",
        "DATE OF LOSS: 2024-06-15",          # real date, wrong claim
    ],
)
def test_a2_rejects_unparseable_or_unreal_or_wrong_dates(line):
    text = GOOD.replace("DATE OF LOSS: 2024-06-14", line)
    assert run(text)["A2"]["passed"] is False


def test_a2_fails_when_the_line_is_missing_entirely():
    text = "\n".join(l for l in GOOD.splitlines() if not l.startswith("DATE OF LOSS"))
    assert run(text)["A2"]["passed"] is False


# --- A3 deductible -----------------------------------------------------------

@pytest.mark.parametrize(
    "line",
    [
        "DEDUCTIBLE: the standard deductible applies",
        "DEDUCTIBLE: not stated in the notes",
        "DEDUCTIBLE: N/A",
        "DEDUCTIBLE: unknown",
    ],
)
def test_a3_rejects_a_deductible_described_rather_than_stated(line):
    text = GOOD.replace("DEDUCTIBLE: $1,000", line)
    assert run(text)["A3"]["passed"] is False


@pytest.mark.parametrize("line", ["DEDUCTIBLE: $1,000", "DEDUCTIBLE: 1000", "DEDUCTIBLE: $250.00"])
def test_a3_accepts_any_shape_of_a_real_amount(line):
    text = GOOD.replace("DEDUCTIBLE: $1,000", line)
    assert run(text)["A3"]["passed"] is True


# --- A4 exclusion cited on denial -------------------------------------------

def test_a4_does_not_apply_when_nothing_is_denied():
    assert run(GOOD)["A4"]["applicable"] is False


def test_a4_fails_a_denial_in_the_position_field_with_no_code():
    text = GOOD.replace("COVERAGE POSITION: COVERED", "COVERAGE POSITION: DENIED")
    r = run(text)["A4"]
    assert r["applicable"] is True and r["passed"] is False


def test_a4_catches_a_denial_stated_only_in_the_prose():
    """The position line can say PARTIAL while the prose denies the loss. A check
    that only reads the label misses the sentence the policyholder is sent."""
    text = GOOD.replace("COVERAGE POSITION: COVERED", "COVERAGE POSITION: PARTIAL").replace(
        "SUMMARY: The rupture", "SUMMARY: The claim is denied. The rupture"
    )
    r = run(text)["A4"]
    assert r["applicable"] is True and r["passed"] is False


def test_a4_passes_a_denial_that_names_its_code():
    text = (
        GOOD.replace("COVERAGE POSITION: COVERED", "COVERAGE POSITION: DENIED")
        .replace("EXCLUSIONS APPLIED: NONE", "EXCLUSIONS APPLIED: E-19")
    )
    assert run(text)["A4"]["passed"] is True


def test_a4_is_not_triggered_by_an_exclusion_that_does_not_apply():
    """'This exclusion does not apply' is a grant of coverage, not a denial. A
    keyword match on 'not' turns every covered water loss into an A4 failure."""
    text = GOOD.replace(
        "SUMMARY: The rupture", "SUMMARY: E-17 does not apply here. The rupture"
    )
    assert run(text)["A4"]["applicable"] is False


# --- the parser --------------------------------------------------------------

def test_the_parser_repairs_nothing():
    """A parser that fills in a missing line hands the assertion a pass it did
    not earn, and the assertion then measures the parser."""
    fields = parse("CLAIM: CLM-2024-88431\nSUMMARY: text")
    assert fields["DATE OF LOSS"] is None
    assert fields["DEDUCTIBLE"] is None


def test_the_parser_keeps_a_multi_line_summary_whole():
    fields = parse(GOOD)
    assert "E-17" in fields["SUMMARY"]
    assert fields["SUMMARY"].endswith("].")


def test_an_unapplicable_assertion_is_not_counted_as_a_pass():
    """A run where A4 never applied has three assertions behind it, not four."""
    out = A.run(GOOD, CASE)
    assert out["applicable"] == 3
    assert A.ASSERTION_COUNT == 4


def test_a4_does_not_accept_a_code_that_the_prose_is_negating():
    """'DENIED ... E-17 does not exclude the loss' names no authority for the
    denial. Reading the prose for any E-code passes exactly this sentence, which
    is the one a bad-faith exhibit is built from."""
    text = (
        GOOD.replace("COVERAGE POSITION: COVERED", "COVERAGE POSITION: DENIED")
        .replace("EXCLUSIONS APPLIED: NONE", "EXCLUSIONS APPLIED: NONE")
    )
    assert "E-17" in text
    assert run(text)["A4"]["passed"] is False


def test_a4_falls_back_to_the_prose_only_when_the_line_is_absent():
    text = "\n".join(l for l in GOOD.splitlines() if not l.startswith("EXCLUSIONS APPLIED"))
    text = text.replace("COVERAGE POSITION: COVERED", "COVERAGE POSITION: DENIED")
    assert run(text)["A4"]["passed"] is True
