import os

import pytest

from thai_data_platform.pipeline import run_pipeline

pytestmark = pytest.mark.integration


def test_full_pipeline_is_repeatable_when_services_are_enabled():
    if os.getenv("RUN_FULL_INTEGRATION") != "1":
        pytest.skip("Set RUN_FULL_INTEGRATION=1 to run the full PostgreSQL/ClickHouse path")
    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    kwargs = {
        "ocsc_path": "datasets/ocsc/thai-gov-manpower-2567.4.xlsx",
        "cgd_path": "datasets/cgd/2026.07.03.xlsx",
        "postgres_url": postgres_url,
        "clickhouse_host": os.getenv("CLICKHOUSE_HOST", "localhost"),
        "clickhouse_port": int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
        "clickhouse_user": os.getenv("CLICKHOUSE_USER", "default"),
        "clickhouse_password": os.getenv("CLICKHOUSE_PASSWORD", ""),
    }

    first = run_pipeline(**kwargs)
    second = run_pipeline(**kwargs)

    assert first.status == "serving_published"
    assert second.status == "serving_published"
    assert second.serving_counts["skipped_existing_sources"] == 2
