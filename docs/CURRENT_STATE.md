# Current State

**Last updated:** 2026-09-04

## Status summary

| Area | State | Evidence |
|---|---|---|
| Canonical root | complete | `D:\thai-public-data-platform` exists and is the active workspace |
| Git | complete | initialized with default branch `main`; nothing pushed |
| Source registry | complete | public source pages, release metadata and SHA-256 hashes are recorded |
| Baseline datasets | complete | two public Excel files copied and SHA-256 recorded |
| Governance docs | complete | charter, plan, architecture, model, decisions and QA docs |
| Project structure | complete | required source, SQL, DAG, test, dataset and documentation paths created |
| Safety review | complete | no high-confidence secret pattern or sensitive-looking project path found |
| PostgreSQL implementation | complete | migrations, constraints, loader and run metadata are implemented |
| Airflow executable DAG | complete | `dags/thai_public_data_pipeline.py` wires the required task IDs |
| ClickHouse DDL/load | complete | serving DDL, idempotent publisher and four smoke queries are implemented |
| Parser/DQ validation | complete | baseline parse counts match manifest; 18 tests passed, 2 skipped, and Ruff passed |
| Runtime integration | verified | Docker Compose healthy; CLI and full 8-task Airflow DAG runs reached `serving_published` |

## What exists now

- Python ingestion, source-specific parsers, normalization and metadata under `src/thai_data_platform/`
- PostgreSQL migrations, loader, DQ persistence and fail-closed gate
- ClickHouse serving publisher, idempotency check and analytical smoke queries
- Executable Airflow DAG and package-aware Airflow image
- Local runtime in `Dockerfile`, `docker-compose.yml` and `.env.example`
- CI workflow for lint/test only
- Public source registry and baseline manifest under `config/`
- Bad-data fixture contract under `tests/fixtures/`
- Hands-on Docker verification steps under [`DOCKER_TEST_RUNBOOK.md`](DOCKER_TEST_RUNBOOK.md)
- Data model implemented with required keys, constraints, grains and transaction behavior
- Data provenance and reproducible baseline notes in [`PROVENANCE.md`](PROVENANCE.md)

## Deliberate boundaries

- generated database files, credentials or `.env`
- remote pushes; the repository remains local until explicitly requested
- Kafka, Spark, Kubernetes, Terraform, frontend, ML and LLM features in P0

## Next work

Optional follow-up is GCS raw landing, source-release discovery and richer
operational monitoring now that the Docker integration run is green.
