"""The invariants Week 5 rests on.

Redaction-before-write is the one that is graded as a line in the write-up, so
it is tested as behaviour: the bytes on disk never contain the identifier, and
the corpus vocabulary survives intact.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tracing import sample as sampling  # noqa: E402
from app.tracing import trace as tracing  # noqa: E402
from app.tracing.opencode import check_sentence  # noqa: E402
from app.tracing.redact import redact  # noqa: E402
from app.tracing.replay import audit  # noqa: E402


# --- redaction ---------------------------------------------------------------

@pytest.mark.parametrize(
    "text,rule,secret",
    [
        ("claim CLM-2024-88431 is open", "claim_number", "CLM-2024-88431"),
        ("policy HO-1234567 lapsed", "policy_number", "HO-1234567"),
        ("call 555-212-9090 today", "phone", "555-212-9090"),
        ("email adjuster@example.com", "email", "adjuster@example.com"),
        ("Mrs. Alvarez called", "person_name", "Alvarez"),
        ("the insured is Robert Hanley", "person_name", "Robert Hanley"),
        ("SSN 123-45-6789 on file", "ssn", "123-45-6789"),
        ("loss at 412 Maple Street", "address", "412 Maple Street"),
    ],
)
def test_identifiers_are_removed(text, rule, secret):
    clean, hits = redact(text)
    assert rule in hits, f"{rule} did not fire on {text!r}"
    assert secret not in clean, f"{secret!r} survived into {clean!r}"


@pytest.mark.parametrize(
    "text",
    [
        "reach Dr. Chen at (555) 212-9090",   # bracketed — must not leave a stray "("
        "call 555-212-9090 today",
        "tel +1 555 212 9090",
        "(555)212-9090",
    ],
)
def test_every_phone_shape_is_taken_whole(text):
    clean, hits = redact(text)
    assert "phone" in hits
    assert "9090" not in clean
    assert "(" not in clean and ")" not in clean


@pytest.mark.parametrize(
    "text",
    [
        # dates and money look like identifiers to a careless regex, and the
        # corpus is made of them. Eating these makes traces unreadable.
        "Effective: 03-01-2024 and the aggregate is $10,000 per policy period",
        "Special limits: $2,500 jewelry, $200 money, $1,500 securities",
        "The 14-day clock in E-19; 60 days after our request; 30 consecutive days",
        "structure_aware:HO-0304:HO-0304-ed-03-24.md:0004",
        "HO-0304 ed. 03-24 vs DP-0110 ed. 02-24 and CO-0715 ed. 04-24",
    ],
)
def test_dates_amounts_and_chunk_ids_are_left_alone(text):
    clean, hits = redact(text)
    assert clean == text
    assert hits == []


def test_corpus_vocabulary_survives():
    """Form numbers, editions and exclusion codes are NOT PII. A redactor that
    eats them leaves a trace nobody can read or replay."""
    text = "Does E-17 under HO-0304 ed. 03-24 differ from DP-0110 ed. 02-24 and CO-0715?"
    clean, hits = redact(text)
    assert clean == text
    assert hits == []


def test_clean_text_reports_no_rules_fired():
    _, hits = redact("What is the 14 day threshold in E-19?")
    assert hits == []


# --- the writer --------------------------------------------------------------

def _trace(question, output):
    return tracing.build_trace(
        question=question,
        output=output,
        system_prompt="SYS",
        rendered_prompt=f"CTX\nQuestion: {question}",
        retrieved=[{"rank": 1, "chunk_id": "c1", "score": 0.5, "form_number": "HO-0304"}],
        model="claude-sonnet-5",
        params={"temperature": 0, "max_tokens": 1024},
        strategy="structure_aware",
        retriever="hybrid",
        k=3,
        source="test",
    )


def test_redaction_happens_before_the_bytes_hit_disk(tmp_path):
    path = tmp_path / "traces.jsonl"
    t = _trace(
        "Claim CLM-2024-88431 for Mr. Robert Hanley — is E-17 excluded?",
        "The insured Mr. Robert Hanley is covered under E-17.",
    )
    tracing.write(t, path)

    raw = path.read_text()
    assert "CLM-2024-88431" not in raw
    assert "Robert Hanley" not in raw
    assert "[CLAIM_ID]" in raw and "[NAME]" in raw
    # and the thing the trace is about is still legible
    assert "E-17" in raw

    row = json.loads(raw.strip())
    assert row["redaction"] == {
        "applied": True,
        "when": "pre-write",
        "rules_fired": ["claim_number", "person_name"],
    }


def test_write_appends_and_reads_back(tmp_path):
    path = tmp_path / "traces.jsonl"
    tracing.write(_trace("q1", "a1"), path)
    tracing.write(_trace("q2", "a2"), path)
    rows = tracing.read_all(path)
    assert [r["question"] for r in rows] == ["q1", "q2"]
    assert len({r["trace_id"] for r in rows}) == 2


def test_trace_carries_everything_replay_needs(tmp_path):
    path = tmp_path / "traces.jsonl"
    written = tracing.write(_trace("q", "a"), path)
    report = audit(written)
    assert report["replayable"] is True
    assert report["missing_fields"] == []


def test_audit_names_the_field_that_is_missing():
    t = _trace("q", "a")
    del t["rendered_prompt"]
    report = audit(t)
    assert report["replayable"] is False
    assert [m["field"] for m in report["missing_fields"]] == ["rendered_prompt"]


# --- sampling ----------------------------------------------------------------

def _population(n):
    return [{"trace_id": f"tr_{i:04d}", "source": "traffic"} for i in range(n)]


def test_same_seed_draws_the_same_sample():
    pop = _population(80)
    a = sampling.draw(pop, seed=20260907, n=20)["trace_ids"]
    b = sampling.draw(pop, seed=20260907, n=20)["trace_ids"]
    assert a == b


def test_a_different_seed_draws_a_different_sample():
    pop = _population(80)
    a = sampling.draw(pop, seed=20260907, n=20)["trace_ids"]
    b = sampling.draw(pop, seed=1, n=20)["trace_ids"]
    assert a != b


def test_file_order_does_not_change_the_draw():
    """Traces land in the file in the order requests happened. If that leaked
    into the sample, the same seed would draw different traces tomorrow."""
    pop = _population(60)
    shuffled = list(reversed(pop))
    assert (
        sampling.draw(pop, seed=7, n=20)["trace_ids"]
        == sampling.draw(shuffled, seed=7, n=20)["trace_ids"]
    )


def test_short_population_refuses_rather_than_under_draws():
    with pytest.raises(SystemExit):
        sampling.draw(_population(5), n=20)


def test_source_filter_keeps_the_demo_set_out_of_the_random_sample():
    pop = _population(50) + [{"trace_id": f"tr_demo{i}", "source": "demo"} for i in range(10)]
    picked = sampling.draw(pop, seed=3, n=20, source="traffic")["trace_ids"]
    assert all(not p.startswith("tr_demo") for p in picked)


# --- open coding -------------------------------------------------------------

@pytest.mark.parametrize(
    "sentence",
    [
        "This is a retrieval issue.",
        "The model hallucinated the limit.",
        "We should fix the chunker.",
        "Classic bug in the fusion step.",
    ],
)
def test_diagnoses_are_refused_at_entry(sentence):
    assert check_sentence(sentence)


@pytest.mark.parametrize(
    "sentence",
    [
        "The answer quoted the $10,000 mold aggregate but cited a chunk from DP-0110.",
        "It refused, saying the deductible amount was not in the context.",
        "I don't know why this failed.",
        "The answer said E-17 is excluded; the retrieved HO-0304 row says Excluded? = No.",
    ],
)
def test_honest_observations_pass(sentence):
    assert check_sentence(sentence) == []
