# Resume Project Notes

## Project description

Designed and implemented a local-first public data platform that converts
heterogeneous government Excel reports into reproducible, quality-gated and
analyst-ready data products.

## Resume bullets

- Designed an end-to-end batch data platform for two heterogeneous Excel
  sources, handling merged cells, multi-row headers, totals/subtotals and
  source-specific parsing with Python, pandas and openpyxl.
- Built PostgreSQL `raw`, `staging`, `core` and `ops` layers with primary/foreign
  keys, numeric constraints, natural-grain uniqueness and cell-level source
  lineage for auditability.
- Implemented fail-closed data quality gates for required keys, numeric bounds,
  duplicate grain, source identity, row-count collapse and detail-to-total
  reconciliation; invalid fixtures stop downstream publication.
- Added SHA-256 source-release identity and retry-safe publication guards so
  rerunning the same release produces no duplicate facts while a new release
  remains independently queryable.
- Added a versioned schema contract and explicit operational run types for
  manual, scheduled, replay and backfill executions, with integration evidence
  for a second source release.
- Orchestrated the pipeline with an eight-task Apache Airflow DAG and published
  approved PostgreSQL core data to ClickHouse for read-optimized analytical SQL.
- Containerized the local stack with Docker Compose and added GitHub Actions
  CI, unit/integration tests, migration checks, runbooks and architecture
  decision records for reproducible handoff.
- Authored grain-aware analytical queries and a semantic metric contract that
  documents filters and caveats to prevent double counting and misleading
  cross-period comparisons.

## Short interview version

I built a reliable batch data platform for messy public-sector Excel reports.
The main engineering decisions were to preserve raw evidence down to the cell,
define the grain before loading facts, fail closed on data-quality problems and
separate PostgreSQL canonical truth from ClickHouse analytical serving. I also
made source releases content-addressed and added explicit rerun/backfill
behavior so the pipeline is reproducible rather than a one-off script.

## Honest scope statement

The project demonstrates production-like local engineering patterns. Cloud
deployment, a full quarantine workflow, streaming and distributed Spark
processing are planned extensions and should not be described as implemented
until their runtime evidence exists.
