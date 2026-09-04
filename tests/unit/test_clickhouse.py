from decimal import Decimal
from types import SimpleNamespace

import pandas as pd

from thai_data_platform.warehouse.clickhouse import (
    _BUDGET_COLUMNS,
    _WORKFORCE_COLUMNS,
    _budget_rows,
    _split_sql,
    _workforce_rows,
    run_smoke_queries,
)


def test_clickhouse_serializers_match_declared_column_contract():
    budget = pd.DataFrame(
        [
            {
                "source_file_hash": "a" * 64,
                "sheet_index": 1,
                "sheet_name": "หน่วยงาน",
                "row_number": 6,
                "report_type": "disbursement",
                "entity_type": "agency",
                "entity_name": "กรมตัวอย่าง",
                "expense_category": "total",
                "allocated_million_baht": Decimal("10.25"),
            }
        ]
    )
    workforce = pd.DataFrame(
        [
            {
                "source_file_hash": "b" * 64,
                "sheet_index": 1,
                "sheet_name": "หน่วยงาน",
                "row_number": 6,
                "entity_type": "agency",
                "agency_name": "กรมตัวอย่าง",
                "metric_name": "civil_servant",
                "metric_group": "employment_type",
                "headcount": 25,
                "source_unit": "person",
            }
        ]
    )

    budget_rows = _budget_rows(budget, "run-1", "source-1")
    workforce_rows = _workforce_rows(workforce, "run-1", "source-2")

    assert len(budget_rows) == 1
    assert len(budget_rows[0]) == len(_BUDGET_COLUMNS)
    assert len(workforce_rows) == 1
    assert len(workforce_rows[0]) == len(_WORKFORCE_COLUMNS)


def test_clickhouse_migration_splitter_ignores_empty_statements():
    assert _split_sql("CREATE DATABASE analytics;\n\nCREATE TABLE t (id UInt8);\n") == [
        "CREATE DATABASE analytics",
        "CREATE TABLE t (id UInt8)",
    ]
    assert _split_sql("SELECT 'semi;colon'; SELECT 2;") == [
        "SELECT 'semi;colon'",
        "SELECT 2",
    ]


def test_clickhouse_smoke_queries_send_one_statement_without_trailing_semicolon():
    class FakeClient:
        def __init__(self):
            self.queries = []

        def query(self, statement):
            self.queries.append(statement)
            assert not statement.rstrip().endswith(";")
            return SimpleNamespace(result_rows=[(1,)])

    client = FakeClient()
    results = run_smoke_queries(client, "analytics/queries")

    assert len(results) == 4
    assert len(client.queries) == 4
