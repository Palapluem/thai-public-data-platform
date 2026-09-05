# Current State

**Last updated:** 2026-09-05

## Status summary

| Area | State | Evidence |
|---|---|---|
| Canonical root | complete | `D:\thai-public-data-platform` exists and is the active workspace |
| Git | complete | `main` tracks `origin/main`; baseline commit is pushed |
| Source registry | complete | public source pages, release metadata and SHA-256 hashes are recorded |
| Baseline datasets | complete | two public Excel files copied and SHA-256 recorded |
| Governance docs | complete | charter, plan, architecture, model, decisions and QA docs |
| Project structure | complete | required source, SQL, DAG, test, dataset and documentation paths created |
| Safety review | complete | no high-confidence secret pattern or sensitive-looking project path found |
| PostgreSQL implementation | complete | migrations, constraints, loader and run metadata are implemented |
| Airflow executable DAG | complete | `dags/thai_public_data_pipeline.py` wires the required task IDs |
| ClickHouse DDL/load | complete | serving DDL, idempotent publisher and four smoke queries are implemented |
| Parser/DQ validation | complete | baseline parse counts match manifest; 25 tests passed and Ruff passed |
| Runtime integration | verified | Docker Compose healthy; CLI and full 8-task Airflow DAG runs reached `serving_published` |
| P1 release operations | verified | schema contract, run types, health view and second-release/backfill integration pass |
| P2 multi-format ingestion | verified | CSV, nested JSON API, HTML validation and tabular JSON adapters normalize into canonical public indicators |
| P2 incremental operations | verified | content-addressed releases, period watermarks, correction/backfill selection and post-serving commit |
| P2 dashboard/story | verified | self-contained dashboard, four public SQL contracts and source-aware analytical narrative |

## What exists now

- Python ingestion, source-specific parsers, normalization and metadata under `src/thai_data_platform/`
- PostgreSQL migrations, loader, DQ persistence and fail-closed gate
- ClickHouse serving publisher, idempotency check and analytical smoke queries
- Executable Airflow DAG and package-aware Airflow image
- Local runtime in `Dockerfile`, `docker-compose.yml` and `.env.example`
- CI workflow for lint/test, contract validation and application image build
- Public source registry and baseline manifest under `config/`
- Versioned parser-output contract under `config/schema_contracts.json`
- Analyst metric contract under `analytics/metrics/`
- Bad-data fixture contract under `tests/fixtures/`
- Hands-on Docker verification steps under [`DOCKER_TEST_RUNBOOK.md`](DOCKER_TEST_RUNBOOK.md)
- Data model implemented with required keys, constraints, grains and transaction behavior
- Data provenance and reproducible baseline notes in [`PROVENANCE.md`](PROVENANCE.md)
- Multi-format public source registry and snapshots in `config/public_sources.yml` and `datasets/public/`
- Canonical public indicator model in `raw.public_record`, `staging.public_indicator` and `core.fact_public_indicator`
- Watermark state/events in `ops.public_source_watermark` and `ops.public_watermark_event`
- Self-contained dashboard builder under `src/thai_data_platform/public_sources/dashboard.py`
- AI-to-Data-Engineering learning, exercise, interview and new-project playbooks under `docs/`

## Deliberate boundaries

- generated database files, credentials or `.env`
- credentials or `.env` remain local; source code and documentation are safe to push
- Kafka, Spark, Kubernetes, Terraform, frontend and ML/LLM features remain planned extensions

## Next work

Next follow-up is a quarantine workflow, cross-store atomic serving publication,
GCS/PySpark scale experiments, alerting and cloud/IAM deployment evidence.
