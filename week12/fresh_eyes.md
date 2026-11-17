# Fresh-eyes note

**Status: NOT YET RUN BY ANOTHER SQUAD.** The brief needs a real person from another squad (Thursday) to clone the
repo, run it from the README, and call our MCP server from *their* agent. That can't be produced by this squad and
mustn't be invented. Fill in the table below after the session, unedited.

| | |
|---|---|
| reviewer (name, squad) | _to fill_ |
| date | _to fill_ |
| what they ran | _to fill_ |
| where they stumbled | _to fill_ |
| what we changed because of it | _to fill_ |
| what our MCP server returned to their agent | _to fill: paste the `mcp.policy-docs.*` server spans from week12/obs/mcp_server_spans.jsonl for their session_ |

## What to hand the reviewer

1. Clone the repo, then `./run.sh setup`, put an LLM key in `.env`, then `./run.sh triage CLM-2024-20001`.
2. To call **our** server from their own MCP host, add this to their config. It's the same entry we use, with
   `cwd` set to their clone's `backend/`:

```json
"policy-docs": {
  "command": "<their clone>/.venv/bin/python",
  "args": ["-m", "app.mcp_servers.policy_server"],
  "cwd": "<their clone>/backend",
  "env": {"TRIAGE_VERSION": "triage-v2", "ANONYMIZED_TELEMETRY": "False",
          "W12_MCP_SPAN_FILE": "<their clone>/week12/obs/mcp_server_spans.jsonl"}
}
```

3. Tools they'll discover: `search_policy(query, policy_line, loss_date, k)` and `get_clause(form_number, clause, loss_date)`.

## What our MCP server can hand another squad's agent (answer this out loud on Friday)

- **Policy wording only.** Clause text, form number, edition and the dates that edition was in force. The server
  has no claim data: it never reads the claims store or the adjuster notes.
- **What it logs** is one span per call: the redacted arguments, the ids it returned, latency, and the caller's trace
  id if one was sent in `_meta`. If their agent puts a claimant's name in a search query, the server's span log
  stores `[NAME]`, not the name. It does not echo the query back in the result.
- **What it does not protect.** Their agent's *own* logs and their model provider see whatever their agent sends,
  including anything they put in a query. Our redaction runs on our side only.
