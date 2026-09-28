# Week 8 · Task Set D: the outcome-vs-trajectory gap in the claims agent

This is the Week 7 agent, unchanged: same model (`openai/gpt-oss-120b` on Groq), the same three tools, and the same 10 claims
([evals/w7/claims.jsonl](../evals/w7/claims.jsonl)). The outcome eval (`contract.grade`) scores **what** the agent answered.
[trajectory_eval.py](../backend/app/agents/trajectory_eval.py) scores **how** it got there.

## Run it (from `backend/`)

```bash
python -m app.agents.trajectory_eval run --tag before                       # 10 claims, paid
python -m app.agents.trajectory_eval run --tag after --mitigation replan    # 10 claims, paid
python -m app.agents.trajectory_eval score --tag before                     # offline -> week8/results_before.md
python -m app.agents.trajectory_eval compare before after                   # offline -> week8/regression_before_vs_after.md
python -m pytest tests/test_trajectory_eval.py tests/test_agents.py         # scorer + re-plan, no network
```

`run` saves every trajectory to [evals/w8/runs/](../evals/w8/runs/): each call's arguments, and for a search the clauses and
dollar amounts it returned. Scoring is pure over those files, so changing the scorer never needs another paid run.

Generated reports: [results_before.md](results_before.md) · [results_after.md](results_after.md) ·
[regression_before_vs_after.md](regression_before_vs_after.md) · run logs in [logs/](logs/).

---

## 1. The 10 expected tool sequences (asserted in code)

`G` = get_claim, `S` = search_policy, `P` = compute_payout. **Alt** marks a case that accepts more than one path; those are
asserted as a *set*. The evidence (`must_see`) is also a set: the clause has to have been retrieved at some point, in any
search, in any order.

| claim | class | accepted paths | alt? | must_see (clause the decision turns on) |
|---|---|---|---|---|
| 10001 | clean | `G S P` · `G S S P` | **alt** | HO-0304 E-17 (sudden burst is *not* excluded) |
| 10002 | exclusion | `G S P` · `G S S P` | **alt** | HO-0304 E-15 |
| 10003 | exclusion | `G S P` · `G S S P` | **alt** | HO-0304 E-19 |
| 10004 | policy-line trap | `G S P` · `G S S P` | **alt** | **DP-0110** E-17; searching `homeowners` is an invalid argument |
| 10005 | limit | `G S P` · `G S S P` · `G S S S P` | **alt** | CO-0715 coverage grant ($250 deductible) **and** a CO-0715 exclusion |
| 10006 | exclusion | `G S P` · `G S S P` | **alt** | CO-0715 E-31 |
| 10007 | exclusion | `G S P` · `G S S P` | **alt** | HO-0304 E-20 |
| 10008 | limit | `G S P` · `G S S P` | **alt** | HO-0521 B (jewelry $2,500) |
| 10009 | missing notes | `G` · `G P` | **alt** | none: UNDETERMINED needs no wording |
| 10010 | exclusion | `G S P` · `G S S P` | **alt** | CO-0715 E-33 |

Why these are the alternates (the full reasoning is in the code comments):

- **Two searches are always accepted.** Week 7 measured that a notes-worded query misses E-17 and E-15, so a reformulated
  second search is correct behaviour, not waste.
- **10005 needs two things,** the deductible and the exclusions. They can arrive in one, two or three searches, in either order.
- **10009 can stop or call the payout tool.** Stopping after `get_claim` and calling `compute_payout("undetermined")` both honour the rules.
- **The notes-before-policy / policy-before-notes ambiguity in the brief doesn't arise here.** The notes arrive *inside*
  `get_claim`, which has to come first because it's the only source of the policy line. Evidence order is never asserted.
- **What is asserted strictly:** every decided claim ends in `P`. That's contract rule 5, "payable_amount comes from
  compute_payout", and it's in the agent's own system prompt. §3 gives the gap under a lenient reading as well.

**Argument validity** checks every argument against what was real at that moment in the run:

- the claim number matches the claim
- `policy_line` is the claim's own line
- the excess is either the claim file's excess or a figure the agent had retrieved
- the special limit is a figure the agent had retrieved
- `covered_amount` is a figure from the claim file (the claimed total or an estimate line in the notes)
- every cited exclusion code exists on that line **and** appeared in a retrieved clause
- a call to a tool that doesn't exist counts as an invalid call

## 2. Results: before (no mitigation)

