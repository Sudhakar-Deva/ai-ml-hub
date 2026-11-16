# Bonus: AgentCard and the A2A task lifecycle

**AgentCard:** [agent_card.json](agent_card.json). It advertises two skills (`adjudicate-claim`, `summarise-adjuster-notes`),
JSON/text in and JSON out, OAuth2 client credentials with read-only scopes (`claims:read`, `policy:read`), no write scope.

## The failed case on the A2A lifecycle

A2A task states: `submitted → working → (input-required | auth-required) → completed | failed | canceled | rejected`.

What our run did on CLM-2026-10002 with the exclusions worker returning 500:

```
submitted → working → [exclusions worker 500, 500] → completed   (artifact: UNDETERMINED, $0)
```

**It should have ended `input-required`, not `completed` and not `failed`.** The task wasn't finished: no coverage
position was reached, and `completed` hides that from any queue reading task states. It wasn't an unrecoverable error
either, because the facts were gathered and the only missing piece is a coverage check that an adjuster can confirm or
re-trigger. So the right move is to pause with a status message ("exclusions check unavailable (HTTP 500 ×2); confirm
E-15 flood exclusion or retry the check") and resume on the adjuster's reply in the same task. `failed` would only be right
if the claim itself could not be adjudicated (no claim file, no policy line).

## What A2A buys over a plain REST call to the worker

A REST 500 gives you one status code and the caller has to invent everything else. A2A gives the hand-off a shared task
with an id, a defined lifecycle (`input-required` to pause for a human, `failed` vs `completed`), history and push
notifications, so a dead worker becomes a resumable paused task instead of a silent "undetermined, done".
