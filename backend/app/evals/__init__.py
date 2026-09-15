"""Week 6 — evals. Measuring whether a change actually helped.

Two kinds of check live here and they are deliberately not the same kind:

  assertions.py  deterministic, free, never has an off day. Format, presence,
                 parseability, and the internal consistency between a denial and
                 the code behind it.
  judge.py       one LLM call, one binary criterion, and a prompt kept in a file
                 so its versions can be diffed.

Anything a regex can decide is not sent to a model. Paying per token to check
that a claim number looks like CLM-2024-88431 buys a slower answer that is
sometimes wrong.
"""
