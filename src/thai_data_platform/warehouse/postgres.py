"""PostgreSQL migrations, staging, core publication and run metadata."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg

from thai_data_platform.ingestion.metadata import SourceFileMetadata
from thai_data_platform.public_sources.models import ParsedPublicSource
from thai_data_platform.public_sources.watermark import WatermarkDecision, decide_watermark
from thai_data_platform.quality.gate import QualityGateError
from thai_data_platform.transform.cgd import CgdExtract
from thai_data_platform.transform.ocsc import OcscExtract

VALID_RUN_TYPES = frozenset({"manual", "scheduled", "backfill", "replay"})


@dataclass(frozen=True)
class StageResult:
    source_file_ids: dict[str, str]
    workbook_sheet_ids: dict[tuple[str, int], int]
    raw_cell_count: int
    cgd_row_count: int
    ocsc_row_count: int


@dataclass(frozen=True)
class PublicStageResult:
    release_ids: dict[str, str]
    new_releases: dict[str, bool]
    record_counts: dict[str, int]
    selected_record_counts: dict[str, int]
    previous_watermarks: dict[str, date | None]
    watermark_candidates: dict[str, date | None]
    decisions: dict[str, WatermarkDecision]

    @property
    def selected_row_count(self) -> int:
        return sum(self.selected_record_counts.values())


def connect(postgres_url: str) -> psycopg.Connection:
    """Open a non-autocommit connection; callers own transaction boundaries."""
    # A bounded timeout prevents a bad host/port resolution from hanging a
    # pipeline worker indefinitely, especially on Windows localhost/IPv6.
    return psycopg.connect(postgres_url, connect_timeout=10)


def run_migrations(postgres_url: str, migrations_dir: str | Path = "sql/postgres") -> int:
    """Apply ordered SQL files in one transaction and return migration count."""
    migration_paths = sorted(Path(migrations_dir).glob("*.sql"))
    if not migration_paths:
        raise FileNotFoundError(f"No PostgreSQL migrations found in {migrations_dir}")
    with connect(postgres_url) as connection:
        for migration_path in migration_paths:
            connection.execute(migration_path.read_text(encoding="utf-8"))
        connection.commit()
    return len(migration_paths)


def prepare_run(
    postgres_url: str,
    run_id: str,
    source_hashes: Iterable[str],
    *,
    pipeline_name: str = "thai_public_data_platform",
    run_type: str = "manual",
) -> None:
    _validate_run_type(run_type)
    with connect(postgres_url) as connection:
        connection.execute(
            """
            INSERT INTO ops.pipeline_run (
                run_id, pipeline_name, run_type, status, started_at, source_hashes
            )
            VALUES (%s, %s, %s, 'prepared', %s, %s::jsonb)
            """,
            (
                run_id,
                pipeline_name,
                run_type,
                _utc_now(),
                json.dumps(sorted(set(source_hashes))),
            ),
        )
        connection.commit()


def stage_extracts(
    postgres_url: str,
    run_id: str,
    sources: list[SourceFileMetadata],
    cgd_extract: CgdExtract,
    ocsc_extract: OcscExtract,
) -> StageResult:
    """Persist raw evidence and source-aligned staging rows atomically."""
    source_file_ids: dict[str, str] = {}
    workbook_sheet_ids: dict[tuple[str, int], int] = {}

    with connect(postgres_url) as connection:
        for source in sources:
            source_file_ids[source.sha256] = _upsert_source_file(connection, source)

        for source, sheets in [
            (sources_for_dataset(sources, "cgd_budget_execution"), cgd_extract.workbook_sheets),
            (
                sources_for_dataset(sources, "ocsc_government_manpower"),
                ocsc_extract.workbook_sheets,
            ),
        ]:
            source_file_id = source_file_ids[source.sha256]
            for row in _dataframe_records(sheets):
                sheet_index = int(row["sheet_index"])
                workbook_sheet_ids[(source.sha256, sheet_index)] = _upsert_workbook_sheet(
                    connection,
                    source_file_id,
                    row,
                )

        raw_frames = [cgd_extract.raw_cells, ocsc_extract.raw_cells]
        raw_cell_count = sum(len(frame) for frame in raw_frames)
        for frame in raw_frames:
            _insert_raw_cells(connection, frame, source_file_ids, workbook_sheet_ids)

        cgd_row_count = _insert_cgd_staging(
            connection,
            run_id,
            cgd_extract.budget_execution,
            source_file_ids,
            workbook_sheet_ids,
        )
        ocsc_frame = pd.concat(
            [ocsc_extract.workforce_agency, ocsc_extract.workforce_profile],
            ignore_index=True,
        )
        ocsc_row_count = _insert_ocsc_staging(
            connection,
            run_id,
            ocsc_frame,
            source_file_ids,
            workbook_sheet_ids,
        )
        connection.execute(
            """
            UPDATE ops.pipeline_run
            SET status = 'staged',
                raw_cell_count = %s,
                cgd_row_count = %s,
                ocsc_row_count = %s
            WHERE run_id = %s
            """,
            (raw_cell_count, cgd_row_count, ocsc_row_count, run_id),
        )
        connection.commit()

    return StageResult(
        source_file_ids=source_file_ids,
        workbook_sheet_ids=workbook_sheet_ids,
        raw_cell_count=raw_cell_count,
        cgd_row_count=cgd_row_count,
        ocsc_row_count=ocsc_row_count,
    )


def public_watermarks(postgres_url: str, source_ids: Iterable[str]) -> dict[str, date | None]:
    """Read the last committed watermark for each public source."""
    ids = list(source_ids)
    if not ids:
        return {}
    with connect(postgres_url) as connection:
        rows = connection.execute(
            """
            SELECT source_id, watermark_value
            FROM ops.public_source_watermark
            WHERE source_id = ANY(%s)
            """,
            (ids,),
        ).fetchall()
    values = {str(source_id): watermark for source_id, watermark in rows}
    return {source_id: values.get(source_id) for source_id in ids}


def public_release_exists(
    postgres_url: str,
    sources: Iterable[ParsedPublicSource],
) -> dict[str, bool]:
    """Return whether the exact content hash has already been registered."""
    source_list = list(sources)
    if not source_list:
        return {}
    pairs = [(source.spec.source_id, source.content_sha256) for source in source_list]
    with connect(postgres_url) as connection:
        existing = connection.execute(
            """
            SELECT source_id, content_sha256
            FROM raw.public_source_release
            WHERE (source_id, content_sha256) IN (
                SELECT * FROM UNNEST(%s::TEXT[], %s::CHAR(64)[])
            )
            """,
            ([pair[0] for pair in pairs], [pair[1] for pair in pairs]),
        ).fetchall()
    existing_pairs = {(str(source_id), str(content_hash)) for source_id, content_hash in existing}
    return {
        source.spec.source_id: (source.spec.source_id, source.content_sha256) in existing_pairs
        for source in source_list
    }


def public_release_committed(
    postgres_url: str,
    sources: Iterable[ParsedPublicSource],
) -> dict[str, bool]:
    """Return whether the release reached the post-serving watermark commit."""
    source_list = list(sources)
    if not source_list:
        return {}
    pairs = [(source.spec.source_id, source.content_sha256) for source in source_list]
    with connect(postgres_url) as connection:
        rows = connection.execute(
            """
            SELECT
                release.source_id,
                release.content_sha256,
                EXISTS (
                    SELECT 1
                    FROM ops.public_watermark_event AS event
                    WHERE event.release_id = release.release_id
                      AND event.status <> 'failed'
                ) AS committed
            FROM raw.public_source_release AS release
            WHERE (release.source_id, release.content_sha256) IN (
                SELECT * FROM UNNEST(%s::TEXT[], %s::CHAR(64)[])
            )
            """,
            ([pair[0] for pair in pairs], [pair[1] for pair in pairs]),
        ).fetchall()
    return {
        source.spec.source_id: any(
            str(source_id) == source.spec.source_id
            and str(content_hash) == source.content_sha256
            and bool(committed)
            for source_id, content_hash, committed in rows
        )
        for source in source_list
    }


def stage_public_sources(
    postgres_url: str,
    run_id: str,
    sources: list[ParsedPublicSource],
    selected_records: dict[str, pd.DataFrame],
    *,
    run_type: str = "scheduled",
) -> PublicStageResult:
    """Persist public raw evidence and selected canonical rows atomically.

    Raw records always preserve the complete downloaded release. Staging only
    receives the watermark-selected slice, which makes the incremental choice
    visible and keeps a later correction/backfill auditable.
    """
    source_ids = [source.spec.source_id for source in sources]
    previous = public_watermarks(postgres_url, source_ids)
    release_ids: dict[str, str] = {}
    new_releases: dict[str, bool] = {}
    record_counts = {source.spec.source_id: len(source.records) for source in sources}
    selected_counts = {
        source.spec.source_id: len(selected_records.get(source.spec.source_id, pd.DataFrame()))
        for source in sources
    }
    candidates = {source.spec.source_id: source.watermark for source in sources}
    decisions: dict[str, WatermarkDecision] = {}

    with connect(postgres_url) as connection:
        for source in sources:
            source_id = source.spec.source_id
            release_id, is_new, is_committed = _upsert_public_release(connection, run_id, source)
            release_ids[source_id] = release_id
            needs_processing = is_new or not is_committed
            new_releases[source_id] = needs_processing
            # If serving publication succeeded but the worker died before the
            # watermark commit, an existing release with no prior watermark
            # must be safely repairable on the next run.
            needs_initial_commit = (
                previous.get(source_id) is None and candidates[source_id] is not None
            )
            decisions[source_id] = decide_watermark(
                previous.get(source_id),
                candidates[source_id],
                is_new_release=needs_processing or needs_initial_commit,
            )
            _insert_public_raw_records(connection, release_id, source.records)
            _insert_public_staging_records(
                connection,
                run_id,
                release_id,
                source,
                selected_records.get(source_id, pd.DataFrame()),
            )
        connection.execute(
            """
            UPDATE ops.pipeline_run
            SET status = 'staged', public_row_count = %s
            WHERE run_id = %s
            """,
            (sum(selected_counts.values()), run_id),
        )
        connection.commit()

    return PublicStageResult(
        release_ids=release_ids,
        new_releases=new_releases,
        record_counts=record_counts,
        selected_record_counts=selected_counts,
        previous_watermarks=previous,
        watermark_candidates=candidates,
        decisions=decisions,
    )


def publish_public_core(
    postgres_url: str,
    run_id: str,
) -> dict[str, int]:
    """Move the validated public staging slice into the relational core."""
    with connect(postgres_url) as connection:
        inserted = connection.execute(
            """
            INSERT INTO core.fact_public_indicator (
                run_id, release_id, source_id, content_sha256, source_format, source_role,
                record_key, source_record_number, period_start, period_end, period_grain,
                calendar_year, calendar_year_be, fiscal_year, fiscal_year_be, entity_type,
                entity_code, entity_name, geography_type, geography_code, geography_name,
                category, subcategory, metric_name, metric_unit, value, reference_metric,
                reference_value, source_url, raw_payload
            )
            SELECT
                run_id, release_id, source_id, content_sha256, source_format, source_role,
                record_key, source_record_number, period_start, period_end, period_grain,
                calendar_year, calendar_year_be, fiscal_year, fiscal_year_be, entity_type,
                entity_code, entity_name, geography_type, geography_code, geography_name,
                category, subcategory, metric_name, metric_unit, value, reference_metric,
                reference_value, source_url, raw_payload
            FROM staging.public_indicator
            WHERE run_id = %s
            ON CONFLICT DO NOTHING
            RETURNING core_public_id
            """,
            (run_id,),
        ).fetchall()
        connection.execute(
            """
            UPDATE ops.pipeline_run
            SET status = 'core_published',
                public_row_count = (
                    SELECT COUNT(*) FROM staging.public_indicator WHERE run_id = %s
                ),
                core_published_at = now()
            WHERE run_id = %s
            """,
            (run_id, run_id),
        )
        connection.commit()
    return {"public_indicators": len(inserted)}


def mark_public_watermarks(
    postgres_url: str,
    run_id: str,
    stage_result: PublicStageResult,
) -> int:
    """Commit watermark state only after ClickHouse publication succeeds."""
    advanced_count = 0
    with connect(postgres_url) as connection:
        for source_id, decision in stage_result.decisions.items():
            release_id = stage_result.release_ids[source_id]
            selected_count = stage_result.selected_record_counts[source_id]
            connection.execute(
                """
                INSERT INTO ops.public_watermark_event (
                    run_id, source_id, release_id, previous_watermark,
                    selected_watermark, selected_record_count, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    source_id,
                    release_id,
                    decision.previous,
                    decision.selected,
                    selected_count,
                    decision.status,
                ),
            )
            if not decision.is_new_release:
                continue
            if decision.status == "advanced":
                advanced_count += 1
            connection.execute(
                """
                INSERT INTO ops.public_source_watermark (
                    source_id, watermark_field, watermark_value,
                    last_release_id, last_run_id, updated_at
                )
                VALUES (%s, 'period_end', %s, %s, %s, now())
                ON CONFLICT (source_id) DO UPDATE SET
                    watermark_value = EXCLUDED.watermark_value,
                    last_release_id = EXCLUDED.last_release_id,
                    last_run_id = EXCLUDED.last_run_id,
                    updated_at = now()
                """,
                (source_id, decision.selected, release_id, run_id),
            )
        connection.execute(
            """
            UPDATE ops.pipeline_run
            SET watermark_advanced_count = %s
            WHERE run_id = %s
            """,
            (advanced_count, run_id),
        )
        connection.commit()
    return advanced_count


