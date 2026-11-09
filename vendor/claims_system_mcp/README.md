# claims-system MCP server (vendored)

| | |
|---|---|
| Owner | Claims Platform team (not the assistant team) |
| Version | 0.4.1 |
| Transport | MCP over stdio |
| Tools | `get_claim_status`, `get_adjuster_notes` |
| Needs | `CLAIMS_API_TOKEN` (any non-empty value is accepted in this build) |
| Writes | one JSON line per tool call to `CLAIMS_SYSTEM_LOG` |

Third-party code, vendored as delivered. The assistant reaches it only through
the `claims-system` entry in [mcp_servers.json](../../mcp_servers.json).
The risk assessment is in [week9/risk_note.md](../../week9/risk_note.md).

**Simulation note:** the data in `data/claims.json` is synthetic, generated from
`evals/w7/claims.jsonl`, so the agent sees the same 10 claims it was evaluated
on in Weeks 7 and 8.
