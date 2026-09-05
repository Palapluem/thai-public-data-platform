# P1 Production Hardening

P0 proves that the baseline can be parsed, quality-gated and served. P1 adds
the operational behaviors that appear when the source publishes a new release
or a correction.

## What was added

- A versioned parser-output contract at `config/schema_contracts.json`.
- Fail-closed detection for missing required columns before staging begins.
- Non-breaking additive columns are logged as contract warnings.
- `run_type` in `ops.pipeline_run`: `manual`, `scheduled`, `backfill` and `replay`.
- `ops.pipeline_run_health` for run duration, source count, row counts and a
  simple operational health classification.
- An integration test that creates a second source release, loads it once and
  records the run as a backfill.
- An analyst-facing metric definition contract under `analytics/metrics/`.

## Why this matters

The source file hash identifies a release by content, not by filename. A
repeated release remains idempotent, while a different release gets its own
raw evidence and fact rows. A backfill is therefore an explicit operational
intent, not a destructive overwrite of the current data.

The schema contract sits before `raw`/`staging` persistence in the reusable
pipeline and Airflow path. A missing required field cannot silently become a
column of nulls in a downstream table.

## Local checks

```powershell
python -m ruff check .
python -m pytest
python -m json.tool config/schema_contracts.json
docker compose config --quiet
```

With the local services running, the full integration suite can be enabled by
setting `RUN_FULL_INTEGRATION=1` together with the local `POSTGRES_URL` and
ClickHouse connection variables. The suite proves the baseline rerun and the
new-release/backfill path.

## Inspect operational evidence

```sql
SELECT
    run_id,
    run_type,
    status,
    health,
    duration_seconds,
    source_count,
    cgd_row_count,
    ocsc_row_count,
    dq_failed_check_count
FROM ops.pipeline_run_health
ORDER BY started_at DESC
LIMIT 10;
```

## Deliberate boundary

This is a production-like local slice, not a claim that the project already
has a complete cloud deployment. The next hardening items are a quarantine
table for rejected releases, explicit watermark selection for late-arriving
data, cross-store atomic serving publication, IAM/secret separation and
alert delivery.
