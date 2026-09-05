/* Grain: one row per month; do not sum reference_value (annual budget repeats per ministry). */
SELECT
    period_end,
    round(sum(value), 2) AS monthly_expenditure_million_baht
FROM fact_public_indicator FINAL
WHERE source_id = 'mof_budget_monthly_json_api_2026'
  AND source_role = 'authoritative'
  AND metric_name = 'monthly_expenditure_million_baht'
GROUP BY period_end
ORDER BY period_end;
