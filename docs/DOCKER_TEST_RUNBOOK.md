# Docker Test Runbook

This runbook is the hands-on verification path for the local data platform.
It is designed to show what each service does while giving a repeatable way to
test the data end to end.

## 1. Understand the service roles

| Service | Role | What to observe |
|---|---|---|
| `postgres` | canonical relational store | raw cells, staging rows, core facts and `ops` run/DQ evidence |
| `clickhouse` | analytical serving store | read-optimized facts and four SQL smoke queries |
| `airflow-init` | one-time metadata setup | database migration and local admin creation |
| `airflow-scheduler` | workflow executor | task dependencies, retries and task states |
| `airflow-webserver` | workflow UI | DAG graph, logs and run history |

The important dependency is:

```text
Excel → raw → staging → data-quality gate → core → ClickHouse → analytics
```

Airflow coordinates this path; it does not contain the parser or analytical
business rules.

## 2. Start and inspect the stack

Create `.env` once from [`.env.example`](../.env.example). Keep the real local
values untracked. If another PostgreSQL is already using port `5432`, choose a
different host port such as `55432` in `.env`; the container still listens on
`5432` internally.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build
docker compose ps
```

Expected state:

- PostgreSQL: `healthy`
- ClickHouse: `healthy`
- Airflow scheduler and webserver: `Up`
- Airflow UI: `http://127.0.0.1:8080`

For a quick HTTP check:

```powershell
(Invoke-WebRequest http://127.0.0.1:8080/health).StatusCode
```

Expected result: `200`.

## 3. Run the deterministic CLI path

Set these values in the same PowerShell session. Replace placeholders with the
matching local values from `.env`.

```powershell
$env:POSTGRES_URL = "postgresql://platform:<POSTGRES_PASSWORD>@127.0.0.1:<POSTGRES_PORT>/thai_data_platform"
$env:CLICKHOUSE_PASSWORD = "<CLICKHOUSE_PASSWORD>"
```

Run the full path:

```powershell
python -m thai_data_platform run `
  --ocsc datasets/ocsc/thai-gov-manpower-2567.4.xlsx `
  --cgd datasets/cgd/2026.07.03.xlsx `
  --postgres-url $env:POSTGRES_URL `
  --clickhouse-host 127.0.0.1 `
  --clickhouse-port 8123 `
  --clickhouse-password $env:CLICKHOUSE_PASSWORD
```

Expected result shape:

```text
status: serving_published
cgd_rows: 2937
ocsc_rows: 5784
dq_failed_checks: 0
```

The exact `run_id` changes on every attempt. A successful repeated run should
report zero new core facts and skip the two already-published source releases.

## 4. Inspect PostgreSQL evidence

The SQL below runs inside the Compose network, so it does not depend on the
host port chosen for PostgreSQL.

```powershell
docker compose exec -T postgres psql -U platform -d thai_data_platform -P pager=off -c `
  "SELECT run_id,status,raw_cell_count,cgd_row_count,ocsc_row_count,dq_failed_check_count,core_published_at IS NOT NULL AS core_done,serving_published_at IS NOT NULL AS serving_done FROM ops.pipeline_run ORDER BY started_at DESC LIMIT 5;"
```

Expected latest successful row:

```text
status                | serving_published
raw_cell_count        | 125890
cgd_row_count         | 2937
ocsc_row_count        | 5784
dq_failed_check_count | 0
core_done             | t
serving_done          | t
```

Check the relational layers:

```powershell
docker compose exec -T postgres psql -U platform -d thai_data_platform -P pager=off -c `
  "SELECT 'staging.cgd_budget_execution' AS table_name,count(*) AS rows FROM staging.cgd_budget_execution UNION ALL SELECT 'staging.ocsc_workforce',count(*) FROM staging.ocsc_workforce UNION ALL SELECT 'core.entity',count(*) FROM core.entity UNION ALL SELECT 'core.fact_budget_execution',count(*) FROM core.fact_budget_execution UNION ALL SELECT 'core.fact_workforce_metric',count(*) FROM core.fact_workforce_metric;"
```

Expected counts are `2937`, `5784`, `829`, `2937` and `5784` respectively.

## 5. Run the Airflow DAG

The DAG is intentionally manual for the deterministic local demo. Unpause it
once, then trigger a run:

```powershell
docker compose exec -T airflow-scheduler airflow dags unpause thai_public_data_platform
docker compose exec -T airflow-scheduler airflow dags trigger thai_public_data_platform --run-id manual_local_test
```

Open `http://127.0.0.1:8080`, sign in with the local credentials in `.env`,
and open DAG `thai_public_data_platform`.

The eight tasks should complete in this order:

```text
prepare_run
  ├─ ingest_cgd ─┐
  └─ ingest_ocsc ┘
        ↓
validate_staging → publish_core → quality_gate
        → publish_clickhouse → analytics_smoke
```

Inspect task states directly when learning or debugging:

```powershell
docker compose exec -T postgres psql -U platform -d thai_data_platform -P pager=off -c `
  "SELECT task_id,state,try_number,start_date,end_date,duration FROM task_instance WHERE dag_id='thai_public_data_platform' ORDER BY start_date DESC NULLS LAST,task_id;"
```

## 6. Execute and interpret the analytical checks

The four SQL files under [`analytics/queries`](../analytics/queries) are both
analyst-facing examples and post-publish smoke checks:

1. largest budget allocations
2. below-median disbursement
3. workforce distribution
4. budget-to-workforce ratio

Each query declares its grain and filters source semantics before aggregating.
The fourth query exposes `budget_basis`; for the baseline agency rows it uses
`budget_after_transfer` because `allocated` is not populated at that grain.
This is an explicit source-semantic fallback, not an imputation. It also keeps
the two reporting periods visible in the result.

## 7. Prove the negative path

The fixture intentionally contains invalid data. It must fail with exit code
`1`; that is a pass condition for the fail-closed contract.

```powershell
python -m thai_data_platform quality-fixture
```

Expected output shape:

```text
{"passed": false, "blocking_issue_count": 6}
```

This fixture is isolated and does not alter the running database. In a real
run, a blocking quality result leaves raw/staging/ops evidence for diagnosis
but prevents core and ClickHouse publication.

## 8. Prove idempotency

Run the CLI path twice with the same two files. The second run should keep the
same counts and report:

```text
core_counts: entities=0, budget_facts=0, workforce_facts=0
serving_counts: skipped_existing_sources=2
```

The reason is source-release identity (SHA-256 plus dataset metadata) and
unique natural grain, rather than a fragile filename-only check.

## 9. Useful diagnostics and safe stop

```powershell
docker compose logs --tail 100 airflow-scheduler
docker compose logs --tail 100 airflow-webserver
docker compose logs --tail 100 postgres
docker compose logs --tail 100 clickhouse
```

To stop containers while preserving the database volumes:

```powershell
docker compose stop
```

Use `docker compose down` only when removing the containers/network is desired.
Do not add `-v` unless you intentionally want to delete the local database
volumes and start the demo from an empty state.