def record_quality_results(
    postgres_url: str,
    run_id: str,
    issues: pd.DataFrame,
    *,
    passed: bool,
) -> None:
    with connect(postgres_url) as connection:
        for row in _dataframe_records(issues):
            sample = _json_sample(row.get("sample"))
            connection.execute(
                """
                INSERT INTO ops.dq_result (
                    run_id, check_name, severity, dataset_name, table_name,
                    issue_count, sample, blocking, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (run_id, check_name, dataset_name, table_name)
                DO UPDATE SET
                    issue_count = EXCLUDED.issue_count,
                    sample = EXCLUDED.sample,
                    blocking = EXCLUDED.blocking,
                    status = EXCLUDED.status,
                    checked_at = now()
                """,
                (
                    run_id,
                    row["check_name"],
                    row["severity"],
                    row["dataset_name"],
                    row["table_name"],
                    int(row["issue_count"]),
                    json.dumps(sample, ensure_ascii=False, default=str),
                    bool(row.get("blocking", row["severity"] == "error")),
                    row["status"],
                ),
            )
        failed_count = int(
            issues.loc[issues["status"].eq("failed"), "check_name"].nunique()
            if not issues.empty and "status" in issues.columns
            else 0
        )
        connection.execute(
            """
            UPDATE ops.pipeline_run
            SET status = %s,
                dq_failed_check_count = %s,
                ended_at = CASE WHEN %s THEN now() ELSE ended_at END
            WHERE run_id = %s
            """,
            ("validated" if passed else "quality_failed", failed_count, not passed, run_id),
        )
        connection.commit()


