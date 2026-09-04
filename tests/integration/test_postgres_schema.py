import os

import pytest

from thai_data_platform.warehouse import postgres

pytestmark = pytest.mark.integration


def test_postgres_migrations_create_platform_contract():
    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        pytest.skip("POSTGRES_URL is not configured")

    assert postgres.run_migrations(postgres_url) >= 6
    with postgres.connect(postgres_url) as connection:
        schemas = {
            row[0]
            for row in connection.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name IN ('raw', 'staging', 'core', 'ops')
                """
            ).fetchall()
        }
        tables = {
            (row[0], row[1])
            for row in connection.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema IN ('raw', 'staging', 'core', 'ops')
                """
            ).fetchall()
        }

    assert schemas == {"raw", "staging", "core", "ops"}
    assert {
        ("raw", "source_file"),
        ("raw", "workbook_sheet"),
        ("raw", "cell"),
        ("staging", "cgd_budget_execution"),
        ("staging", "ocsc_workforce"),
        ("core", "entity"),
        ("core", "fact_budget_execution"),
        ("core", "fact_workforce_metric"),
        ("ops", "pipeline_run"),
        ("ops", "dq_result"),
        ("ops", "source_release_observation"),
    }.issubset(tables)
