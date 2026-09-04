# Task Board

## Done — Foundation

- [x] Confirm canonical workspace root
- [x] Confirm workspace was empty and not a Git repository
- [x] Initialize Git with `main` as default branch
- [x] Register public source pages and baseline release metadata
- [x] Inspect CGD/OCSC parser, cleaning, DQ, metadata and tests
- [x] Verify baseline workbook structure without printing cell data
- [x] Copy only the two public baseline Excel files
- [x] Create required repository structure
- [x] Create governance, architecture, model and interview documentation
- [x] Create safe placeholders and Git safety policy
- [x] Create bad-data fixture contract
- [x] Run bootstrap safety review
- [x] Validate metadata syntax, package smoke test, lint and Compose configuration
- [x] Do not push to remote

## P0 complete

- [x] Implement PostgreSQL DDL/migrations for `raw`, `staging`, `core`, `ops`
- [x] Add local database health/migration verification entry points
- [x] Adapt CGD parser into `src/thai_data_platform/transform/`
- [x] Adapt OCSC parser into `src/thai_data_platform/transform/`
- [x] Move shared cleaning and Thai date rules into the new namespace
- [x] Implement source metadata/SHA-256/run context
- [x] Implement local raw landing and transaction-safe PostgreSQL load
- [x] Implement DQ checks and fail-closed quality gate
- [x] Add idempotent source/core/ClickHouse publication guards
- [x] Implement core-to-ClickHouse serving publish
- [x] Add executable Airflow DAG with contract task IDs
- [x] Add four analytical SQL questions and smoke checks
- [x] Complete Docker/CI walkthrough and README runbook

## Final local verification

- [x] Start Docker Desktop and run PostgreSQL/ClickHouse integration path
- [x] Run Airflow init/scheduler/webserver and trigger the DAG
- [x] Capture final `pipeline_run`, DQ and serving row-count evidence
- [x] Verify all four analytical queries against ClickHouse
- [x] Verify same-source rerun is idempotent
- [x] Verify bad-data fixture exits non-zero and blocks publication

## Optional after P0 is green

- [ ] GCS adapter
- [ ] source discovery monitor
- [ ] richer operational metrics/alerts

## Explicitly deferred

- [ ] Kafka
- [ ] Spark
- [ ] Kubernetes
- [ ] Terraform
- [ ] frontend/dashboard
- [ ] ML/LLM features