def assert_persisted_quality_gate(postgres_url: str, run_id: str) -> None:
    """Fail closed when persisted DQ evidence is absent, failed or stale."""
    with connect(postgres_url) as connection:
        row = connection.execute(
            """
            SELECT
                pr.status,
                COUNT(dq.dq_result_id) AS result_count,
                COUNT(*) FILTER (
                    WHERE dq.status = 'failed' AND dq.blocking
                ) AS blocking_failure_count
            FROM ops.pipeline_run AS pr
            LEFT JOIN ops.dq_result AS dq ON dq.run_id = pr.run_id
            WHERE pr.run_id = %s
            GROUP BY pr.status
            """,
            (run_id,),
        ).fetchone()
    if not row:
        raise QualityGateError(f"Quality gate has no pipeline run evidence for {run_id}")
    status, result_count, blocking_failure_count = row
    if isinstance(status, bytes):
        status = status.decode("utf-8")
    if status != "core_published":
        raise QualityGateError(
            f"Quality gate expected core_published status, found {status!r} for {run_id}"
        )
    if int(result_count) == 0:
        raise QualityGateError(f"Quality gate has no DQ results for {run_id}")
    if int(blocking_failure_count) > 0:
        raise QualityGateError(
            f"Quality gate found {int(blocking_failure_count)} blocking failures for {run_id}"
        )


