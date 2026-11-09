"""The MCP host agent. It knows NO tool by name.

    python -m app.mcphost.agent --list-tools                 # what tools/list returned, per server
    python -m app.mcphost.agent "status of CLM-2026-10002?"  # one query, trace to week9/traces/
    python -m app.mcphost.agent --config other.json "..."    # a different set of servers

Every server comes from the MCP config file (config.MCP_CONFIG_FILE, the same
shape as Claude Desktop's "mcpServers"). Every tool comes from that server's
tools/list. A tool is exposed to the model as "<server>__<tool>", so two servers
can both have a "search" without colliding, and a call is routed back by that
prefix. A server's resources are attached to the system prompt only when the
config lists them under "attach_resources"; the model never calls for them.

Adding a server is a config change. If this file needs editing to reach a new
server, discovery was never real.

Where the model runs: here, in run_query(), via app.llm.chat_with_tools. It runs
between tools/list (which tells it what exists) and tools/call (which carries the
call it chose). The servers never call a model.
"""
import argparse
import asyncio
import json
import os
import re
import sys
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .. import config
from .. import llm as provider
from ..agents.budget import price
from ..agents.llm import text_of, to_param

SEP = "__"
MAX_LAPS = 8

SYSTEM = """You are a claims-triage assistant for homeowners, dwelling-fire and
condominium claims. Answer only from what your tools return and from the context
attached below; never from general insurance knowledge. When a tool returns an
error, read it. If it tells you how to correct the call, correct it and call again.
If it does not, say plainly which call failed and why you cannot answer. Never
guess past a failed call. Name the tool output each statement relies on."""


# --- config ---------------------------------------------------------------------

_VAR = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")


def expand(value: str) -> str:
    """${VAR} and ${VAR:-default} from the environment; ${PYTHON} is this interpreter."""
    def sub(m):
        if m.group(1) == "PYTHON":
            return sys.executable
        return os.environ.get(m.group(1), m.group(2) or "")
    return _VAR.sub(sub, value)


def load_config(path: Path) -> dict[str, dict]:
    servers = json.loads(path.read_text())["mcpServers"]
    for name in servers:
        if SEP in name or not re.fullmatch(r"[A-Za-z0-9-]+", name):
            raise SystemExit(f"server name {name!r}: letters, digits and '-' only (it prefixes tool names)")
    return servers


# --- the host -------------------------------------------------------------------

class Host:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.servers = load_config(config_path)
        self.sessions: dict[str, ClientSession] = {}
        self.info: dict[str, dict] = {}
        self.tools: list[dict] = []          # what the model is shown
        self.context: list[str] = []         # attached resources
        self._stack = AsyncExitStack()

    async def __aenter__(self):
        base = self.config_path.parent
        for name, spec in self.servers.items():
            params = StdioServerParameters(
                command=expand(spec["command"]),
                args=[expand(a) for a in spec.get("args", [])],
                # only what the config passes, on top of the SDK's minimal safe env;
                # the host's own secrets (LLM_API_KEY) never reach a server
                env={k: expand(v) for k, v in spec.get("env", {}).items()},
                cwd=str((base / expand(spec["cwd"])).resolve()) if spec.get("cwd") else None,
            )
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            init = await session.initialize()
            self.sessions[name] = session
            self.info[name] = {"server": init.serverInfo.name, "version": init.serverInfo.version,
                               "protocol": init.protocolVersion, "tools": []}
            for tool in await _list_all_tools(session):
                self.info[name]["tools"].append(tool.name)
                self.tools.append({"name": f"{name}{SEP}{tool.name}",
                                   "description": f"[{name}] {tool.description or ''}".strip(),
                                   "input_schema": tool.inputSchema})
            for uri in spec.get("attach_resources", []):
                res = await session.read_resource(uri)
                body = "\n".join(c.text for c in res.contents if hasattr(c, "text"))
                self.context.append(f"--- resource {uri} (from {name}) ---\n{body}")
        return self

    async def __aexit__(self, *exc):
        await self._stack.aclose()

    def system_prompt(self) -> str:
        return SYSTEM + ("\n\nAttached context:\n" + "\n\n".join(self.context) if self.context else "")

    async def call(self, qualified: str, args: dict) -> tuple[str, bool]:
        """Route "<server>__<tool>" to that server's tools/call. -> (text, is_error)"""
        server, _, tool = qualified.partition(SEP)
        session = self.sessions.get(server)
        if session is None or tool not in self.info[server]["tools"]:
            return f"unknown tool {qualified!r}; available: {[t['name'] for t in self.tools]}", True
        res = await session.call_tool(tool, args)
        text = "\n".join(c.text for c in res.content if getattr(c, "type", "") == "text")
        if not text and res.structuredContent is not None:
            text = json.dumps(res.structuredContent)
        return text, bool(res.isError)


