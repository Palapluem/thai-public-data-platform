/* Grain: one row per source release representation; validation sources are visible but not summed. */
SELECT
    source_id,
    source_format,
    source_role,
    count() AS row_count,
    min(period_end) AS min_period_end,
    max(period_end) AS max_period_end
FROM fact_public_indicator FINAL
GROUP BY source_id, source_format, source_role
ORDER BY source_role, source_id;
