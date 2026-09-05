/* Grain: one row per region and sex for the latest available quarter. */
WITH latest_period AS (
    SELECT max(period_end) AS period_end
    FROM fact_public_indicator FINAL
    WHERE source_id = 'nso_labour_region_sex_json_2569'
      AND source_role = 'authoritative'
      AND metric_name = 'labour_force_thousand_persons'
)
SELECT
    geography_name AS region_name,
    round(sum(value), 2) AS labour_force_thousand_persons
FROM fact_public_indicator FINAL
WHERE source_id = 'nso_labour_region_sex_json_2569'
  AND source_role = 'authoritative'
  AND metric_name = 'labour_force_thousand_persons'
  AND period_end = (SELECT period_end FROM latest_period)
GROUP BY region_name
ORDER BY labour_force_thousand_persons DESC;
