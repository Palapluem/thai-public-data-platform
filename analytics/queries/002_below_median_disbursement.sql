/*
   Question: which comparable entities are below the median disbursement rate?
   The median is calculated within the same filtered CGD snapshot and excludes
   summary/total rows so denominators stay at the entity grain.
*/
WITH eligible AS (
    SELECT
        entity_name,
        entity_type,
        fiscal_year,
        fiscal_year_be,
        as_of_date,
        disbursement_million_baht,
        disbursement_pct
    FROM analytics.fact_budget_execution FINAL
    WHERE report_type = 'disbursement'
      AND expense_category = 'total'
      AND entity_type NOT IN ('summary', 'total')
      AND disbursement_pct IS NOT NULL
),
median_rate AS (
    SELECT quantileExact(0.5)(toFloat64(disbursement_pct)) AS median_disbursement_pct
    FROM eligible
)
SELECT
    eligible.entity_name,
    eligible.entity_type,
    eligible.fiscal_year,
    eligible.fiscal_year_be,
    eligible.as_of_date,
    eligible.disbursement_million_baht,
    eligible.disbursement_pct,
    median_rate.median_disbursement_pct
FROM eligible
CROSS JOIN median_rate
WHERE toFloat64(eligible.disbursement_pct) < median_rate.median_disbursement_pct
ORDER BY eligible.disbursement_pct ASC, eligible.entity_name
LIMIT 50;
