"""ClickHouse analytical serving publisher."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import clickhouse_connect
import pandas as pd

from thai_data_platform.ingestion.metadata import SourceFileMetadata


def connect(
    *,
    host: str,
    port: int = 8123,
    username: str = "default",
    password: str = "",
    database: str = "analytics",
) -> Any:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database):
        raise ValueError(f"Unsafe ClickHouse database identifier: {database!r}")
    client = clickhouse_connect.get_client(
        host=host,
        port=port,
        username=username,
        password=password,
        database="__default__",
    )
    if database != "default":
        client.command(f"CREATE DATABASE IF NOT EXISTS {database}", use_database=False)
        client.database = database
    return client


def run_migrations(client: Any, migrations_dir: str | Path = "sql/clickhouse") -> int:
    migration_paths = sorted(Path(migrations_dir).glob("*.sql"))
    if not migration_paths:
        raise FileNotFoundError(f"No ClickHouse migrations found in {migrations_dir}")
    statement_count = 0
    for migration_path in migration_paths:
        for statement in _split_sql(migration_path.read_text(encoding="utf-8")):
            client.command(statement)
            statement_count += 1
    return statement_count


def publish_frames(
    client: Any,
    *,
    run_id: str,
    source_file_ids: dict[str, str],
    sources: list[SourceFileMetadata],
    cgd_frame: pd.DataFrame,
    ocsc_frame: pd.DataFrame,
) -> dict[str, int]:
    """Insert approved frames once per source hash into serving tables."""
    counts = {"budget_facts": 0, "workforce_facts": 0, "skipped_existing_sources": 0}
    cgd_source = _source_for_dataset(sources, "cgd_budget_execution")
    ocsc_source = _source_for_dataset(sources, "ocsc_government_manpower")

    if _source_already_published(client, "fact_budget_execution", cgd_source.sha256):
        counts["skipped_existing_sources"] += 1
    else:
        budget_rows = _budget_rows(cgd_frame, run_id, source_file_ids[cgd_source.sha256])
        if budget_rows:
            client.insert(
                "fact_budget_execution",
                budget_rows,
                column_names=_BUDGET_COLUMNS,
            )
            counts["budget_facts"] = len(budget_rows)

    if _source_already_published(client, "fact_workforce_metric", ocsc_source.sha256):
        counts["skipped_existing_sources"] += 1
    else:
        workforce_rows = _workforce_rows(
            ocsc_frame,
            run_id,
            source_file_ids[ocsc_source.sha256],
        )
        if workforce_rows:
            client.insert(
                "fact_workforce_metric",
                workforce_rows,
                column_names=_WORKFORCE_COLUMNS,
            )
            counts["workforce_facts"] = len(workforce_rows)
    return counts


def publish_public_indicators(
    client: Any,
    *,
    run_id: str,
    stage_result: Any,
    sources: list[Any],
    selected_records: dict[str, pd.DataFrame],
) -> dict[str, int]:
    """Publish the selected canonical public rows with release idempotency."""
    counts = {"public_indicators": 0, "skipped_existing_sources": 0}
    for source in sources:
        source_id = source.spec.source_id
        frame = selected_records.get(source_id, pd.DataFrame())
        if _public_source_already_published(client, source_id, source.content_sha256):
            counts["skipped_existing_sources"] += 1
            continue
        rows = _public_rows(
            frame,
            run_id=run_id,
            release_id=stage_result.release_ids[source_id],
            content_sha256=source.content_sha256,
        )
        if not rows:
            continue
        client.insert(
            "fact_public_indicator",
            rows,
            column_names=_PUBLIC_COLUMNS,
        )
        counts["public_indicators"] += len(rows)
    return counts


def run_smoke_queries(client: Any, query_dir: str | Path = "analytics/queries") -> dict[str, int]:
    results: dict[str, int] = {}
    for query_path in sorted(Path(query_dir).glob("*.sql")):
        if query_path.name.startswith("00_") or query_path.name.startswith("README"):
            continue
        statements = _split_sql(query_path.read_text(encoding="utf-8"))
        if len(statements) != 1:
            raise ValueError(f"Expected one analytical statement in {query_path}")
        # clickhouse-connect appends FORMAT Native; remove the file's trailing
        # semicolon so ClickHouse does not interpret it as multi-statement SQL.
        rows = client.query(statements[0]).result_rows
        results[query_path.stem] = len(rows)
    return results


def run_public_smoke_queries(
    client: Any,
    query_dir: str | Path = "analytics/queries/public",
) -> dict[str, int]:
    """Execute one read-only statement per public analytical contract."""
    results: dict[str, int] = {}
    for query_path in sorted(Path(query_dir).glob("*.sql")):
        if query_path.name.startswith("00_") or query_path.name.startswith("README"):
            continue
        statements = _split_sql(query_path.read_text(encoding="utf-8"))
        if len(statements) != 1:
            raise ValueError(f"Expected one analytical statement in {query_path}")
        results[query_path.stem] = len(client.query(statements[0]).result_rows)
    return results


_BUDGET_COLUMNS = [
    "run_id",
    "source_file_id",
    "source_file_hash",
    "sheet_index",
    "sheet_name",
    "row_number",
    "fiscal_year",
    "fiscal_year_be",
    "as_of_date",
    "report_type",
    "entity_type",
    "entity_name",
    "entity_code",
    "expense_category",
    "budget_after_transfer_million_baht",
    "allocated_million_baht",
    "po_reserved_debt_million_baht",
    "disbursement_million_baht",
    "disbursement_pct",
    "expenditure_million_baht",
    "expenditure_pct",
    "monthly_target_gap_pct",
    "remaining_million_baht",
    "remaining_pct",
    "published_at",
]
_WORKFORCE_COLUMNS = [
    "run_id",
    "source_file_id",
    "source_file_hash",
    "sheet_index",
    "sheet_name",
    "row_number",
    "fiscal_year",
    "fiscal_year_be",
    "entity_type",
    "ministry_name",
    "agency_name",
    "metric_name",
    "metric_group",
    "headcount",
    "percentage",
    "source_value",
    "source_unit",
    "published_at",
]
_PUBLIC_COLUMNS = [
    "run_id",
    "release_id",
    "source_id",
    "source_format",
    "source_role",
    "content_sha256",
    "record_key",
    "source_record_number",
    "period_start",
    "period_end",
    "period_grain",
    "calendar_year",
    "calendar_year_be",
    "fiscal_year",
    "fiscal_year_be",
    "entity_type",
    "entity_code",
    "entity_name",
    "geography_type",
    "geography_code",
    "geography_name",
    "category",
    "subcategory",
    "metric_name",
    "metric_unit",
    "value",
    "reference_metric",
    "reference_value",
    "source_url",
    "raw_payload",
    "published_at",
]


def _budget_rows(frame: pd.DataFrame, run_id: str, source_file_id: str) -> list[tuple[Any, ...]]:
    published_at = datetime.now(UTC)
    return [
        (
            run_id,
            source_file_id,
            row["source_file_hash"],
            int(row["sheet_index"]),
            row["sheet_name"],
            int(row["row_number"]),
            _value(row.get("fiscal_year")),
            _value(row.get("fiscal_year_be")),
            _date_value(row.get("as_of_date")),
            row["report_type"],
            row["entity_type"],
            row["entity_name"],
            _value(row.get("entity_code")),
            row["expense_category"],
            *[_value(row.get(column)) for column in _BUDGET_COLUMNS[14:24]],
            published_at,
        )
        for row in _records(frame)
    ]


def _workforce_rows(frame: pd.DataFrame, run_id: str, source_file_id: str) -> list[tuple[Any, ...]]:
    published_at = datetime.now(UTC)
    return [
        (
            run_id,
            source_file_id,
            row["source_file_hash"],
            int(row["sheet_index"]),
            row["sheet_name"],
            int(row["row_number"]),
            _value(row.get("fiscal_year")),
            _value(row.get("fiscal_year_be")),
            row["entity_type"],
            _value(row.get("ministry_name")),
            row["agency_name"],
            row["metric_name"],
            row["metric_group"],
            _value(row.get("headcount")),
            _value(row.get("percentage")),
            _value(row.get("source_value")),
            row["source_unit"],
            published_at,
        )
        for row in _records(frame)
    ]


def _source_already_published(client: Any, table_name: str, source_hash: str) -> bool:
    result = client.query(
        f"SELECT count() FROM {table_name} WHERE source_file_hash = {{source_hash:String}}",
        parameters={"source_hash": source_hash},
    )
    return bool(result.result_rows and result.result_rows[0][0])


def _public_source_already_published(client: Any, source_id: str, source_hash: str) -> bool:
    result = client.query(
        """
        SELECT count()
        FROM fact_public_indicator
        WHERE source_id = {source_id:String}
          AND content_sha256 = {source_hash:String}
        """,
        parameters={"source_id": source_id, "source_hash": source_hash},
    )
    return bool(result.result_rows and result.result_rows[0][0])


def _public_rows(
    frame: pd.DataFrame,
    *,
    run_id: str,
    release_id: str,
    content_sha256: str,
) -> list[tuple[Any, ...]]:
    published_at = datetime.now(UTC)
    rows: list[tuple[Any, ...]] = []
    for row in _records(frame):
        rows.append(
            (
                run_id,
                release_id,
                row["source_id"],
                row["source_format"],
                row["source_role"],
                content_sha256,
                row["record_key"],
                int(row["source_record_number"]),
                _date_value(row.get("period_start")),
                _date_value(row.get("period_end")),
                row["period_grain"],
                _value(row.get("calendar_year")),
                _value(row.get("calendar_year_be")),
                _value(row.get("fiscal_year")),
                _value(row.get("fiscal_year_be")),
                row["entity_type"],
                _value(row.get("entity_code")),
                row["entity_name"],
                row.get("geography_type") or "",
                _value(row.get("geography_code")),
                _value(row.get("geography_name")),
                row.get("category") or "",
                _value(row.get("subcategory")),
                row["metric_name"],
                row["metric_unit"],
                _value(row.get("value")),
                _value(row.get("reference_metric")),
                _value(row.get("reference_value")),
                row["source_url"],
                json.dumps(row.get("raw_payload") or {}, ensure_ascii=False, default=str),
                published_at,
            )
        )
    return rows


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return [
        {column: _value(value) for column, value in row.items()}
        for row in frame.to_dict("records")
    ]


def _value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item") and not isinstance(value, (str, bytes, Decimal)):
        return value.item()
    return value


def _date_value(value: Any) -> date | None:
    value = _value(value)
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _source_for_dataset(sources: list[SourceFileMetadata], dataset_name: str) -> SourceFileMetadata:
    matches = [source for source in sources if source.dataset_name == dataset_name]
    if len(matches) != 1:
        raise ValueError(f"Expected one source for {dataset_name}, found {len(matches)}")
    return matches[0]


def _split_sql(sql_text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    line_comment = False
    block_comment = False
    index = 0

    while index < len(sql_text):
        char = sql_text[index]
        next_char = sql_text[index + 1] if index + 1 < len(sql_text) else ""

        if line_comment:
            current.append(char)
            if char in "\r\n":
                line_comment = False
        elif block_comment:
            current.append(char)
            if char == "*" and next_char == "/":
                current.append(next_char)
                index += 1
                block_comment = False
        elif quote:
            current.append(char)
            if char == "\\" and next_char:
                current.append(next_char)
                index += 1
            elif char == quote:
                if next_char == quote:
                    current.append(next_char)
                    index += 1
                else:
                    quote = None
        elif char == "-" and next_char == "-":
            current.extend((char, next_char))
            index += 1
            line_comment = True
        elif char == "/" and next_char == "*":
            current.extend((char, next_char))
            index += 1
            block_comment = True
        elif char in {"'", '"', "`"}:
            current.append(char)
            quote = char
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        index += 1

    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements
