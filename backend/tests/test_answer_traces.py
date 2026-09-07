"""End-to-end: the answer path writes a trace that is complete, redacted and
replayable — proven with the model call stubbed, so it runs without a key.

This is the test that de-risks the Week 5 traffic run. Everything downstream
(sampling, open coding, the taxonomy) is worthless if the trace the app writes
turns out to be missing a field, and finding that out after burning the traffic
means running it twice.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.generation import answer as gen  # noqa: E402
from app.tracing.replay import audit  # noqa: E402
from app.tracing.trace import read_all  # noqa: E402


class _Msg:
    def __init__(self, text):
        self.content = [type("Blk", (), {"text": text})()]


class _StubClient:
    """Stands in for anthropic.Anthropic. Records what it was sent so the test
    can assert the trace stores the prompt that was ACTUALLY used."""

    sent = {}

    def __init__(self, api_key=None):
        pass

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        _StubClient.sent = kwargs
        return _Msg(
            "E-17 is listed Excluded? = No, so the water damage is covered "
            "[structure_aware:HO-0304:HO-0304-ed-03-24.md:0004 | HO-0304 | "
            "SECTION I — EXCLUSIONS / E-17]"
        )


@pytest.fixture
def traced(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key-not-real")
    monkeypatch.setattr(config, "TRACE_FILE", tmp_path / "traces.jsonl")
    monkeypatch.setattr(gen.anthropic, "Anthropic", _StubClient)
    return tmp_path / "traces.jsonl"


def test_answering_writes_one_complete_trace(traced):
    result = gen.answer(
        "Does exclusion E-17 apply under form HO-0304 ed. 03-24?",
        k=3,
        source="test",
    )
    rows = read_all(traced)
    assert len(rows) == 1
    t = rows[0]

    assert t["trace_id"] == result["trace_id"]
    assert t["prompt_version"] == config.PROMPT_VERSION
    assert t["model"] == config.LLM_MODEL
    assert t["params"] == {"temperature": 0, "max_tokens": 1024}
    assert t["retrieval"]["retriever"] == config.SHIPPED_RETRIEVER
    assert len(t["retrieval"]["retrieved"]) == 3
    assert all(r["chunk_id"] and r["score"] is not None for r in t["retrieval"]["retrieved"])
    assert t["output"].startswith("E-17 is listed")
    assert t["latency_ms"] is not None


def test_the_trace_stores_the_prompt_that_was_actually_sent(traced):
    gen.answer("What is the E-19 threshold under HO-0304?", k=3, source="test")
    t = read_all(traced)[0]
    assert t["rendered_prompt"] == _StubClient.sent["messages"][0]["content"]
    assert t["system_prompt"] == _StubClient.sent["system"]


def test_the_written_trace_is_replayable_from_itself(traced):
    gen.answer("Is seepage excluded under DP-0110?", k=3, source="test")
    report = audit(read_all(traced)[0])
    assert report["replayable"] is True
    assert report["missing_fields"] == []
    assert report["gaps"] == []


def test_identifiers_in_a_live_question_never_reach_the_file(traced):
    gen.answer(
        "Claim CLM-2024-88431 for Mr. Robert Hanley — is E-17 excluded?",
        k=3,
        source="test",
    )
    raw = traced.read_text()
    assert "CLM-2024-88431" not in raw
    assert "Robert Hanley" not in raw
    assert "E-17" in raw and "HO-0304" in raw

    t = json.loads(raw.strip())
    assert t["redaction"]["when"] == "pre-write"
    assert set(t["redaction"]["rules_fired"]) == {"claim_number", "person_name"}


def test_tracing_can_be_switched_off_for_eval_runs(traced):
    """The Week 4 harness calls answer() in a loop; those are experiments, not
    traffic, and must not pollute the population the sample is drawn from."""
    r = gen.answer("What is the mold aggregate?", k=3, trace=False)
    assert r["trace_id"] is None
    assert read_all(traced) == []
