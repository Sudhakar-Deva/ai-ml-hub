"""One model call, booked against a Budget. Used by BOTH systems.

Thinking is explicitly disabled on both sides: the pinned SDK (anthropic 0.40)
predates thinking blocks and cannot round-trip them through the message list, and
whatever setting one system gets the other must get too, or the race measures the
setting. No temperature: the current Sonnet/Opus models reject sampling params.
"""
import anthropic

from .. import config
from .budget import Budget

_client = None


def client():
    global _client
    if _client is None:
        if not config.LLM_API_KEY:
            from ..generation.answer import MissingAPIKey

            raise MissingAPIKey("LLM_API_KEY is not set — copy .env.example to .env and fill it in.")
        _client = anthropic.Anthropic(api_key=config.LLM_API_KEY, max_retries=2)
    return _client


def call(budget: Budget, *, system: str, messages: list[dict], tools: list[dict] | None = None):
    """-> (response, usage dict). Raises BudgetExceeded before or after the call."""
    budget.check()
    kwargs = {"tools": tools} if tools else {}
    resp = client().with_options(timeout=max(1.0, budget.remaining_s())).messages.create(
        model=config.AGENT_MODEL,
        max_tokens=config.AGENT_MAX_TOKENS_PER_CALL,
        system=system,
        messages=messages,
        extra_body={"thinking": {"type": "disabled"}},
        **kwargs,
    )
    u = resp.usage
    # Cache reads/writes are input tokens too; count them or the cost is short.
    in_tok = u.input_tokens + (getattr(u, "cache_read_input_tokens", 0) or 0) \
        + (getattr(u, "cache_creation_input_tokens", 0) or 0)
    usage = {"input_tokens": in_tok, "output_tokens": u.output_tokens}
    budget.charge(config.AGENT_MODEL, in_tok, u.output_tokens)
    return resp, usage


def to_param(block) -> dict:
    """SDK content block -> the dict we send back next lap."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return block.model_dump()


def text_of(resp) -> str:
    return "".join(b.text for b in resp.content if b.type == "text").strip()
