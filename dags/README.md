# Airflow DAG Contract

The executable DAG is [`thai_public_data_pipeline.py`](thai_public_data_pipeline.py). It only wires task dependencies; parser, loader, quality and serving logic remain under `src/thai_data_platform/`.

## DAG identity

- DAG id: `thai_public_data_platform`
- schedule: configurable; local/manual trigger is the deterministic first milestone
- catchup: `false` unless a future backfill contract is approved
- retries: task-level, bounded and observable
- timezone: Asia/Bangkok for business-facing scheduling; timestamps stored in UTC
- parser contract: `config/schema_contracts.json`, injected through `SCHEMA_CONTRACT`
- run classification: `PIPELINE_RUN_TYPE` (`manual` by default; also `scheduled`, `backfill`, `replay`)

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
| `validate_staging` | call reusable schema contract and data-quality checks | inline check implementation |
| `publish_core` | call approved core publisher | bypass gate or publish on failed validation |
| `quality_gate` | evaluate persisted DQ results and fail task when blocking | silently downgrade errors |
| `publish_clickhouse` | call serving publisher for approved run | read raw Excel directly |
| `analytics_smoke` | run documented read-only smoke queries | mutate canonical/serving data |

All business rules belong under `src/thai_data_platform/`. The DAG should stay thin enough that a unit test can verify dependency order without loading a workbook.

## Failure contract

If `validate_staging` or `quality_gate` fails, `publish_core` and `publish_clickhouse` must not report success. Raw/staging/ops evidence remains available for diagnosis and replay.

For a correction or historical release, keep the source file as a new
content-addressed release and set `PIPELINE_RUN_TYPE=backfill`. This labels the
operational intent; it does not overwrite the previous release.

## Multi-format DAG

The second DAG is [`thai_public_multiformat_pipeline.py`](thai_public_multiformat_pipeline.py).
It uses the same thin-DAG boundary for the generic public-indicator path:

```text
run_public_multiformat_pipeline
              ↓
build_public_dashboard
```

The first task calls the reusable parser → DQ → PostgreSQL → ClickHouse
workflow. The second task queries the published serving layer and writes the
portable dashboard artifact. The four registered snapshots and their parser
contracts live under `config/public_sources.yml` and
`src/thai_data_platform/public_sources/`.

The public path records source format and role, preserves raw payloads, selects
scheduled rows after the previous `period_end` watermark, processes equal/older
new releases as corrections, and commits watermark state only after serving
publication. A rerun of the same release should be observable as `unchanged`
and should not add current serving rows.