def previous_successful_row_counts(postgres_url: str) -> dict[str, int]:
    """Read the latest successful row counts for volume-collapse checks."""
    with connect(postgres_url) as connection:
        row = connection.execute(
            """
            SELECT cgd_row_count, ocsc_row_count
            FROM ops.pipeline_run
            WHERE status IN ('core_published', 'serving_published')
            ORDER BY started_at DESC
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return {}
    cgd_count, ocsc_count = (int(value) for value in row)
    return {
        dataset_name: count
        for dataset_name, count in {
            "cgd_budget_execution": cgd_count,
            "ocsc_government_manpower": ocsc_count,
        }.items()
        if count > 0
    }


def publish_core(
    postgres_url: str,
    run_id: str,
    sources: list[SourceFileMetadata],
    cgd_frame: pd.DataFrame,
    ocsc_frame: pd.DataFrame,
    stage_result: StageResult,
) -> dict[str, int]:
    """Publish approved staging rows into core in one transaction."""
    source_file_ids = stage_result.source_file_ids
    workbook_sheet_ids = stage_result.workbook_sheet_ids
    counts = {"entities": 0, "budget_facts": 0, "workforce_facts": 0}

    with connect(postgres_url) as connection:
        entity_ids: dict[tuple[str, str, str], str] = {}
        for source, frame, name_col, type_col, code_col, ministry_col in [
            (
                sources_for_dataset(sources, "cgd_budget_execution"),
                cgd_frame,
                "entity_name",
                "entity_type",
                "entity_code",
                None,
            ),
            (
                sources_for_dataset(sources, "ocsc_government_manpower"),
                ocsc_frame,
                "agency_name",
                "entity_type",
                None,
                "ministry_name",
            ),
        ]:
            for row in _dataframe_records(frame):
                entity_name = str(row[name_col])
                entity_type = str(row[type_col])
                key = (source.dataset_name, entity_name, entity_type)
                if key in entity_ids:
                    continue
                entity_id, created = _upsert_entity(
                    connection,
                    dataset_name=source.dataset_name,
                    entity_name=entity_name,
                    entity_type=entity_type,
                    entity_code=row.get(code_col) if code_col else None,
                    ministry_name=row.get(ministry_col) if ministry_col else None,
                )
                entity_ids[key] = entity_id
                if created:
                    counts["entities"] += 1

        for row in _dataframe_records(cgd_frame):
            source = sources_for_dataset(sources, "cgd_budget_execution")
            entity_id = entity_ids[
                (source.dataset_name, str(row["entity_name"]), str(row["entity_type"]))
            ]
            inserted = connection.execute(
                """
                INSERT INTO core.fact_budget_execution (
                    run_id, source_file_id, workbook_sheet_id, entity_id,
                    dataset_name, sheet_index, sheet_name, row_number,
                    fiscal_year, fiscal_year_be, as_of_date, report_type,
                    entity_type, entity_name, entity_code, expense_category,
                    budget_after_transfer_million_baht, allocated_million_baht,
                    po_reserved_debt_million_baht, disbursement_million_baht,
                    disbursement_pct, expenditure_million_baht, expenditure_pct,
                    monthly_target_gap_pct, remaining_million_baht, remaining_pct
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT DO NOTHING
                RETURNING core_budget_id
                """,
                _cgd_core_values(row, run_id, source_file_ids, workbook_sheet_ids, entity_id),
            ).fetchone()
            if inserted:
                counts["budget_facts"] += 1

        for row in _dataframe_records(ocsc_frame):
            source = sources_for_dataset(sources, "ocsc_government_manpower")
            entity_id = entity_ids[
                (source.dataset_name, str(row["agency_name"]), str(row["entity_type"]))
            ]
            inserted = connection.execute(
                """
                INSERT INTO core.fact_workforce_metric (
                    run_id, source_file_id, workbook_sheet_id, entity_id,
                    dataset_name, sheet_index, sheet_name, row_number,
                    fiscal_year, fiscal_year_be, entity_type, ministry_name,
                    agency_name, metric_name, metric_group, headcount,
                    percentage, source_value, source_unit
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING core_workforce_id
                """,
                _ocsc_core_values(row, run_id, source_file_ids, workbook_sheet_ids, entity_id),
            ).fetchone()
            if inserted:
                counts["workforce_facts"] += 1

        connection.execute(
            """
            UPDATE ops.pipeline_run
            SET status = 'core_published', core_published_at = now()
            WHERE run_id = %s
            """,
            (run_id,),
        )
        connection.commit()
    return counts


def mark_serving_published(postgres_url: str, run_id: str) -> None:
    with connect(postgres_url) as connection:
        connection.execute(
            """
            UPDATE ops.pipeline_run
            SET status = 'serving_published', serving_published_at = now(), ended_at = now()
            WHERE run_id = %s
            """,
            (run_id,),
        )
        connection.commit()


def mark_run_failed(postgres_url: str, run_id: str, message: str) -> None:
    with connect(postgres_url) as connection:
        connection.execute(
            """
            UPDATE ops.pipeline_run
            SET status = 'failed', error_message = %s, ended_at = now()
            WHERE run_id = %s
            """,
            (message[:4000], run_id),
        )
        connection.commit()


def healthcheck(postgres_url: str) -> bool:
    with connect(postgres_url) as connection:
        connection.execute("SELECT 1").fetchone()
    return True


def sources_for_dataset(sources: list[SourceFileMetadata], dataset_name: str) -> SourceFileMetadata:
    matches = [source for source in sources if source.dataset_name == dataset_name]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one source for {dataset_name}, found {len(matches)}")
    return matches[0]


def _validate_run_type(run_type: str) -> None:
    if run_type not in VALID_RUN_TYPES:
        allowed = ", ".join(sorted(VALID_RUN_TYPES))
        raise ValueError(f"Unsupported run_type {run_type!r}; expected one of: {allowed}")


def _upsert_source_file(connection: psycopg.Connection, source: SourceFileMetadata) -> str:
    row = connection.execute(
        """
        INSERT INTO raw.source_file (
            dataset_name, source_name, filename, source_path, sha256,
            source_page_url, file_url, fiscal_year, fiscal_year_be, as_of_date,
            file_size_bytes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sha256) DO NOTHING
        RETURNING source_file_id
        """,
        (
            source.dataset_name,
            source.source_name,
            source.filename,
            str(source.path),
            source.sha256,
            source.source_page_url,
            source.file_url,
            source.fiscal_year,
            source.fiscal_year_be,
            source.as_of_date,
            source.file_size_bytes,
        ),
    ).fetchone()
    if row:
        return str(row[0])
    return str(
        connection.execute(
            "SELECT source_file_id FROM raw.source_file WHERE sha256 = %s",
            (source.sha256,),
        ).fetchone()[0]
    )


def _upsert_workbook_sheet(
    connection: psycopg.Connection,
    source_file_id: str,
    row: dict[str, Any],
) -> int:
    values = (
        source_file_id,
        int(row["sheet_index"]),
        str(row["sheet_name"]),
        int(row.get("max_row") or 0),
        int(row.get("max_column") or 0),
        int(row.get("non_empty_cells") or 0),
        int(row.get("merged_cell_count") or 0),
        int(row.get("formula_cell_count") or 0),
        int(row.get("blank_row_count") or 0),
        int(row.get("blank_column_count") or 0),
        row.get("guessed_header_row"),
        str(row.get("sheet_type") or "unknown"),
    )
    inserted = connection.execute(
        """
        INSERT INTO raw.workbook_sheet (
            source_file_id, sheet_index, sheet_name, max_row, max_column,
            non_empty_cells, merged_cell_count, formula_cell_count,
            blank_row_count, blank_column_count, guessed_header_row, sheet_type
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_file_id, sheet_index) DO UPDATE SET
            sheet_name = EXCLUDED.sheet_name,
            max_row = EXCLUDED.max_row,
            max_column = EXCLUDED.max_column,
            non_empty_cells = EXCLUDED.non_empty_cells,
            merged_cell_count = EXCLUDED.merged_cell_count,
            formula_cell_count = EXCLUDED.formula_cell_count,
            blank_row_count = EXCLUDED.blank_row_count,
            blank_column_count = EXCLUDED.blank_column_count,
            guessed_header_row = EXCLUDED.guessed_header_row,
            sheet_type = EXCLUDED.sheet_type
        RETURNING workbook_sheet_id
        """,
        values,
    ).fetchone()
    return int(inserted[0])


def _insert_raw_cells(
    connection: psycopg.Connection,
    frame: pd.DataFrame,
    source_file_ids: dict[str, str],
    workbook_sheet_ids: dict[tuple[str, int], int],
) -> None:
    if frame.empty:
        return
    rows = []
    for row in _dataframe_records(frame):
        source_hash = str(row["source_file_hash"])
        sheet_key = (source_hash, int(row["sheet_index"]))
        rows.append(
            (
                workbook_sheet_ids[sheet_key],
                int(row["row_number"]),
                int(row["column_number"]),
                str(row["cell_value"]),
            )
        )
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO raw.cell (workbook_sheet_id, row_number, column_number, cell_value)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (workbook_sheet_id, row_number, column_number) DO NOTHING
            """,
            rows,
        )


def _insert_cgd_staging(
    connection: psycopg.Connection,
    run_id: str,
    frame: pd.DataFrame,
    source_file_ids: dict[str, str],
    workbook_sheet_ids: dict[tuple[str, int], int],
) -> int:
    if frame.empty:
        return 0
    rows = []
    for row in _dataframe_records(frame):
        source_hash = str(row["source_file_hash"])
        rows.append(
            (
                run_id,
                source_file_ids[source_hash],
                workbook_sheet_ids[(source_hash, int(row["sheet_index"]))],
                "cgd_budget_execution",
                int(row["sheet_index"]),
                str(row["sheet_name"]),
                int(row["row_number"]),
                row.get("fiscal_year"),
                row.get("fiscal_year_be"),
                row.get("as_of_date"),
                row.get("report_type"),
                row.get("entity_type"),
                row.get("entity_name"),
                row.get("entity_code"),
                row.get("expense_category"),
                row.get("budget_after_transfer_million_baht"),
                row.get("allocated_million_baht"),
                row.get("po_reserved_debt_million_baht"),
                row.get("disbursement_million_baht"),
                row.get("disbursement_pct"),
                row.get("expenditure_million_baht"),
                row.get("expenditure_pct"),
                row.get("monthly_target_gap_pct"),
                row.get("remaining_million_baht"),
                row.get("remaining_pct"),
                None,
            )
        )
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO staging.cgd_budget_execution (
                run_id, source_file_id, workbook_sheet_id, dataset_name,
                sheet_index, sheet_name, row_number, fiscal_year, fiscal_year_be,
                as_of_date, report_type, entity_type, entity_name, entity_code,
                expense_category, budget_after_transfer_million_baht,
                allocated_million_baht, po_reserved_debt_million_baht,
                disbursement_million_baht, disbursement_pct,
                expenditure_million_baht, expenditure_pct, monthly_target_gap_pct,
                remaining_million_baht, remaining_pct, source_value
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT DO NOTHING
            """,
            rows,
        )
    return len(rows)


def _insert_ocsc_staging(
    connection: psycopg.Connection,
    run_id: str,
    frame: pd.DataFrame,
    source_file_ids: dict[str, str],
    workbook_sheet_ids: dict[tuple[str, int], int],
) -> int:
    if frame.empty:
        return 0
    rows = []
    for row in _dataframe_records(frame):
        source_hash = str(row["source_file_hash"])
        rows.append(
            (
                run_id,
                source_file_ids[source_hash],
                workbook_sheet_ids[(source_hash, int(row["sheet_index"]))],
                "ocsc_government_manpower",
                int(row["sheet_index"]),
                str(row["sheet_name"]),
                int(row["row_number"]),
                row.get("fiscal_year"),
                row.get("fiscal_year_be"),
                row.get("entity_type"),
                row.get("ministry_name"),
                row.get("agency_name"),
                row.get("metric_name"),
                row.get("metric_group"),
                row.get("headcount"),
                row.get("percentage"),
                row.get("source_value"),
                row.get("source_unit"),
            )
        )
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO staging.ocsc_workforce (
                run_id, source_file_id, workbook_sheet_id, dataset_name,
                sheet_index, sheet_name, row_number, fiscal_year, fiscal_year_be,
                entity_type, ministry_name, agency_name, metric_name, metric_group,
                headcount, percentage, source_value, source_unit
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            rows,
        )
    return len(rows)


def _upsert_public_release(
    connection: psycopg.Connection,
    run_id: str,
    source: ParsedPublicSource,
) -> tuple[str, bool, bool]:
    spec = source.spec
    inserted = connection.execute(
        """
        INSERT INTO raw.public_source_release (
            run_id, source_id, source_name, dataset_name, source_format, source_role,
            source_url, local_path, content_sha256, source_updated_at, record_count, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (source_id, content_sha256) DO NOTHING
        RETURNING release_id
        """,
        (
            run_id,
            spec.source_id,
            spec.source_name,
            spec.dataset_name,
            spec.format,
            spec.source_role,
            spec.file_url or spec.source_page_url,
            str(spec.path),
            source.content_sha256,
            source.source_updated_at,
            len(source.records),
            json.dumps(source.metadata, ensure_ascii=False, default=str),
        ),
    ).fetchone()
    if inserted:
        return str(inserted[0]), True, False
    existing = connection.execute(
        """
        SELECT
            release.release_id,
            EXISTS (
                SELECT 1
                FROM ops.public_watermark_event AS event
                WHERE event.release_id = release.release_id
                  AND event.status <> 'failed'
            ) AS committed
        FROM raw.public_source_release AS release
        WHERE release.source_id = %s AND release.content_sha256 = %s
        """,
        (spec.source_id, source.content_sha256),
    ).fetchone()
    if not existing:
        raise RuntimeError(f"Public source release disappeared: {spec.source_id}")
    return str(existing[0]), False, bool(existing[1])


def _insert_public_raw_records(
    connection: psycopg.Connection,
    release_id: str,
    frame: pd.DataFrame,
) -> None:
    if frame.empty:
        return
    rows = []
    for row in _dataframe_records(frame):
        rows.append(
            (
                release_id,
                int(row["source_record_number"]),
                row["record_key"],
                row.get("period_end"),
                json.dumps(row.get("raw_payload") or {}, ensure_ascii=False, default=str),
            )
        )
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO raw.public_record (
                release_id, source_record_number, record_key, watermark_value, payload
            )
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (release_id, record_key) DO NOTHING
            """,
            rows,
        )


def _insert_public_staging_records(
    connection: psycopg.Connection,
    run_id: str,
    release_id: str,
    source: ParsedPublicSource,
    frame: pd.DataFrame,
) -> None:
    if frame.empty:
        return
    rows = []
    for row in _dataframe_records(frame):
        rows.append(
            (
                run_id,
                release_id,
                row["source_id"],
                source.content_sha256,
                row["source_format"],
                row["source_role"],
                row["record_key"],
                int(row["source_record_number"]),
                row.get("period_start"),
                row.get("period_end"),
                row["period_grain"],
                row.get("calendar_year"),
                row.get("calendar_year_be"),
                row.get("fiscal_year"),
                row.get("fiscal_year_be"),
                row["entity_type"],
                row.get("entity_code"),
                row["entity_name"],
                row.get("geography_type"),
                row.get("geography_code"),
                row.get("geography_name"),
                row.get("category"),
                row.get("subcategory"),
                row["metric_name"],
                row["metric_unit"],
                row.get("value"),
                row.get("reference_metric"),
                row.get("reference_value"),
                row["source_url"],
                json.dumps(row.get("raw_payload") or {}, ensure_ascii=False, default=str),
            )
        )
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO staging.public_indicator (
                run_id, release_id, source_id, content_sha256, source_format, source_role,
                record_key, source_record_number, period_start, period_end, period_grain,
                calendar_year, calendar_year_be, fiscal_year, fiscal_year_be, entity_type,
                entity_code, entity_name, geography_type, geography_code, geography_name,
                category, subcategory, metric_name, metric_unit, value, reference_metric,
                reference_value, source_url, raw_payload
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
            )
            ON CONFLICT (release_id, record_key, metric_name) DO NOTHING
            """,
            rows,
        )


def _upsert_entity(
    connection: psycopg.Connection,
    *,
    dataset_name: str,
    entity_name: str,
    entity_type: str,
    entity_code: Any,
    ministry_name: Any,
) -> tuple[str, bool]:
    inserted = connection.execute(
        """
        INSERT INTO core.entity (
            dataset_name, source_entity_name, source_entity_type,
            source_entity_code, ministry_name
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (dataset_name, source_entity_name, source_entity_type) DO NOTHING
        RETURNING entity_id
        """,
        (dataset_name, entity_name, entity_type, entity_code, ministry_name),
    ).fetchone()
    if inserted:
        return str(inserted[0]), True
    return str(
        connection.execute(
            """
            SELECT entity_id
            FROM core.entity
            WHERE dataset_name = %s AND source_entity_name = %s AND source_entity_type = %s
            """,
            (dataset_name, entity_name, entity_type),
        ).fetchone()[0]
    ), False


def _cgd_core_values(
    row: dict[str, Any],
    run_id: str,
    source_file_ids: dict[str, str],
    workbook_sheet_ids: dict[tuple[str, int], int],
    entity_id: str,
) -> tuple[Any, ...]:
    source_hash = str(row["source_file_hash"])
    return (
        run_id,
        source_file_ids[source_hash],
        workbook_sheet_ids[(source_hash, int(row["sheet_index"]))],
        entity_id,
        "cgd_budget_execution",
        int(row["sheet_index"]),
        row["sheet_name"],
        int(row["row_number"]),
        row.get("fiscal_year"),
        row.get("fiscal_year_be"),
        row.get("as_of_date"),
        row.get("report_type"),
        row.get("entity_type"),
        row.get("entity_name"),
        row.get("entity_code"),
        row.get("expense_category"),
        row.get("budget_after_transfer_million_baht"),
        row.get("allocated_million_baht"),
        row.get("po_reserved_debt_million_baht"),
        row.get("disbursement_million_baht"),
        row.get("disbursement_pct"),
        row.get("expenditure_million_baht"),
        row.get("expenditure_pct"),
        row.get("monthly_target_gap_pct"),
        row.get("remaining_million_baht"),
        row.get("remaining_pct"),
    )


def _ocsc_core_values(
    row: dict[str, Any],
    run_id: str,
    source_file_ids: dict[str, str],
    workbook_sheet_ids: dict[tuple[str, int], int],
    entity_id: str,
) -> tuple[Any, ...]:
    source_hash = str(row["source_file_hash"])
    return (
        run_id,
        source_file_ids[source_hash],
        workbook_sheet_ids[(source_hash, int(row["sheet_index"]))],
        entity_id,
        "ocsc_government_manpower",
        int(row["sheet_index"]),
        row["sheet_name"],
        int(row["row_number"]),
        row.get("fiscal_year"),
        row.get("fiscal_year_be"),
        row.get("entity_type"),
        row.get("ministry_name"),
        row.get("agency_name"),
        row.get("metric_name"),
        row.get("metric_group"),
        row.get("headcount"),
        row.get("percentage"),
        row.get("source_value"),
        row.get("source_unit"),
    )


def _dataframe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return [
        {column: _python_value(value) for column, value in row.items()}
        for row in frame.to_dict("records")
    ]


def _python_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item") and not isinstance(value, (str, bytes, Decimal)):
        return value.item()
    return value


def _json_sample(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"text": value}
    return value


def _utc_now() -> datetime:
    return datetime.now(UTC)
