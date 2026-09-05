# Hands-on Practice Exercises

Each exercise has an expected artifact. Do not stop at “the command completed”;
record what the result proves and what it does not prove.

## Level 1 — foundations

### 1. Explain the grain

Read the four public parsers and write one sentence for the grain of each
source. List every field that can make two otherwise similar rows different.

Expected evidence: a table with source, grain, key fields, period field, metric
and additive/non-additive notes.

### 2. Trace one row to raw payload

Choose one canonical CSV or NSO row, find its `record_key`, then query the
corresponding `raw.public_record.payload` and `source_record_number`.

Expected evidence: source ID, release hash, row number, metric, value and the
source URL. Explain whether the trace is sufficient for a reviewer.

### 3. Compare formats

Run the parser unit tests and inspect one record from CSV, nested JSON, HTML
and tabular JSON. Identify one ambiguity that is unique to each format.

Expected evidence: four examples and the parser rule that resolves each one.

### 4. Recompute a percentage

Use the CSV data to calculate `sum(disbursed) / sum(budget_received)` by ministry.
Compare it with the source row percentage and explain why averaging row
percentages can be wrong.

Expected evidence: SQL or notebook, numerator, denominator and reconciliation
comment.

## Level 2 — reliability

### 5. Prove idempotency

Run:

```powershell
python -m thai_data_platform public-run --run-type scheduled ...
python -m thai_data_platform public-run --run-type scheduled ...
```

Expected evidence: both runs are `serving_published`; the second has zero
selected rows, four unchanged statuses and four serving skips. Query counts by
`source_id`, `record_key`, `metric_name` and verify no current duplicate.

### 6. Simulate a later period

Create a temporary copy of the nested JSON, append one month for a ministry,
update its config path and run it as `scheduled`.

Expected evidence: a new content hash, selected rows only after the previous
watermark, `advanced` status and a watermark equal to the new month end.

### 7. Simulate a correction

Copy the CSV, change one existing amount without adding a later period, and run
with `scheduled`. Then query both historical core and current view.

Expected evidence: status `backfill`, watermark does not move backwards, raw
release count increases, and current view resolves the corrected natural key.

### 8. Break the contract

Create a temporary config pointing at an empty file, remove a required source
field in a fixture, or inject a negative value.

Expected evidence: DQ status `quality_failed`, a persisted sample in
`ops.dq_result`, no new approved current rows and a clear error message.

### 9. Test retry recovery

Allow a run to reach core, interrupt or simulate a serving failure, then rerun
the same release. Inspect whether the watermark remains unchanged until
serving succeeds and whether the next run repairs the state.

Expected evidence: a failed operational run, a later successful run, and a
watermark event only after serving completion.

## Level 3 — analytics and operations

### 10. Extend the dashboard

Add a chart for the HTML validation table, but label it validation and build a
reconciliation comparison rather than adding it to authoritative totals.

Expected evidence: source-role filter, matching period, difference amount and a
written explanation of why the table is not additive to the API/CSV.

### 11. Make a metric contract

Define one metric with name, business question, grain, numerator, denominator,
filters, unit, source, freshness and caveats. Add it to
`analytics/metrics/definitions.yml` and create a query test.

Expected evidence: a reviewer can reproduce the metric without asking what a
column means.

### 12. Profile a query

Run `EXPLAIN` or a ClickHouse query profile for one dashboard query. Propose an
index, partition or pre-aggregation only if the plan shows a reason.

Expected evidence: before/after observation and a clear trade-off.

### 13. Design an alert

Write an alert contract for “source has not advanced in 48 hours”. Include
owner, threshold, severity, deduplication, notification route and runbook.

Expected evidence: alert definition plus the exact SQL/metadata query that
feeds it.

### 14. Prepare a deployment rollback

Describe what happens if a new parser or migration is bad. Include image tag,
database migration compatibility, current-view protection, serving rebuild and
operator steps.

Expected evidence: a one-page rollback runbook that does not depend on deleting
history.

## Stretch exercises for an AI Engineer

- build a data-contract test generator from the YAML registry;
- add property-based tests for record-key stability and fiscal date conversion;
- use an LLM only to suggest anomaly hypotheses, then require SQL/DQ evidence
  before accepting one;
- compare pandas and a Parquet scan on a larger synthetic dataset;
- create a semantic layer API that exposes metric definitions and caveats;
- add a lineage endpoint that returns source URL, release hash and raw payload
  coordinates for a dashboard metric.
