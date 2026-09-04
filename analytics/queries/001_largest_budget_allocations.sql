/*
   Question: which agency/category has the largest allocation?
   Grain: one published source row at CGD's total-expense category.
   The report is a snapshot, so results are ordered within the available
   source release rather than interpreted as a time series.
*/
SELECT
    entity_name,
    entity_type,
    fiscal_year,
    fiscal_year_be,
    as_of_date,
    sumOrNull(allocated_million_baht) AS allocated_million_baht,
    sumOrNull(budget_after_transfer_million_baht) AS budget_after_transfer_million_baht,
    sumOrNull(disbursement_million_baht) AS disbursement_million_baht
FROM analytics.fact_budget_execution FINAL
WHERE report_type = 'disbursement'
  AND expense_category = 'total'
  AND entity_type NOT IN ('summary', 'total')
GROUP BY
    entity_name,
    entity_type,
    fiscal_year,
    fiscal_year_be,
    as_of_date
ORDER BY allocated_million_baht DESC
LIMIT 20;
