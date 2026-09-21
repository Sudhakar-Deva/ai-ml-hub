"""Week 7 — the claims agent, the fixed workflow it races, and the race.

    python -m app.agents.agent    --all              # the loop
    python -m app.agents.workflow --all              # the same task, no loop
    python -m app.agents.race                        # both, same 10 claims -> race.csv
    python -m app.agents.tools    --diff             # third-tool description diff

Same model, same tools (app/agents/tools.py), same output contract
(app/agents/contract.py). The only thing that differs is who picks the next step.
"""
