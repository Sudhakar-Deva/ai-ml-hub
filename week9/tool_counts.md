# Tools discovered: 2 before → 4 after

Taken from each server's `tools/list` reply by `python -m app.mcphost.agent --list-tools`, not typed by hand.
Raw reports: [tools_before.txt](tools_before.txt) (server one only) · [tools_after.txt](tools_after.txt) (server one + two).
The claims-system `tools/list` reply itself is message 5 in [wire.json](wire.json).

**2 before → 4 after:**
- before (policy-docs): `search_policy`, `get_clause`
- after (policy-docs + claims-system): `search_policy`, `get_clause`, **`get_claim_status`**, **`get_adjuster_notes`**

| server | before | after | tools (names as `tools/list` returned them) |
|---|---|---|---|
| policy-docs (ours) | 2 | 2 | `search_policy`, `get_clause` |
| claims-system (third-party) | — | 2 | `get_claim_status`, `get_adjuster_notes` |
| **total exposed to the model** | **2** | **4** | `policy-docs__search_policy`, `policy-docs__get_clause`, `claims-system__get_claim_status`, `claims-system__get_adjuster_notes` |

The host prefixes each tool with its server name (`<server>__<tool>`) so tools from different servers can't collide. It
strips the prefix again before `tools/call`.

Resources aren't tools: policy-docs also serves `policy://exclusions/{homeowners,dwelling_fire,condo}`, which the host
attaches to the system prompt because the config lists them under `attach_resources`. They don't count toward the 4, and
the model never calls for them.
