# Integration Tests

Integration tests are opt-in because they need running local services. The
PostgreSQL schema test is available now and is skipped when `POSTGRES_URL` is
not set. The full CLI run is the end-to-end check for staging, DQ, core and
ClickHouse publication.

```powershell
$env:POSTGRES_URL = "postgresql://platform:<POSTGRES_PASSWORD>@localhost:5432/thai_data_platform"
python -m pytest tests/integration -m integration -q
```

For a complete run, follow the root README runbook and then run the same
source release twice. Compare `ops.pipeline_run`, raw/staging/core counts and
ClickHouse source-hash counts to verify idempotency.

The opt-in automated version is:

```powershell
$env:RUN_FULL_INTEGRATION = "1"
$env:CLICKHOUSE_HOST = "localhost"
python -m pytest tests/integration/test_full_pipeline.py -m integration -q
```
