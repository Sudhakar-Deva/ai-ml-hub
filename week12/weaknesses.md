# Top 3 known weaknesses (written before any integrated run)

Written **Monday 2026-11-16, before the first integrated suite run**. The brief asks for these on Wednesday; the date is
the real one. Unprompted: nobody had asked, and no eval number existed yet when this was written.

1. **The flood row is short, so it retrieves badly.** HO-0304 E-15 is a one-line table row. In an offline probe before
   the agent existed, a surface-water query ("rain pooled in the garden and came in under the patio door") did not
   return E-15 in the top 5 even with the date filter on: it returned E-16, E-17, E-18, E-20 and E-22. I expect the
   integrated system to miss the flood exclusion on surface-water claims however good the date handling is.
2. **The model may carry the edition from the wrong tool.** The coverage-in-force tool names the editions in force,
   and the wording search returns whatever edition it found. Where they disagree, I expect the model to cite the one it
   read text from (the search result), not the one the in-force check named. That means a 2024 loss cited against 2025
   wording when retrieval is undated.
3. **Three money numbers, two sources.** The policy deductible (register and claims system) and a peril deductible
   (CO-0715's $250 per loss assessment) are different numbers. Sub-limits exist only from their edition's effective
   date (surface water only from 2025-04-01). I expect at least one condo case to report the $1,000 policy deductible,
   and at least one pre-April-2025 surface-water case to report the $15,000 sub-limit that did not exist yet.
