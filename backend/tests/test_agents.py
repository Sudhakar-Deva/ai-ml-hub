"""Week 7: the loop, the four budgets, the workflow's fixed shape, the grader.

No network: the model is a scripted fake and search_policy is stubbed, so these
check the MECHANICS (budgets fire, the workflow never loops, tokens are summed
per lap). The race numbers come from real runs, never from here.
"""
import json
from types import SimpleNamespace as NS

import pytest

from app.agents import agent, contract, llm, tools, workflow
from app.agents.budget import Budget


def text(t):
    return NS(type="text", text=t)


def tool_use(name, args, i="t1"):
    return NS(type="tool_use", id=i, name=name, input=args)


def resp(blocks, stop, tin=1000, tout=100):
    return NS(content=blocks, stop_reason=stop, usage=NS(input_tokens=tin, output_tokens=tout))


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.messages = self

    def with_options(self, **_):
        return self

    def create(self, **kw):
        self.calls.append(json.loads(json.dumps(kw["messages"], default=str)))
        return self.script.pop(0) if len(self.script) > 1 else self.script[0]


@pytest.fixture
def fake(monkeypatch):
    def install(script):
        fc = FakeClient(script)
        monkeypatch.setattr(llm, "_client", fc)
        return fc
    stub = lambda query, policy_line, k=5: {"results": [
        {"chunk_id": "c1", "form_number": "HO-0304 ed. 03-24", "clause": "E-17", "text": "..."}]}
    monkeypatch.setitem(tools.REGISTRY, "search_policy", stub)
    monkeypatch.setattr(workflow, "search_policy", stub)
    return install


GOOD = json.dumps({"claim_number": "CLM-2026-10001", "decision": "COVERED",
                   "exclusion_codes": [], "payable_amount": 7500, "reason": "c1"})


def test_agent_happy_path_sums_every_lap(fake):
    fc = fake([
        resp([tool_use("get_claim", {"claim_number": "CLM-2026-10001"})], "tool_use"),
        resp([tool_use("search_policy", {"query": "supply line", "policy_line": "homeowners"})], "tool_use"),
        resp([tool_use("compute_payout", {"claim_status": "covered", "covered_amount": 8500,
                                          "excess": 1000, "special_limit": None})], "tool_use"),
        resp([text(GOOD)], "end_turn"),
    ])
    r = agent.run("CLM-2026-10001", Budget())
    assert r["status"] == "ok"
    assert r["path"] == ["get_claim", "search_policy", "compute_payout"]
    assert r["iters"] == 4 and r["tokens"] == 4 * 1100      # every lap counted, not the last
    assert contract.grade(r["output"], tools._claims()["CLM-2026-10001"]["gold"])[0]
    assert len(fc.calls[-1]) == 7                            # whole history re-sent each lap


def spin():
    return resp([tool_use("search_policy", {"query": "x", "policy_line": "homeowners"})], "tool_use")


def test_max_iterations_terminates_cleanly(fake):
    fake([spin()])
    r = agent.run("CLM-2026-10007", Budget(max_iters=3))
    assert r["status"] == "budget_exhausted" and r["budget_fired"] == "max_iterations"
    assert r["iters"] == 3 and r["output"]["decision"] == "UNDETERMINED"


def test_max_tokens_fires(fake):
    fake([spin()])
    r = agent.run("CLM-2026-10007", Budget(max_tokens=2500))
    assert r["budget_fired"] == "max_tokens" and r["iters"] == 3


def test_max_cost_fires(fake):
    fake([spin()])
    r = agent.run("CLM-2026-10007", Budget(max_cost_usd=0.01))   # 1000 in + 100 out = $0.003/lap
    assert r["budget_fired"] == "max_cost" and r["iters"] == 4


def test_wall_clock_fires_before_calling(fake):
    fc = fake([spin()])
    r = agent.run("CLM-2026-10007", Budget(wall_clock_s=0))
    assert r["budget_fired"] == "wall_clock" and fc.calls == []


def test_workflow_is_fixed_one_call_no_loop(fake):
    fc = fake([resp([text(json.dumps({"decision": "PARTIAL", "exclusion_codes": [], "covered_amount": 6000,
                                      "excess": 500, "special_limit": 2500, "reason": "c1"}))], "end_turn")])
    r = workflow.run("CLM-2026-10008", Budget())
    assert len(fc.calls) == 1
    assert r["path"] == ["get_claim", "search_policy", "compute_payout"]
    assert r["output"]["payable_amount"] == 2500                 # excess first, then the limit
    assert contract.grade(r["output"], tools._claims()["CLM-2026-10008"]["gold"])[0]


def test_compute_payout():
    assert tools.compute_payout("covered", 8500, 1000)["payable_amount"] == 7500
    assert tools.compute_payout("partial", 6000, 500, 2500)["payable_amount"] == 2500
    assert tools.compute_payout("denied", 9000, 1000)["payable_amount"] == 0
    assert "error" in tools.compute_payout("maybe", 1, 1)


def test_grade_optional_and_unsupported_codes():
    gold = tools._claims()["CLM-2026-10007"]["gold"]
    base = {"decision": "DENIED", "payable_amount": 0}
    assert contract.grade({**base, "exclusion_codes": ["E-20"]}, gold)[0]
    assert contract.grade({**base, "exclusion_codes": ["E-20", "E-21"]}, gold)[0]
    assert not contract.grade({**base, "exclusion_codes": ["E-21"]}, gold)[0]
    assert not contract.grade({**base, "exclusion_codes": ["E-20", "E-19"]}, gold)[0]


def test_tool_spec_one_job_enums_no_overlap():
    assert tools.check() == []


def test_race_set_shape():
    claims = tools.load_claims()
    assert len(claims) == 10
    assert sum(c["depends_on_notes"] and c["class"] != "missing_notes" for c in claims) >= 3
    assert any(c["class"] == "missing_notes" for c in claims)
    for c in claims:  # get_claim never leaks the answer
        assert "gold" not in tools.get_claim(c["claim_number"])
