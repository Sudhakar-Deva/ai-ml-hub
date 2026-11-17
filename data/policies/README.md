# Policy register, product limits, claims store (Week 12, synthetic)

The capstone brief describes a corpus this repo was never given: motor and household wordings, 2023 and 2025
endorsement sets, 500 claim files, a limits table and coverage-in-force date ranges. What is here is the **smallest
synthetic stand-in** that lets the integrated system be tested on the things the brief cares about. All of it was
written for Week 12 and none of it is real.

| file | what | used by |
|---|---|---|
| `register.json` | coverage-in-force terms per policy number, policy deductible, policy limit. No insured names. | `lookup_policy`, `check_coverage_in_force` |
| `products.json` | sub-limits and peril deductibles by product, each with the clause that sets it and the dates it is in force | `lookup_policy` |
| `claims_store.json` | the 26 suite claims in the vendored claims-system's format (FNOL note + adjuster notes, with names, addresses and injuries left in on purpose) | the `claims-system` MCP server via `CLAIMS_DATA` (vendor code untouched) |

Two endorsement editions were added to `data/endorsements/`, both synthetic: **HO-0304 ed. 01-23** (in force
2023-01-01 to 2024-02-29; the seepage threshold E-19 is 30 days, not 14) and **HO-0304 ed. 04-25** (in force from
2025-04-01; E-15 rewritten so surface water from rainfall is no longer excluded but capped at a $15,000 sub-limit).
The existing ed. 03-24 is now in force 2024-03-01 to 2025-03-31. The other five forms still have one edition each.
