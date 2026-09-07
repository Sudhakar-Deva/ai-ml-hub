<!-- TEMPLATE — not yet a prediction. Fill this in only after taxonomy.md
     exists, and commit it BEFORE writing a line of the fix. The point is to be
     able to be wrong on the record; a prediction written after the fix is a
     description. -->

## Prediction — dated, falsifiable, numeric

**Date:** <YYYY-MM-DD, the day this is committed>
**Taxonomy it is based on:** `taxonomy.md` @ <commit hash of the taxonomy>
**Mode I will attack next week:** <the exact mode name from taxonomy.md>
**Current frequency:** <count>/20 = <pct>% · severity <wrongly-denies | wrongly-pays | annoys-adjuster>

**The change:** <one specific change, one variable — e.g. "filter retrieval on
edition_date parsed from the question">

**What I expect, with numbers:**

> <mode name> drops from <pct>% to under <pct>% of a fresh 20-trace random
> sample drawn with seed <seed>, measured on <date>, with no other change to
> the app.

**What would prove me wrong:** <the observation that falsifies it — e.g. "the
mode is still at or above X% in the new sample", or "it drops but mode Y rises
by more than Z">

**What I am NOT predicting:** <the modes this change should not touch, named>
