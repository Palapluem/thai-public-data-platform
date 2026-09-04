# Architecture

## Locked decision

```text
CGD / OCSC Excel
        ↓
Python ingestion
        ↓
Raw landing (local first; optional GCS later)
        ↓
PostgreSQL: raw → staging → core
        ↓
Data Quality Gate
        ↓
ClickHouse analytical serving
        ↓
Analytical SQL
```

Apache Airflow orchestrates the flow. Docker Compose provides the reproducible local runtime. GitHub Actions is CI only.

## Component responsibilities

| Component | Owns | Does not own |
|---|---|---|
| `src/thai_data_platform/ingestion` | open source files, source metadata, raw evidence | database business joins |
| `src/thai_data_platform/transform` | source-specific parsing and normalization | Airflow scheduling |
| `src/thai_data_platform/storage` | local landing and optional object-store adapter | core business semantics |
| `src/thai_data_platform/warehouse` | PostgreSQL/ClickHouse load boundaries | parsing Excel layouts |
| `src/thai_data_platform/quality` | reusable checks and gate decision | retries/scheduling |
| `dags/` | task dependency, retries, run context, operator calls | parser/transform/DQ implementation |
| `sql/postgres/` | schema, indexes, constraints, migrations | source file parsing |
| `sql/clickhouse/` | serving tables/views optimized for reads | canonical correction workflow |
| `analytics/queries/` | analyst-facing SQL with grain filters | ingestion state changes |

## Data flow and transaction boundary

1. `prepare_run` creates a run id and records requested source releases.
2. Source ingestion computes SHA-256 before parsing and writes immutable local landing evidence.
3. A transaction writes `raw.source_file`, `raw.workbook_sheet`, `raw.cell` and source-aligned staging rows.
4. `validate_staging` runs structural and semantic checks. It must not silently coerce a missing required key into a valid row.
5. Only a passing run can publish `core` rows. Staging can retain typed numeric values rejected by DQ for diagnosis; core publication is transactional and keeps the previous successful core snapshot available until commit succeeds.
6. `quality_gate` applies severity policy. Any blocking error or threshold breach prevents ClickHouse publishing.
7. `publish_clickhouse` replaces or upserts only the approved run/read model according to the serving contract.
8. `analytics_smoke` runs representative SQL and records row-count/result-shape evidence.

If any step fails, the run is marked failed in `ops.pipeline_run`; no partial core or ClickHouse publish is considered successful.

## Idempotency and lineage

- `sha256` is the content identity of a source release; filename alone is not identity.
- A repeated ingestion of identical bytes is a new operational attempt but does not create a second canonical release or duplicate fact grain.
- Every staged/core row carries a source-file reference and source sheet/row lineage.
- Raw cells preserve the original non-empty cell value plus sheet, row and column coordinates.
- `ops.pipeline_run` records status, timestamps, source hashes, counts and DQ outcome.

## Source-specific boundaries

### CGD

The report can contain `disbursement` and `expenditure` views, and expense categories `current`, `investment` and `total`. These are separate semantic axes. The transform must preserve them rather than flattening them into one ambiguous spend measure.

### OCSC

Workforce data contains employment-type counts and profile metrics such as age, gender and education. A workforce row is not interchangeable with a single employee record. Metric name, group and unit are part of the grain.

## Data-quality gate policy

Blocking examples are missing required keys, zero-row extraction, duplicate natural grain, negative financial amounts and broken foreign keys. Percentage bounds, reconciliation mismatch and row-count collapse are checked with explicit severity/threshold policy; if configured as blocking for a dataset, they stop publishing. Warnings are retained as evidence and never silently discarded.

## Runtime choices

- PostgreSQL is the authoritative relational database and owns referential integrity.
- ClickHouse receives approved analytical data and is disposable/rebuildable from PostgreSQL core.
- Docker Compose runs PostgreSQL, ClickHouse and Airflow locally on loopback interfaces.
- GCS is intentionally a later adapter; local-first storage keeps the one-day demo deterministic.
- DuckDB is deliberately not used in this canonical architecture; the platform is designed around PostgreSQL truth and ClickHouse serving.

## Operational non-goals

Kafka, Spark, Kubernetes, Terraform, frontend, ML, LLM and non-essential dashboards are outside this build. They would add infrastructure surface without improving the core proof: trustworthy ingestion, constraints, quality gates, idempotency and serving.
