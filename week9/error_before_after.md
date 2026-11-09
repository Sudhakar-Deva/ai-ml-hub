# One tool, rewritten: `policy-docs.get_clause`

Our own server ([policy_server.py](../backend/app/mcp_servers/policy_server.py)). Full diff: [get_clause.diff](get_clause.diff).

| | v1 (before) | v2 (after) |
|---|---|---|
| docstring (= the tool description the model reads in `tools/list`) | `Get a clause.` | Says when to use it and when to use `search_policy` instead. Gives the exact format of both arguments with examples, and what NOT to pass (the `"HO-0304 ed. 03-24"` edition string that `search_policy` prints, or a heading as the clause). Says what comes back, and what to do on an error. |
| unknown form | `Error 3` | `form 'HO-0304 ed. 03-24' not found: form_number is the bare form number, two letters, a dash and four digits (like 'HO-0304'), with no edition suffix. Forms on file: CO-0715 (condo), DP-0110 (dwelling_fire), HO-0304 (homeowners), HO-0417 (homeowners), HO-0521 (homeowners), HO-0608 (homeowners). Did you mean 'HO-0304'?` |
| unknown clause | `Error 4` | `clause 'X' not found on HO-0304: clause is an exclusion code like 'E-17' or a section letter like 'B'. Clauses on HO-0304: E-15, …, E-22.` |

Both versions return the error as `result.isError = true` with the message as text, so the model reads it as a tool result
and can act on it. v1's message says *that* the call failed. v2's says *which argument* was wrong and *what a valid one looks like*.

Query in every run: **"Quote clause E-17 of form HO-304 word for word."** Model: `openai/gpt-oss-120b`.

## The same failing call, old error vs new (controlled replay)

[error_replay.py](error_replay.py) rebuilds the natural before-run's conversation up to its first failing call. That's the
same two searches, then the call below, sent through the real host to the real server. The model takes over from there.
In the v1 replay, the server's v1 tool description and v1 error strings are restored (see the script's docstring).
Traces: [error_replay_v1.jsonl](traces/error_replay_v1.jsonl) · [error_replay_v2.jsonl](traces/error_replay_v2.jsonl).

The failing call, identical in both:

```
policy-docs__get_clause({"form_number": "HO-0304 ed. 03-24", "clause": "E-17"})
```

The model copied the edition string out of a `search_policy` result as the form number.

### Before (v1: "Get a clause." / "Error 3")

```
FAILING_CALL get_clause(form_number="HO-0304 ed. 03-24", clause="E-17")
             -> isError  "Error executing tool get_clause: Error 3"
lap 1  get_clause(form_number="HO-0304 ed. 03-24", clause="SECTION I — EXCLUSIONS / E-17")
             -> isError  "Error executing tool get_clause: Error 3"
lap 2  get_clause(form_number="HO-0304", clause="E-17")
             -> ok       "HO-0304 ed. 03-24 · E-17 | E-17 | Water damage resulting from …"
ANSWER  Clause E-17 of form HO-0304 (ed. 03-24): "Water damage resulting from the "sudden and
        accidental" discharge, rupture, or burst of a plumbing supply line …" — Exclusion: No …
```

"Error 3" didn't say which argument was wrong, so the model **changed the argument that was fine** (the clause became a
heading) and failed again. It reached `HO-0304` by guessing. Cost: **2 more calls, 1 more failure, 15,594 tokens** after
the failing call.

### After (v2: docstring as prompt / recoverable error)

```
FAILING_CALL get_clause(form_number="HO-0304 ed. 03-24", clause="E-17")
             -> isError  "Error executing tool get_clause: form 'HO-0304 ed. 03-24' not found: form_number is
                          the bare form number, two letters, a dash and four digits (like 'HO-0304'), with no
                          edition suffix. Forms on file: CO-0715 (condo), DP-0110 (dwelling_fire), HO-0304 …
                          Did you mean 'HO-0304'?"
lap 1  get_clause(form_number="HO-0304", clause="E-17")
             -> ok       "HO-0304 ed. 03-24 · E-17 | E-17 | Water damage resulting from …"
ANSWER  Clause E-17 of form HO-0304 reads: "Water damage resulting from the "sudden and accidental"
        discharge, rupture, or burst of a plumbing supply line within the dwelling – No. This
        exclusion does NOT apply. …" [policy-docs__get_clause]
```

The error named the bad argument and the fix, and the model **corrected exactly that argument on the next call**.
Cost: **1 more call, 0 more failures, 11,051 tokens** after the failing call.

| after the identical failing call | v1 | v2 |
|---|---|---|
| further calls | 2 | 1 |
| further failed calls | 1 | 0 |
| wrong argument changed | yes (clause → heading) | no |
| tokens to the answer | 15,594 | 11,051 |

## Natural runs (no replay), whole query from scratch

| run | calls | failed calls | tokens | trace |
|---|---|---|---|---|
| before (v1) | 5: search, search, get_clause ✗, get_clause ✗, get_clause ✓ | 2 | 24,535 | [error_before_*.jsonl](traces/) |
| after (v2) | 1: get_clause("HO-0304", "E-17") ✓ | 0 | 3,956 | [error_after_*.jsonl](traces/) |

In the natural after-run the failing call **never happened**. The rewritten docstring told the model the form-number
format up front, so it wrote `HO-0304` from the user's `HO-304` on its first call. The docstring prevents the failure,
and the recoverable error fixes it when it happens anyway; the replay above isolates the second effect.
All runs are single samples. The replay is what makes the comparison like-for-like.
