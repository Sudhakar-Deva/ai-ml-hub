# Week 7 · Task Set D — race the claims agent against a fixed workflow

Same model (`config.AGENT_MODEL`, default `claude-sonnet-5`), same three tools
([tools.py](../backend/app/agents/tools.py)), same rules text and output contract
([contract.py](../backend/app/agents/contract.py)). The one variable is who picks
the next step.

## Run it (from `backend/`)

```bash
python -m app.agents.agent    --all          # the agent, one command
python -m app.agents.workflow --all          # the workflow, one command
python -m app.agents.race                    # both over the same 10 claims -> evals/w7/race.csv

# the budget-termination log (deliverable 4)
python -m app.agents.agent --claim CLM-2026-10007 --max-iters 2 --log ../week7/budget_termination.log

python -m app.agents.tools --diff            # -> week7/tool_descriptions.diff
python -m app.agents.tools --check           # one job per tool, enums typed, no overlap
python -m pytest tests/test_agents.py        # loop + all four budgets, no network
```

## 1. Third tool: `compute_payout` ([diff](tool_descriptions.diff))

`compute_payout(claim_status ∈ {covered, partial, denied, undetermined}, covered_amount, excess, special_limit)`:
arithmetic only (excess first, then the special limit, per HO-0521 §II). It
doesn't look anything up and doesn't decide coverage.

The same diff also sharpens the two v1 descriptions, which both claimed the
coverage job ("get a claim and **check it against the policy**" /
"search the policy **to check coverage for a claim**"). In v2 each description
names one job and rules out the other two. `search_policy.policy_line` is now an
enum too. The fix lives in the descriptions, not in the system prompt.
`tools --check` enforces it.

## 2. The workflow ([workflow.py](../backend/app/agents/workflow.py))

`get_claim` → read the notes → `search_policy(query = notes, policy_line)` **once** →
one model call to decide → `compute_payout` → the contract. Every claim takes the
same six steps. It has no `while`, no retry and no second search. The same `Budget` guards its one call.

## 3. The race set ([evals/w7/claims.jsonl](../evals/w7/claims.jsonl))

| class | claims | what forces a step-3 lookup |
|---|---|---|
| clean | 10001 | none: sudden supply-line burst |
| notes_trigger_exclusion | 10002, 10003, 10006, 10007, 10010 | notes reveal flood / 3-week seepage / association deductible / sewer backup + mould / deferred maintenance |
| notes_trigger_limit | 10005, 10008 | notes reveal a loss assessment ($250 form deductible, not the $1,000 policy excess) / jewelry theft ($2,500 sublimit) |
| policy_line_trap | 10004 | dwelling-fire form excludes the sudden burst that homeowners covers |
| missing_notes | 10009 | no notes on file, so the only right answer is UNDETERMINED |

Pass = decision, exclusion codes (required ⊆ cited ⊆ required + optional) and payable within $1.

### Pre-race evidence (measured, no LLM)

What the workflow's single search (query = the notes) returns:

| claim | needs | workflow's top-5 clauses | clause present? |
|---|---|---|---|
| 10001 clean | E-17 (covers the burst) | E-20, E-19, E-21, E-22, conditions | **no** |
| 10002 flood | E-15 | conditions, E-19, E-18, E-20, E-17 | **no** |
| 10003 seepage | E-19 | E-20, E-19, E-21, application, E-22 | yes |
| 10004 DP burst | E-17 (DP) | DP E-23, E-24, E-19, E-17, header | yes |
| 10005 assessment | CO-0715 $250 | E-33, E-34, E-32, loss-assessment §I, E-31 | yes |
| 10006 assoc. deductible | E-31 | §I, E-32, E-33, E-34, E-31 | yes |
| 10007 sewer | E-20 | E-21, E-20, E-18, HO-0521 A, E-17 | yes |
| 10008 jewelry | HO-0521 B | HO-0521 B, HO-0608 ×3, HO-0417 A | yes |
| 10010 riser | E-33 | E-33, §I, E-34, §II, E-32 | yes |

In the 8 of 10 claims where the search finds the clause, the path doesn't need to vary. The
decision rule predicts the agent can only win on **10001 and 10002**, where a
second, reformulated search is the only way to reach the clause.

## 4. Results

**Not run yet: needs `LLM_API_KEY` in `.env`.** `python -m app.agents.race`
writes `evals/w7/race.csv` (the 8 numbers) and prints the table, the agent's
distinct paths and every claim where the two systems disagree. The verdict gets
written from those numbers.

## 5. Verdict

_Pending the race. It has to name the class from the disagreements list, or say
that no class forces an agent, and it has to agree with the table._
