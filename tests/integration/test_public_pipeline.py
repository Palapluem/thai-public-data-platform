import os

import pytest

from thai_data_platform.public_sources.pipeline import run_public_pipeline

pytestmark = pytest.mark.integration


def test_public_pipeline_is_incremental_and_idempotent():
    if os.getenv("RUN_PUBLIC_INTEGRATION") != "1":
        pytest.skip("Set RUN_PUBLIC_INTEGRATION=1 to run the public multi-format path")
    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        pytest.skip("POSTGRES_URL is not configured")
    common = {
        "postgres_url": postgres_url,
        "clickhouse_host": os.getenv("CLICKHOUSE_HOST", "localhost"),
        "clickhouse_port": int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
        "clickhouse_user": os.getenv("CLICKHOUSE_USER", "default"),
        "clickhouse_password": os.getenv("CLICKHOUSE_PASSWORD", ""),
        "run_type": "scheduled",
    }

    first = run_public_pipeline(**common)
    second = run_public_pipeline(**common)

    assert first.status == "serving_published"
    assert second.status == "serving_published"
    assert second.watermark_status == {
        "mof_budget_summary_csv_2568": "unchanged",
        "mof_budget_monthly_json_api_2026": "unchanged",
        "mof_budget_summary_html_2026": "unchanged",
        "nso_labour_region_sex_json_2569": "unchanged",
    }
    assert second.stage_counts["selected_public_indicators"] == 0
    assert second.serving_counts["skipped_existing_sources"] == 4
    assert second.smoke_counts["001_monthly_expenditure_trend"] == 22
