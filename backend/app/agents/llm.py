"""One model call, booked against a Budget. Used by BOTH systems.

The provider (Groq by default, Anthropic optional) is chosen in app/llm.py, and
both the agent and the workflow go through this one function — whatever setting
one system gets, the other gets too, or the race measures the setting.

On Anthropic, thinking is explicitly disabled: the pinned SDK (anthropic 0.40)
predates thinking blocks and cannot round-trip them through the message list.
On Groq, gpt-oss reasoning effort is pinned by config.LLM_REASONING_EFFORT, and
its reasoning tokens are billed (and budgeted) as output tokens.
"""
from .. import config
from .. import llm as provider
from .budget import Budget


def call(budget: Budget, *, system: str, messages: list[dict], tools: list[dict] | None = None):
    """-> (response, usage dict). Raises BudgetExceeded before or after the call."""
    budget.check()
    resp, usage = provider.chat_with_tools(
        model=config.AGENT_MODEL,
        system=system,
        messages=messages,
        tools=tools,
        max_tokens=config.AGENT_MAX_TOKENS_PER_CALL,
        timeout=max(1.0, budget.remaining_s()),
    )
    budget.charge(config.AGENT_MODEL, usage["input_tokens"], usage["output_tokens"])
    return resp, usage


def to_param(block) -> dict:
    """Response content block -> the dict we send back next lap."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return block.model_dump()


def text_of(resp) -> str:
    return "".join(b.text for b in resp.content if b.type == "text").strip()