| metric | value |
|---|---|
| outcome pass rate | **100%** (10/10) |
| trajectory pass rate | **20%** (2/10) |
| tool-choice accuracy | **68.8%** (22/32 calls align to an accepted path) |
| argument validity rate | **94.0%** (47/50 args) |
| step efficiency (taken / needed) | **0.96**, worst claim **4.00** |
| cost / claim | **p50 $0.00093 · max $0.00234** (mean $0.00113) |
| tokens / claim | p50 5,238 · max 14,452 |
| latency / claim, net of 429 sleeps | p50 3.6 s · max 5.5 s |

The step efficiency of 0.96 looks better than 1.0 because the agent **skipped** steps; it isn't a sign of an efficient run. The
cost spread is 2.5× (p50 $0.00093 vs max $0.00234): 10001 searched twice ("deductible water damage", then "deductible"),
re-sending ~6 kB of policy text on every later lap.

Failure modes, before: `missing_step` **7** · `hallucinated_tool` 3 · `invalid_argument` 3 · `extra_steps` 1. All other
modes are 0, including `skipped_evidence`.

## 3. The gap: **+80 points** (100% outcome − 20% trajectory)

Eight claims got the right answer down a path the eval rejects.

**Named case: CLM-2026-10008 (jewelry theft), correct $2,500 payout, and `compute_payout` was never called.**

```
lap 1  get_claim({"claim_number": "CLM-2026-10008"})
lap 2  search_policy({"policy_line": "homeowners", "query": "theft coverage", "k": 5})
          -> HO-0521 | B. Other special limits
          -> HO-0608 | SECTION I — DUTIES AFTER LOSS
          -> HO-0521 | LIMITS AND SUB-LIMITS ENDORSEMENT
          -> HO-0521 | SECTION II — HOW THESE LIMITS APPLY
          -> HO-0304 | SECTION I — EXCLUSIONS / E-22
final   PARTIAL  codes=[]  payable=2500
        reason: Special limits for jewelry theft apply (...:0004); deductible applied first, then $2,500 limit caps payout.
```

**The wrong path:** `G S` then answer. The agent claims "deductible applied first", but no deductible ever reached the
arithmetic tool. The payout is the model's own mental arithmetic, with no audit trail for the $500 excess.

**Why it's a time bomb:** in the after run the same claim *did* call the tool, as
`compute_payout(partial, covered_amount=2500, excess=500, special_limit=null)`. It passed the limit in as the covered amount,
which applies the cap *before* the deductible, against HO-0521 §II ("Deductible first"). Result: **$2,000, outcome FAIL**.
The before-run's $2,500 passed only because the $2,500 cap hides the order of operations
($6,000 − $500 = $5,500 → capped at $2,500). The outcome eval couldn't have caught this. The trajectory eval flagged the path
on the first run.

**What the gap is *not*:** `skipped_evidence` was **0/10**. On these 10 claims the agent always retrieved the governing
clause (E-17, E-15, …) in its first search. The brief's "never opened the exclusions" failure didn't happen in this run. What did
happen is the neighbouring one: the agent read the wording, then **skipped the tool that turns it into a number**.

**Sensitivity:** if `P` were optional on DENIED claims (payable 0 is trivially right), then 10002, 10004, 10006 and 10010 would
pass. Trajectory pass would be 60% and **the gap +40 pts**. I report +80 because rule 5 is in the agent's own prompt and an auditor
would ask for the calculator of record on every claim. The lenient number is here so the gap can't be called inflated.

## 4. One mitigation: re-planning on `missing_step`

Top mode: `missing_step`, 7/10. The mitigation, and the only change between the runs: **re-planning**. When the agent tries
to finish a COVERED, PARTIAL or DENIED claim and `compute_payout` isn't on its path, the loop sends it back **once**
with the rule it skipped. It isn't told the answer, and the four budgets still bound the extra lap.
Diff: [mitigation.diff](mitigation.diff) (+21 lines in [agent.py](../backend/app/agents/agent.py)).
It is enabled only by `--mitigation replan`, so the before and after runs execute identical code otherwise.

| | before | after |
|---|---|---|
| **`missing_step` (top mode)** | **7** | **0** |
| trajectory pass rate | 20% | 70% |
| **gap (outcome − trajectory)** | **+80 pts** | **+20 pts** |
| tool-choice accuracy | 68.8% | 88.2% |
| outcome pass rate | 100% | **90%** (10008, see §5) |

**The price, measured.** The re-plan fired on 6 claims (10002, 10003, 10004, 10006, 10007, 10010). On those 6, against their own before-runs:

| price | per re-planned claim | whole run (10 claims) |
|---|---|---|
| tokens | **+5,835 mean** (+6,699 max) | p50 5,238 → 10,207 (**+95%**) |
| cost | **+$0.00096 mean** (+$0.0011 max) | p50 $0.00093 → $0.00174 (**+87%**) · mean $0.00113 → $0.00173 |
| laps | +1.8 mean (+3 max) | p50 3.5 → 5 |
| latency, net of 429 sleeps | **+2.2 s mean** (+5.3 s max) | p50 3.6 s → 5.7 s |
| step efficiency | | 0.96 → 1.21 |

Max cost per claim didn't move ($0.00234 → $0.00232), because the most expensive claim (10001) never re-planned. The price comes
from each re-plan lap re-sending the whole conversation, policy text included, to get a `P` call that returns `0` on a denial.
That's roughly a doubling of the p50 bill, paid for an audit trail. It isn't free.

## 5. Regression check: every mode, before → after

| mode | before | after | Δ | verdict |
|---|---|---|---|---|
| missing_step | 7 | 0 | −7 | targeted, fixed |
| hallucinated_tool | 3 | 2 | −1 | better (10003, 10007 fixed · 10004 **new**: tool `commentary` · 10009 still `JSON`) |
| invalid_argument | 3 | 3 | 0 | **same count, different claims:** 10003/10007 fixed; **10008 worse** (limit passed as covered_amount) and 10004 new (the `commentary` call) |
| contradicts_tool | 0 | 1 | +1 | **NEW:** 10009 called `compute_payout("covered", 11000, 1000)`, then answered UNDETERMINED / $0 |
| extra_steps | 1 | 1 | 0 | unchanged (10009) |
| skipped_evidence | 0 | 0 | 0 | checked, none |
| out_of_order | 0 | 0 | 0 | checked, none |
| fabricated_citation | 0 | 0 | 0 | checked, none |
| budget_exhausted | 0 | 0 | 0 | checked, none |
| no_contract | 0 | 0 | 0 | checked, none |

**What got worse, named:**

- **CLM-2026-10008 went from outcome PASS to FAIL.** Its payout call put the limit in the wrong argument (§3).
- **`contradicts_tool` appeared on CLM-2026-10009.**

**Attribution.** The re-plan did **not** fire on either claim (`replans: 0` in [after.jsonl](../evals/w8/runs/after.jsonl)).
Both agents called `compute_payout` on their own, so these are run-to-run variance in gpt-oss, not the mitigation's
code path. With one run per claim I can't prove that, so both count against the after-run anyway.

**What 10008 shows.** Forcing the payout tool into the path moves the risk from "skipped the calculator" to
"fed the calculator wrong inputs". The next mitigation to test would be argument validation on `compute_payout`, which is the
mode `invalid_argument` points at. Per the brief it isn't shipped alongside this one.

## Caveats

- **One run per claim, per arm.** The key is on Groq's free tier (8,000 tokens/minute, and about 200k/day). The two arms used
  67k and 103k tokens, which leaves no room for repeats today. A mode moving by 1 is within noise; `missing_step` moving 7 → 0 is not.
- **Wall-clock budget was raised to 400 s for the eval only** (`config.W8_WALL_CLOCK_S`). Otherwise the 90 s budget fires on
  Groq's 429 sleeps and scores the provider's rate limit as the agent's failure. Sleeps are measured
  (`llm.rate_limit_wait_s`) and subtracted from every latency above. The other three budgets are the Week 7 values.
- **Harness fix, applied to both arms.** gpt-oss sometimes calls a tool that doesn't exist (`json`, `JSON`, `commentary`). Groq
  rejected that with a 400, which crashed the first before-run. [llm.py](../backend/app/llm.py) now returns it as the call the
  model made, so the loop answers "unknown tool", as it would on Anthropic, and the eval counts it as `hallucinated_tool`.
- **Scorer revised once, after the after-run.** Three blind spots showed up:
  - `covered_amount` wasn't traced to the claim file, which is how 10008's $2,500 got through
  - there was no check that the answer agrees with the payout call the agent made
  - a hallucinated tool was also being counted as `out_of_order`

  Both runs were re-scored with the same revised scorer. The before-run's numbers were unchanged by it.
- **The bonus (indirect injection) wasn't run.** It needs another full 10-claim trajectory pass, and today's token cap is spent.
