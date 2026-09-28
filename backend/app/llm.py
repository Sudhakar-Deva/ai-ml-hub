"""The one place the app talks to a model provider.

    LLM_PROVIDER=groq        (default) — Groq's OpenAI-compatible chat API
    LLM_PROVIDER=anthropic   — the Anthropic Messages API

Every call site (answer, summarize, judge, replay, the agent and the workflow)
goes through here, so switching provider is one line in .env and never a change
to the thing being measured. Whatever the provider, a call returns the same
shape: the text, plus input/output token counts for the budget and the trace.

Groq is reached over plain HTTPS with httpx (already installed as a dependency of
chromadb), so there is no second SDK to pin.
"""
import json
import re
import time
from types import SimpleNamespace

import httpx

from . import config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class MissingAPIKey(RuntimeError):
    """Raised instead of a bare KeyError so the API can answer 503, not 500."""


class LLMTimeout(RuntimeError):
    """The request ran past its timeout. The agent maps this to the wall-clock budget."""


def _require_key() -> None:
    if not config.LLM_API_KEY:
        raise MissingAPIKey("LLM_API_KEY is not set — copy .env.example to .env and fill it in.")


# --- Groq (OpenAI-compatible) -------------------------------------------------

RATE_LIMIT_RETRIES = 4


class DailyLimit(RuntimeError):
    """The provider's tokens-per-day cap. Not a budget the agent breached: the eval
    must stop here, not record the run as a wall-clock failure."""


# Seconds slept waiting out 429s since import. Week 8 subtracts the delta from a
# run's latency, so a rate-limit sleep is never reported as a mitigation's price.
_rate_wait_s = 0.0


def rate_limit_wait_s() -> float:
    return _rate_wait_s


def _retry_after(r: httpx.Response) -> float:
    try:
        return float(r.headers.get("retry-after", "")) + 0.5
    except ValueError:
        m = re.search(r"try again in ([\d.]+)s", r.text)
        return float(m.group(1)) + 0.5 if m else 5.0


def _groq_post(body: dict, timeout: float | None) -> dict:
    """POST one completion. A 429 (the free tier allows ~8k tokens/minute) is
    waited out and retried — but never past `timeout`, so the agent's wall-clock
    budget still holds. Waits are real elapsed time and land in measured latency;
    they are also summed in _rate_wait_s so they can be taken back out."""
    global _rate_wait_s
    deadline = time.monotonic() + (timeout or 120.0)
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LLMTimeout("timed out waiting on the Groq rate limit")
        try:
            r = httpx.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
                json=body,
                timeout=remaining,
            )
        except httpx.TimeoutException as e:
            raise LLMTimeout(str(e)) from e
        if r.status_code == 429 and "tokens per day" in r.text.lower():
            raise DailyLimit(f"Groq daily token cap reached: {r.text[:300]}")
        if r.status_code == 429 and attempt < RATE_LIMIT_RETRIES:
            wait = _retry_after(r)
            if wait >= deadline - time.monotonic():
                raise LLMTimeout(f"rate limited; retry in {wait:.1f}s exceeds the time left")
            time.sleep(wait)
            _rate_wait_s += wait
            continue
        if r.status_code == 400 and '"tool_use_failed"' in r.text:
            return _failed_generation(r.json()["error"])
        if r.status_code >= 400:
            raise RuntimeError(f"Groq {r.status_code}: {r.text[:500]}")
        return r.json()


def _failed_generation(err: dict) -> dict:
    """Groq validates tool calls server-side and 400s when the model calls a tool
    that is not in the request (gpt-oss has been seen calling a tool named "json").
    That is the MODEL's choice, not a transport error: hand it back as the call it
    made, so the loop answers it the way it answers any unknown tool
    (run_tool -> "unknown tool") and the trajectory eval can count it. Usage is not
    reported on a 400; the generation is charged as zero tokens, which understates
    cost slightly rather than inventing a number."""
    gen = err.get("failed_generation") or ""
    try:
        call = json.loads(gen)
        name, args = str(call["name"]), call.get("arguments") or {}
    except (ValueError, KeyError, TypeError):
        return {"choices": [{"message": {"content": gen}, "finish_reason": "stop"}], "usage": {}}
    return {"choices": [{"finish_reason": "tool_calls", "message": {"content": None, "tool_calls": [{
        "id": f"failed_{abs(hash(gen)) % 10**8}", "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)}}]}}], "usage": {}}


def _groq_params(params: dict) -> dict:
    """Translate the app's params (temperature, max_tokens) to Groq's names.

    gpt-oss is a reasoning model and its reasoning tokens count against
    max_completion_tokens, so reasoning_effort is pinned from config.LLM_REASONING_EFFORT
    for every call. It is added here rather than stored in each trace's params, so
    keep it unchanged between a trace and its replay."""
    out = {k: v for k, v in params.items() if k != "max_tokens"}
    if "max_tokens" in params:
        out["max_completion_tokens"] = params["max_tokens"]
    if config.LLM_REASONING_EFFORT and "reasoning_effort" not in out:
        out["reasoning_effort"] = config.LLM_REASONING_EFFORT
    return out


# gpt-oss writes typographic look-alikes: 【…】 for citation brackets and U+2011
# (non-breaking hyphen) inside codes, so "E‑17" and "CLM‑2026‑10001" would slip
# past every regex in the app (citations, A1-A4, the contract parser). They are
# mapped back to ASCII as the text arrives — the same character, not a rewrite.
_ASCII = str.maketrans({"【": "[", "】": "]", "\u2010": "-", "\u2011": "-"})


def _groq_text(msg: dict) -> str:
    return (msg.get("content") or "").translate(_ASCII)


def _groq_usage(data: dict) -> dict:
    u = data.get("usage") or {}
    # completion_tokens already includes reasoning tokens, which are billed as output.
    return {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0)}


# --- simple calls: one system prompt, one user message ------------------------

def complete(*, model: str, user: str, system: str | None = None, params: dict,
             timeout: float | None = None) -> tuple[str, dict]:
    """-> (text, usage). Used by answer, summarize, judge and replay."""
    _require_key()
    if config.LLM_PROVIDER == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=config.LLM_API_KEY)
        msg = client.messages.create(
            model=model,
            **({"system": system} if system else {}),
            messages=[{"role": "user", "content": user}],
            **params,
        )
        usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
        return msg.content[0].text.strip(), usage

    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": user}
    ]
    data = _groq_post({"model": model, "messages": messages, **_groq_params(params)}, timeout)
    return _groq_text(data["choices"][0]["message"]).strip(), _groq_usage(data)


# --- tool-use calls for the agent and the workflow ------------------------------
#
# The agent loop is written against Anthropic-shaped messages (content blocks of
# type text / tool_use / tool_result). For Groq, the request is translated to the
# OpenAI shape on the way out and the response is translated back on the way in,
# so agent.py and workflow.py are the same code on either provider — the race
# measures the architecture, not a provider adapter.

def _tools_to_openai(tools: list[dict]) -> list[dict]:
    return [
        {"type": "function",
         "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in tools
    ]


def _messages_to_openai(system: str, messages: list[dict]) -> list[dict]:
    out = [{"role": "system", "content": system}]
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            out.append({"role": m["role"], "content": content})
            continue
        if m["role"] == "assistant":
            text = "".join(b["text"] for b in content if b["type"] == "text")
            calls = [
                {"id": b["id"], "type": "function",
                 "function": {"name": b["name"], "arguments": json.dumps(b["input"])}}
                for b in content if b["type"] == "tool_use"
            ]
            out.append({"role": "assistant", "content": text or None, **({"tool_calls": calls} if calls else {})})
        else:  # user turn carrying tool results
            for b in content:
                if b["type"] == "tool_result":
                    out.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": b["content"]})
                elif b["type"] == "text":
                    out.append({"role": "user", "content": b["text"]})
    return out


def _response_from_openai(data: dict):
    """OpenAI-shaped response -> an object that reads like an Anthropic Message."""
    choice = data["choices"][0]
    msg = choice["message"]
    blocks = []
    if msg.get("content"):
        blocks.append(SimpleNamespace(type="text", text=_groq_text(msg)))
    for c in msg.get("tool_calls") or []:
        try:
            args = json.loads(c["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {"_unparseable_arguments": c["function"]["arguments"]}
        blocks.append(SimpleNamespace(type="tool_use", id=c["id"], name=c["function"]["name"], input=args))
    stop = "tool_use" if choice.get("finish_reason") == "tool_calls" else (
        "max_tokens" if choice.get("finish_reason") == "length" else "end_turn")
    return SimpleNamespace(content=blocks, stop_reason=stop)


def chat_with_tools(*, model: str, system: str, messages: list[dict], tools: list[dict] | None,
                    max_tokens: int, timeout: float):
    """-> (response with .content blocks and .stop_reason, usage dict)."""
    _require_key()
    if config.LLM_PROVIDER == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=config.LLM_API_KEY, max_retries=2)
        try:
            resp = client.with_options(timeout=timeout).messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                extra_body={"thinking": {"type": "disabled"}},
                **({"tools": tools} if tools else {}),
            )
        except anthropic.APITimeoutError as e:
            raise LLMTimeout(str(e)) from e
        u = resp.usage
        # Cache reads/writes are input tokens too; count them or the cost is short.
        in_tok = u.input_tokens + (getattr(u, "cache_read_input_tokens", 0) or 0) \
            + (getattr(u, "cache_creation_input_tokens", 0) or 0)
        return resp, {"input_tokens": in_tok, "output_tokens": u.output_tokens}

    body = {
        "model": model,
        "messages": _messages_to_openai(system, messages),
        **_groq_params({"temperature": 0, "max_tokens": max_tokens}),
    }
    if tools:
        body["tools"] = _tools_to_openai(tools)
    data = _groq_post(body, timeout)
    return _response_from_openai(data), _groq_usage(data)