async def _list_all_tools(session: ClientSession) -> list:
    tools, cursor = [], None
    while True:
        page = await session.list_tools(cursor=cursor) if cursor else await session.list_tools()
        tools += page.tools
        cursor = page.nextCursor
        if not cursor:
            return tools


# --- one query --------------------------------------------------------------------

class Trace:
    def __init__(self, path: Path | None, echo: bool = True):
        self.path, self.echo, self.events = path, echo, []

    def __call__(self, event: str, **fields):
        self.events.append({"event": event, **fields})
        if self.echo:
            extra = "  ".join(f"{k}={json.dumps(v) if not isinstance(v, str) else v}" for k, v in fields.items())
            print(f"{event:<10} {extra}", flush=True)

    def save(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("".join(json.dumps(e) + "\n" for e in self.events))


async def run_query(host: Host, query: str, trace: Trace) -> str:
    trace("QUERY", text=query, model=config.AGENT_MODEL, config=str(host.config_path.name))
    for name, i in host.info.items():
        trace("DISCOVER", server=name, server_info=f"{i['server']} {i['version']}", protocol=i["protocol"],
              tools=i["tools"])
    messages = [{"role": "user", "content": query}]
    tokens_in = tokens_out = 0
    answer = ""
    for lap in range(1, MAX_LAPS + 1):
        # >>> the ONLY model call: host side, between tools/list and tools/call
        resp, usage = provider.chat_with_tools(
            model=config.AGENT_MODEL, system=host.system_prompt(), messages=messages,
            tools=host.tools, max_tokens=config.AGENT_MAX_TOKENS_PER_CALL, timeout=120)
        tokens_in += usage["input_tokens"]
        tokens_out += usage["output_tokens"]
        messages.append({"role": "assistant", "content": [to_param(b) for b in resp.content]})
        calls = [b for b in resp.content if b.type == "tool_use"]
        if not calls:
            answer = text_of(resp)
            break
        results = []
        for c in calls:
            trace("TOOL_CALL", lap=lap, tool=c.name, args=c.input)
            text, is_error = await host.call(c.name, c.input)
            trace("RESULT", lap=lap, tool=c.name, is_error=is_error, text=text[:600])
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": text,
                            **({"is_error": True} if is_error else {})})
        messages.append({"role": "user", "content": results})
    else:
        answer = f"(stopped after {MAX_LAPS} laps)"
    trace("ANSWER", text=answer, laps=lap, tokens=tokens_in + tokens_out,
          cost_usd=round(price(config.AGENT_MODEL, tokens_in, tokens_out), 6))
    return answer


def discovery_report(host: Host) -> str:
    lines = [f"config: {host.config_path.name}"]
    total = sum(len(i["tools"]) for i in host.info.values())
    for name, i in host.info.items():
        lines.append(f"  {name}  ({i['server']} {i['version']}, protocol {i['protocol']}): "
                     f"{len(i['tools'])} tools  {i['tools']}")
    lines.append(f"total tools/list: {total}  {[t['name'] for t in host.tools]}")
    return "\n".join(lines)


async def _main(a) -> None:
    async with Host(Path(a.config)) as host:
        if a.list_tools:
            report = discovery_report(host)
            print(report)
            if a.out:
                Path(a.out).write_text(report + "\n")
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        trace = Trace(config.WEEK9_DIR / "traces" / f"{a.name or 'query'}_{ts}.jsonl")
        await run_query(host, a.query, trace)
        trace.save()
        print(f"\ntrace -> {trace.path.relative_to(config.ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--config", default=str(config.MCP_CONFIG_FILE))
    ap.add_argument("--list-tools", action="store_true")
    ap.add_argument("--out", help="with --list-tools: also write the report here")
    ap.add_argument("--name", help="trace file prefix")
    a = ap.parse_args()
    if not a.list_tools and not a.query:
        ap.error("give a query, or --list-tools")
    asyncio.run(_main(a))


if __name__ == "__main__":
    main()
