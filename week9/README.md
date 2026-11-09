# Week 9 · Task Set D: bolt on the claims-system server without touching the agent

The host agent reads its servers from [mcp_servers.json](../mcp_servers.json) and its tools from each server's `tools/list`.
Server two was added by editing that file and nothing else.

| piece | file | owner |
|---|---|---|
| host agent (runs the model) | [backend/app/mcphost/agent.py](../backend/app/mcphost/agent.py) | us |
| server one: policy-docs | [backend/app/mcp_servers/policy_server.py](../backend/app/mcp_servers/policy_server.py) | us |
| server two: claims-system | [vendor/claims_system_mcp/server.py](../vendor/claims_system_mcp/server.py) | Claims Platform team (simulated, vendored) |
| config | [mcp_servers.json](../mcp_servers.json) | us |

**Where the model runs:** only in the host (`agent.py` → `app.llm.chat_with_tools`), between `tools/list` and
`tools/call`. Neither server calls a model.

## Run it (from `backend/`)

```bash
../.venv/bin/python -m app.mcphost.agent --list-tools
../.venv/bin/python -m app.mcphost.agent "Triage CLM-2026-10002: status, adjuster findings, governing exclusion?"
../.venv/bin/python ../week9/wire_capture.py          # raw JSON-RPC -> week9/wire_raw.jsonl
../.venv/bin/python ../week9/error_replay.py v1|v2    # same failing call, old vs new error
../.venv/bin/python -m pytest tests/test_mcp.py       # 12 tests, real stdio servers, no network
```

## Deliverables

| checklist item | file | result |
|---|---|---|
| agent module unchanged | [agent_diff.txt](agent_diff.txt) | **0 changed lines**; blob hash `70672d2f…` identical at both stages |
| config diff adding server two | [config_diff.txt](config_diff.txt) | +12 lines in `mcp_servers.json`, nothing else |
| one query provably calling server two | [traces/stage2_claims_*.jsonl](traces/) | `claims-system__get_claim_status`, then `claims-system__get_adjuster_notes` (also in the vendor's own access log) |
| tool count from `tools/list` | [tool_counts.md](tool_counts.md) | **2 → 4**: `search_policy`, `get_clause` → + `get_claim_status`, `get_adjuster_notes` |
| raw initialize → tools/list → tools/call, annotated | [wire.json](wire.json) (raw: [wire_raw.jsonl](wire_raw.jsonl)) | 7 messages, every top-level field annotated, model-call line stated |
| docstring-as-prompt + recoverable error | [error_before_after.md](error_before_after.md), [get_clause.diff](get_clause.diff) | same failing call: v1 needed 2 more calls (1 more failure); v2 fixed it in 1 call |
| 5-line risk note | [risk_note.md](risk_note.md) | verdict: don't ship as-is; ship to triage only with a scoped token |

## How the "zero lines changed" was proven

1. I built server one and the host, and ran a real query at that stage ([traces/stage1_*.jsonl](traces/)).
2. I recorded `git hash-object` of the agent module and staged it (`git add backend/app/mcphost/ mcp_servers.json`) as the baseline.
3. I added the `claims-system` entry to `mcp_servers.json`.
4. `git diff -- backend/app/mcphost/` (working tree vs that baseline) prints nothing. The hash matches. Only
   `mcp_servers.json` differs.

Every server comes from config and every tool from `tools/list`. The test suite enforces this:
`test_agent_module_names_no_tool_and_no_server` fails if the agent source ever names a tool or a server.

## Design choices the common-mistakes list asks about

- **No hard-coded tools.** Tools are exposed as `<server>__<tool>` from `tools/list`, and calls are routed back by that prefix.
- **No model in a server.** Both servers are lookups.
- **The exclusions schedule is a resource, not a tool.** policy-docs serves `policy://exclusions/<line>`, and the host
  attaches it because the config lists it under `attach_resources`. In the stage-2 triage query the model named E-15 from
  that attached context, without calling out for the list.
- **Unknown claim number is distinguishable from a dead system.** claims-system returns `isError` with
  `claim CLM-2024-88120 not found in claims system`. A system that's down shows up as a connection failure when the host starts.
- **Third-party trust boundary.** Servers get the SDK's minimal environment plus only what the config passes, so the host's
  `LLM_API_KEY` never reaches the vendor process. See [risk_note.md](risk_note.md) for what it *can* reach.

## Notes

- The claims-system server is a **simulation**: there's no real platform team. Its data is generated from
  `evals/w7/claims.jsonl`.
- `serverInfo.version` shows `1.30.0` for both servers. That's the MCP SDK's default, not a server build number.
- Model: `openai/gpt-oss-120b` on Groq. All LLM runs are single samples.
- The bonus (gateway, audit line, scoped token) wasn't done.
