/*
   Question: how is workforce distributed by ministry, entity type, metric
   group and metric? Headcount is only summed for person-unit rows. Percentage
   and average-age rows are intentionally not mixed into this measure.
*/
SELECT
    coalesce(ministry_name, '(unassigned)') AS ministry_name,
    entity_type,
    metric_group,
    metric_name,
    fiscal_year,
    fiscal_year_be,
    sumOrNull(fact_workforce_metric.headcount) AS headcount
FROM analytics.fact_workforce_metric FINAL
WHERE source_unit = 'person'
  AND fact_workforce_metric.headcount IS NOT NULL
  AND entity_type != 'total'
GROUP BY
    ministry_name,
    entity_type,
    metric_group,
    metric_name,
    fiscal_year,
    fiscal_year_be
ORDER BY headcount DESC, ministry_name, metric_group, metric_name
LIMIT 100;
