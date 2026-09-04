# Analytical Queries

These queries target the ClickHouse `analytics` serving layer and are also
used as post-publish smoke checks. They expose reporting-period columns and
semantic filters so an analyst can see the population and time caveats before
interpreting a result.

| File | Question | Main guardrail |
|---|---|---|
| `001_largest_budget_allocations.sql` | Which entities have the largest allocation? | CGD `disbursement` + `total` expense grain; excludes summary/total entities |
| `002_below_median_disbursement.sql` | Which comparable entities are below the median rate? | Median is recomputed from the same filtered snapshot |
| `003_workforce_distribution.sql` | How is workforce distributed by organization and metric? | Sums only `source_unit = 'person'`; keeps metric groups separate |
| `004_budget_to_workforce_ratio.sql` | What is the exploratory budget/person ratio? | Uses an explicit allocated → budget-after-transfer fallback and pre-aggregates each source before an exact conservative name join |

Required questions:

1. largest budget allocations
2. below-median disbursement
3. workforce distribution
4. budget-to-workforce ratio

Queries must not combine `total` with detail, `disbursement` with `expenditure`, or OCSC FY 2567 with CGD FY 2569 as if they were the same reporting period.

The fourth query is deliberately labeled exploratory because the current
baseline sources cover different fiscal years. It must not be presented as a
same-period efficiency or productivity KPI. Its `budget_basis` column records
whether the result used the source's `allocated` amount or the explicit
`budget_after_transfer` fallback. The ratio column is named
`budget_million_baht_per_civil_servant` to match that explicit basis.
