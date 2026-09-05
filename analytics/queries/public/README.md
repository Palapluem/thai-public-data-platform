# Public analytical query contract

These queries read `analytics.fact_public_indicator FINAL`, whose serving grain
is one current row per `(source_id, record_key, metric_name)`. PostgreSQL keeps
the complete release history; ClickHouse uses `ReplacingMergeTree` plus `FINAL`
to expose the latest version of a corrected natural key.

The CSV and nested JSON API are authoritative finance representations with
different grains. The HTML table is intentionally marked `source_role =
'validation'`; it can be reconciled against the authoritative sources but must
not be added to their totals. The API's annual budget is a repeated reference
attribute on each monthly row, so the monthly trend sums only `value`.
