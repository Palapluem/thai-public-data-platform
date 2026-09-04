# Airflow DAG Contract

The executable DAG is [`thai_public_data_pipeline.py`](thai_public_data_pipeline.py). It only wires task dependencies; parser, loader, quality and serving logic remain under `src/thai_data_platform/`.

## DAG identity

- DAG id: `thai_public_data_platform`
- schedule: configurable; local/manual trigger is the deterministic first milestone
- catchup: `false` unless a future backfill contract is approved
- retries: task-level, bounded and observable
- timezone: Asia/Bangkok for business-facing scheduling; timestamps stored in UTC

## Required task IDs

```text
prepare_run
    ↓
┌────────────┐
ingest_cgd   ingest_ocsc
└──────┬─────┘
       ↓
validate_staging
       ↓
publish_core
       ↓
quality_gate
       ↓
publish_clickhouse
       ↓
analytics_smoke
```

## Task responsibilities

| Task | May do | Must not do |
|---|---|---|
| `prepare_run` | create run context and source-release request | parse Excel |
| `ingest_cgd` | call CGD ingestion entry point with run context | contain CGD parsing logic |
| `ingest_ocsc` | call OCSC ingestion entry point with run context | contain OCSC parsing logic |
| `validate_staging` | call reusable structural/schema checks | inline check implementation |
| `publish_core` | call approved core publisher | bypass gate or publish on failed validation |
| `quality_gate` | evaluate persisted DQ results and fail task when blocking | silently downgrade errors |
| `publish_clickhouse` | call serving publisher for approved run | read raw Excel directly |
| `analytics_smoke` | run documented read-only smoke queries | mutate canonical/serving data |

All business rules belong under `src/thai_data_platform/`. The DAG should stay thin enough that a unit test can verify dependency order without loading a workbook.

## Failure contract

If `validate_staging` or `quality_gate` fails, `publish_core` and `publish_clickhouse` must not report success. Raw/staging/ops evidence remains available for diagnosis and replay.
