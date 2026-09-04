"""Application workflow used by the CLI and Airflow task entry points."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

from thai_data_platform.config import expected_row_counts, source_metadata
from thai_data_platform.ingestion.metadata import new_run_id
from thai_data_platform.quality.checks import run_data_quality_checks
from thai_data_platform.quality.gate import QualityGateError, evaluate_quality_gate
from thai_data_platform.storage.landing import land_file
from thai_data_platform.transform.cgd import extract_cgd_workbook
from thai_data_platform.transform.ocsc import extract_ocsc_workbook
from thai_data_platform.warehouse import clickhouse, postgres


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    status: str
    stage_counts: dict[str, int]
    core_counts: dict[str, int]
    serving_counts: dict[str, int]
    dq_failed_checks: int


def run_pipeline(
    *,
    ocsc_path: str | Path,
    cgd_path: str | Path,
    postgres_url: str,
    clickhouse_host: str,
    clickhouse_port: int,
    clickhouse_user: str,
    clickhouse_password: str,
    clickhouse_database: str = "analytics",
    raw_root: str | Path = "data/raw",
    manifest_path: str | Path = "config/source_manifest.json",
    migrations_dir: str | Path = "sql/postgres",
    serving_migrations_dir: str | Path = "sql/clickhouse",
    query_dir: str | Path = "analytics/queries",
) -> PipelineResult:
    """Run the full local pipeline and fail closed before serving on bad data."""
    landed_ocsc = land_file(ocsc_path, "ocsc_government_manpower", raw_root)
    landed_cgd = land_file(cgd_path, "cgd_budget_execution", raw_root)
    ocsc_meta = source_metadata("ocsc_government_manpower", landed_ocsc.path, manifest_path)
    cgd_meta = source_metadata("cgd_budget_execution", landed_cgd.path, manifest_path)
    run_id = new_run_id()
    sources = [ocsc_meta, cgd_meta]

    postgres.run_migrations(postgres_url, migrations_dir)
    postgres.prepare_run(postgres_url, run_id, [source.sha256 for source in sources])
    try:
        cgd_extract = extract_cgd_workbook(landed_cgd.path, cgd_meta, run_id)
        ocsc_extract = extract_ocsc_workbook(landed_ocsc.path, ocsc_meta, run_id)
        if cgd_extract.as_of_date:
            cgd_meta = replace(cgd_meta, as_of_date=cgd_extract.as_of_date.isoformat())
            sources = [ocsc_meta, cgd_meta]

        stage_counts = postgres.stage_extracts(
            postgres_url,
            run_id,
            sources,
            cgd_extract,
            ocsc_extract,
        )
        ocsc_frame = pd.concat(
            [ocsc_extract.workforce_agency, ocsc_extract.workforce_profile],
            ignore_index=True,
        )
        expected_counts = postgres.previous_successful_row_counts(postgres_url)
        expected_counts.update(expected_row_counts(sources, manifest_path))
        dq_frame = run_data_quality_checks(
            cgd_extract.budget_execution,
            ocsc_frame,
            run_id,
            source_hashes=[source.sha256 for source in sources],
            expected_row_counts=expected_counts,
        )
        gate = evaluate_quality_gate(dq_frame)
        postgres.record_quality_results(postgres_url, run_id, dq_frame, passed=gate.passed)
        if not gate.passed:
            raise QualityGateError(
                f"Quality gate blocked publication with {gate.blocking_issue_count} blocking checks"
            )

        core_counts = postgres.publish_core(
            postgres_url,
            run_id,
            sources,
            cgd_extract.budget_execution,
            ocsc_frame,
            stage_counts,
        )
        client = clickhouse.connect(
            host=clickhouse_host,
            port=clickhouse_port,
            username=clickhouse_user,
            password=clickhouse_password,
            database=clickhouse_database,
        )
        try:
            clickhouse.run_migrations(client, serving_migrations_dir)
            serving_counts = clickhouse.publish_frames(
                client,
                run_id=run_id,
                source_file_ids=stage_counts.source_file_ids,
                sources=sources,
                cgd_frame=cgd_extract.budget_execution,
                ocsc_frame=ocsc_frame,
            )
            clickhouse.run_smoke_queries(client, query_dir)
        finally:
            client.close()
        postgres.mark_serving_published(postgres_url, run_id)
        failed_checks = int(dq_frame["status"].eq("failed").sum())
        return PipelineResult(
            run_id=run_id,
            status="serving_published",
            stage_counts={
                "raw_cells": stage_counts.raw_cell_count,
                "cgd_rows": stage_counts.cgd_row_count,
                "ocsc_rows": stage_counts.ocsc_row_count,
            },
            core_counts=core_counts,
            serving_counts=serving_counts,
            dq_failed_checks=failed_checks,
        )
    except QualityGateError:
        raise
    except Exception as exc:
        postgres.mark_run_failed(postgres_url, run_id, str(exc))
        raise


def profile_sources(
    *,
    ocsc_path: str | Path,
    cgd_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    from thai_data_platform.ingestion.excel_inspector import inspect_workbook

    payload = {
        "sources": {
            "ocsc_government_manpower": inspect_workbook(ocsc_path),
            "cgd_budget_execution": inspect_workbook(cgd_path),
        }
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload
