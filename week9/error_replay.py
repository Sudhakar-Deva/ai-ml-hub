"""Same failing call, old error vs new error: how does the model handle it?

    cd backend && ../.venv/bin/python ../week9/error_replay.py v1
    cd backend && ../.venv/bin/python ../week9/error_replay.py v2

Rebuilds the conversation from the natural before-run (week9/traces/error_before_*)
up to and including its first failing call:
    search_policy x2 (re-executed live: retrieval is deterministic), then
    get_clause(form_number="HO-0304 ed. 03-24", clause="E-17")
and lets the model continue from there, through the real host and the real
servers.

  v2  the live server, with the rewritten docstring and recoverable errors.
  v1  the same live server, with its OBSERVABLE v1 behaviour restored: the
      tools/list description "Get a clause." and the v1 error strings
      ("Error 3" for an unknown form, "Error 4" for an unknown clause). The
      v1 tool had exactly those two branches (week9/policy_server_v1.py.txt),
      so the model sees exactly what the v1 server sent.

The model call happens in this script (the host side), never in a server.
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config                                  # noqa: E402
from app import llm as provider                         # noqa: E402
from app.agents.llm import text_of, to_param           # noqa: E402
from app.mcphost.agent import Host, Trace              # noqa: E402

QUERY = "Quote clause E-17 of form HO-304 word for word."
PREFIX = [  # the before-run's calls, in order, up to its first failing call
    ("policy-docs__search_policy", {"k": 5, "policy_line": "homeowners", "query": "HO-304 E-17"}),
    ("policy-docs__search_policy", {"k": 10, "policy_line": "homeowners",
                                    "query": "E-17 Water damage resulting from the \"sudden and accidental\" discharge"}),
    ("policy-docs__get_clause", {"clause": "E-17", "form_number": "HO-0304 ed. 03-24"}),   # <- the failing call
]
V1_DESCRIPTION = "[policy-docs] Get a clause."


def v1_error(args: dict, text: str) -> str:
    """The v1 tool raised ValueError("Error 3") on an unknown form, "Error 4" on an unknown clause."""
    code = "Error 3" if text.startswith("Error executing tool get_clause: form") else "Error 4"
    return f"Error executing tool get_clause: {code}"


async def main(version: str) -> None:
    async with Host(config.MCP_CONFIG_FILE) as host:
        if version == "v1":
            for t in host.tools:
                if t["name"] == "policy-docs__get_clause":
                    t["description"] = V1_DESCRIPTION

        async def call(name, args):
            text, err = await host.call(name, args)
            if version == "v1" and err and name == "policy-docs__get_clause":
                text = v1_error(args, text)
            return text, err

        trace = Trace(ROOT / "week9" / "traces" / f"error_replay_{version}.jsonl")
        trace("QUERY", text=QUERY, version=version, model=config.AGENT_MODEL)
        messages = [{"role": "user", "content": QUERY}]
        for i, (name, args) in enumerate(PREFIX, 1):
            text, err = await call(name, args)
            tag = "REPLAYED" if i < len(PREFIX) else "FAILING_CALL"
            trace(tag, tool=name, args=args, is_error=err, text=text[:600])
            messages.append({"role": "assistant", "content": [
                {"type": "tool_use", "id": f"replay_{i}", "name": name, "input": args}]})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": f"replay_{i}", "content": text,
                 **({"is_error": True} if err else {})}]})

        tokens = 0
        for lap in range(1, 7):                       # the model takes over from here
            resp, usage = provider.chat_with_tools(
                model=config.AGENT_MODEL, system=host.system_prompt(), messages=messages,
                tools=host.tools, max_tokens=config.AGENT_MAX_TOKENS_PER_CALL, timeout=120)
            tokens += usage["input_tokens"] + usage["output_tokens"]
            messages.append({"role": "assistant", "content": [to_param(b) for b in resp.content]})
            calls = [b for b in resp.content if b.type == "tool_use"]
            if not calls:
                trace("ANSWER", text=text_of(resp), laps_after_failure=lap, tokens_after_failure=tokens)
                break
            results = []
            for c in calls:
                trace("TOOL_CALL", lap=lap, tool=c.name, args=c.input)
                text, err = await call(c.name, c.input)
                trace("RESULT", lap=lap, tool=c.name, is_error=err, text=text[:600])
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": text,
                                **({"is_error": True} if err else {})})
            messages.append({"role": "user", "content": results})
        trace.save()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "v2"))
