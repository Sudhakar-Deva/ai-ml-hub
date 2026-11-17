# Architecture: one page

```
 ./run.sh triage CLM-2024-20001          (one command → backend/app/triage/run.py, the one entry point)
        │  trace_id = tr_xxxxxxxxxxxx  ─────────────── carried in every MCP request's _meta, never in tool args
        ▼
 ┌─────────────────────┐   MCP stdio    ┌──────────────────────────────────────┐
 │ 1 INTAKE            │──────────────▶│ claims-system  (vendored, 3rd party)  │  get_claim_status
 │   FNOL + notes      │◀──────────────│ data/policies/claims_store.json       │  get_adjuster_notes
 └─────────┬───────────┘   raw PII      └──────────────────────────────────────┘  (intake only: not shown to the model)
           ▼
 ┌─────────────────────┐
 │ 2 REDACT            │  names · addresses · injuries → [NAME] [ADDRESS] [INJURY]  BEFORE the model sees the notes
 └─────────┬───────────┘
           ▼
 ┌──────────────────────────────────────────────┐        ┌───────────────────────────────────────────────┐
 │ 3 AGENT LOOP (Week 7, hand-built, budgeted)   │  MCP   │ policy-docs  (OUR server, Week 9)              │
 │   ★ MODEL CALL every lap: gpt-oss-20b (Groq)  │──────▶│ search_policy(query, line, loss_date)          │
 │   tools = local + MCP discovered at runtime  │◀──────│   └─ Week 3-4 retriever: hybrid BM25+dense RRF │
 │   ├ check_coverage_in_force  (register)      │        │      + WHERE effective_from ≤ loss ≤ effective_to│
 │   ├ lookup_policy            (register)      │        │ get_clause(form, clause, loss_date)            │
 │   ├ policy-docs__search_policy  (discovered) │        │ writes its own span under the trace id ────┐   │
 │   └ refer_to_adjuster   ← the ONLY exit      │        └────────────────────────────────────────────┼──┘
 └─────────┬────────────────────────────────────┘                     Chroma (local) + MiniLM (local)  │
           ▼                                                                                          │
 ┌─────────────────────┐                                                                              │
 │ 4 GUARD (code)      │  decision words removed · each citation's edition checked vs the one in force│
 └─────────┬───────────┘                                                                              │
           ▼                                                                                          ▼
 ┌─────────────────────┐   week12/obs/traces.jsonl  ◀── one record per request, redacted on write, server spans merged
 │ 5 REFERRAL + TRACE  │   (spans: intake · redact · llm.generation ×laps · tool/mcp calls · guard · server)
 └─────────────────────┘

 OFFLINE, same traces:  suite.py (8 assertions, code) → judge.py (★ MODEL CALL: gpt-oss-120b, 1 per case)
                        → trajectory.py (no model) → eval_report.md
```

## Where the model calls happen

Only two places. Every **agent lap** is one `gpt-oss-20b` call: about 4 laps per claim, and each lap re-sends the
whole conversation. Each **judge** verdict is one `gpt-oss-120b` call, offline, during evals only. The two MCP servers,
the retriever, the register tools, redaction and the guard make no model call.

## Where the money goes

From the v2 suite run (`evals/w12/runs/v2-after`, n=26):

| stage | $ per claim | share |
|---|---|---|
| intake (claims-system MCP) | $0 | 0% |
| redaction, register tools, guard | $0 | 0% |
| retrieval (policy-docs MCP → local Chroma + BM25) | $0 | 0% |
| **agent laps (`gpt-oss-20b`)** | **$0.000579 mean** (6,287 tokens, 4 laps) | **100%** |

Every dollar is model tokens, and most of them are the same prompt re-sent on each lap: system prompt, tool schemas and
FNOL are ~1,000 tokens before the claim's own tool results. The money is small. The token **count** is what breaks
first: see [cost_and_10x.md](cost_and_10x.md).
