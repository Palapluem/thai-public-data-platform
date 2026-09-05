/* Grain: one row per ministry; rate is recomputed from amounts, never averaged. */
SELECT
    category AS ministry_name,
    round(sumIf(value, metric_name = 'budget_received_million_baht'), 2)
        AS budget_received_million_baht,
    round(sumIf(value, metric_name = 'disbursed_million_baht'), 2)
        AS disbursed_million_baht,
    round(
        100 * sumIf(value, metric_name = 'disbursed_million_baht')
        / nullIf(sumIf(value, metric_name = 'budget_received_million_baht'), 0),
        2
    ) AS calculated_disbursement_rate_pct
FROM fact_public_indicator FINAL
WHERE source_id = 'mof_budget_summary_csv_2568'
  AND source_role = 'authoritative'
  AND entity_type = 'department'
GROUP BY ministry_name
ORDER BY disbursed_million_baht DESC
LIMIT 8;
