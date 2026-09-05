"""Airflow-facing task adapters.

The DAG passes only small JSON-safe state between tasks. Excel parsing and
database work remain in the reusable package modules; intermediate extracts
are written to the shared local run directory so parallel ingestion tasks do
not place dataframes in the Airflow metadata database.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

from thai_data_platform.config import expected_row_counts, source_metadata
from thai_data_platform.ingestion.metadata import new_run_id
from thai_data_platform.quality.checks import run_data_quality_checks
from thai_data_platform.quality.gate import QualityGateError, evaluate_quality_gate
from thai_data_platform.quality.schema_contract import validate_extract_contracts
from thai_data_platform.storage.landing import land_file
from thai_data_platform.transform.cgd import CgdExtract, extract_cgd_workbook
from thai_data_platform.transform.ocsc import OcscExtract, extract_ocsc_workbook
from thai_data_platform.warehouse import clickhouse, postgres


def prepare_run_context(
    *,
    ocsc_path: str | Path,
    cgd_path: str | Path,
    raw_root: str | Path = "data/raw",
    manifest_path: str | Path = "config/source_manifest.json",
    migrations_dir: str | Path = "sql/postgres",
    serving_migrations_dir: str | Path = "sql/clickhouse",
    query_dir: str | Path = "analytics/queries",
    schema_contract_path: str | Path = "config/schema_contracts.json",
    run_type: str = "manual",
) -> dict[str, Any]:
    """Land sources, create a run row and return non-secret task context."""
    postgres_url = _required_env("POSTGRES_URL")
    landed_ocsc = land_file(ocsc_path, "ocsc_government_manpower", raw_root)
    landed_cgd = land_file(cgd_path, "cgd_budget_execution", raw_root)
    ocsc_meta = source_metadata("ocsc_government_manpower", landed_ocsc.path, manifest_path)
    cgd_meta = source_metadata("cgd_budget_execution", landed_cgd.path, manifest_path)
    run_id = new_run_id()
    artifact_dir = Path("data/processed/runs") / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    postgres.run_migrations(postgres_url, migrations_dir)
    postgres.prepare_run(
        postgres_url,
        run_id,
        [ocsc_meta.sha256, cgd_meta.sha256],
        run_type=run_type,
    )
    return {
        "run_id": run_id,
        "ocsc_path": str(ocsc_meta.path),
        "cgd_path": str(cgd_meta.path),
        "raw_root": str(raw_root),
        "manifest_path": str(manifest_path),
        "migrations_dir": str(migrations_dir),
        "serving_migrations_dir": str(serving_migrations_dir),
        "query_dir": str(query_dir),
        "schema_contract_path": str(schema_contract_path),
        "run_type": run_type,
        "artifact_dir": str(artifact_dir),
        "source_hashes": {"ocsc": ocsc_meta.sha256, "cgd": cgd_meta.sha256},
    }


def ingest_cgd(context: dict[str, Any]) -> dict[str, Any]:
    """Parse the CGD workbook and persist a JSON-safe handoff artifact."""
    meta = source_metadata(
        "cgd_budget_execution",
        context["cgd_path"],
        context["manifest_path"],
    )
    extract = extract_cgd_workbook(context["cgd_path"], meta, context["run_id"])
    artifact_path = Path(context["artifact_dir"]) / "cgd_extract.json"
    _write_json(
        artifact_path,
        {
            "budget_execution": _frame_payload(extract.budget_execution),
            "raw_cells": _frame_payload(extract.raw_cells),
            "workbook_sheets": _frame_payload(extract.workbook_sheets),
            "as_of_date": extract.as_of_date.isoformat() if extract.as_of_date else None,
        },
    )
    return {"context": context, "artifact_path": str(artifact_path)}


def ingest_ocsc(context: dict[str, Any]) -> dict[str, Any]:
    """Parse the OCSC workbook and persist a JSON-safe handoff artifact."""
    meta = source_metadata(
        "ocsc_government_manpower",
        context["ocsc_path"],
        context["manifest_path"],
    )
    extract = extract_ocsc_workbook(context["ocsc_path"], meta, context["run_id"])
    artifact_path = Path(context["artifact_dir"]) / "ocsc_extract.json"
    _write_json(
        artifact_path,
        {
            "workforce_agency": _frame_payload(extract.workforce_agency),
            "workforce_profile": _frame_payload(extract.workforce_profile),
            "raw_cells": _frame_payload(extract.raw_cells),
            "workbook_sheets": _frame_payload(extract.workbook_sheets),
        },
    )
    return {"context": context, "artifact_path": str(artifact_path)}


def validate_staging(
    cgd_handoff: dict[str, Any],
    ocsc_handoff: dict[str, Any],
) -> dict[str, Any]:
    """Load parser artifacts, persist staging evidence and run the DQ gate."""
    context = cgd_handoff["context"]
    if context["run_id"] != ocsc_handoff["context"]["run_id"]:
        raise ValueError("CGD and OCSC handoffs belong to different pipeline runs")
    postgres_url = _required_env("POSTGRES_URL")
    cgd_extract = _load_cgd_extract(cgd_handoff["artifact_path"])
    ocsc_extract = _load_ocsc_extract(ocsc_handoff["artifact_path"])
    sources = _sources(context, cgd_extract.as_of_date)
    try:
        validate_extract_contracts(
            cgd_extract,
            ocsc_extract,
            context["schema_contract_path"],
        )
        stage_result = postgres.stage_extracts(
            postgres_url,
            context["run_id"],
            sources,
            cgd_extract,
            ocsc_extract,
        )
        ocsc_frame = pd.concat(
            [ocsc_extract.workforce_agency, ocsc_extract.workforce_profile],
            ignore_index=True,
        )
        expected_counts = postgres.previous_successful_row_counts(postgres_url)
        expected_counts.update(expected_row_counts(sources, context["manifest_path"]))
        issues = run_data_quality_checks(
            cgd_extract.budget_execution,
            ocsc_frame,
            context["run_id"],
            source_hashes=[source.sha256 for source in sources],
            expected_row_counts=expected_counts,
        )
        gate = evaluate_quality_gate(issues)
        postgres.record_quality_results(
            postgres_url,
            context["run_id"],
            issues,
            passed=gate.passed,
        )
        if not gate.passed:
            raise QualityGateError(
                f"Quality gate blocked publication with {gate.blocking_issue_count} blocking checks"
            )
    except QualityGateError:
        raise
    except Exception as exc:
        postgres.mark_run_failed(postgres_url, context["run_id"], str(exc))
        raise

    return {
        "context": context,
        "cgd_artifact_path": cgd_handoff["artifact_path"],
        "ocsc_artifact_path": ocsc_handoff["artifact_path"],
        "stage_result": _stage_payload(stage_result),
        "dq_failed_checks": int(issues["status"].eq("failed").sum()),
    }


def publish_core(state: dict[str, Any]) -> dict[str, Any]:
    """Publish only the validated extracts into PostgreSQL core."""
    context = state["context"]
    postgres_url = _required_env("POSTGRES_URL")
    cgd_extract = _load_cgd_extract(state["cgd_artifact_path"])
    ocsc_extract = _load_ocsc_extract(state["ocsc_artifact_path"])
    sources = _sources(context, cgd_extract.as_of_date)
    ocsc_frame = pd.concat(
        [ocsc_extract.workforce_agency, ocsc_extract.workforce_profile],
        ignore_index=True,
    )
    try:
        counts = postgres.publish_core(
            postgres_url,
            context["run_id"],
            sources,
            cgd_extract.budget_execution,
            ocsc_frame,
            _stage_from_payload(state["stage_result"]),
        )
    except Exception as exc:
        postgres.mark_run_failed(postgres_url, context["run_id"], str(exc))
        raise
    return {**state, "core_counts": counts}


def quality_gate(state: dict[str, Any]) -> dict[str, Any]:
    """Re-check persisted DQ evidence after core publication."""
    postgres_url = _required_env("POSTGRES_URL")
    run_id = state["context"]["run_id"]
    try:
        postgres.assert_persisted_quality_gate(postgres_url, run_id)
    except QualityGateError as exc:
        postgres.mark_run_failed(postgres_url, run_id, str(exc))
        raise
    return state


def publish_clickhouse(state: dict[str, Any]) -> dict[str, Any]:
    """Publish the approved core handoff to ClickHouse once per source hash."""
    context = state["context"]
    postgres_url = _required_env("POSTGRES_URL")
    cgd_extract = _load_cgd_extract(state["cgd_artifact_path"])
    ocsc_extract = _load_ocsc_extract(state["ocsc_artifact_path"])
    sources = _sources(context, cgd_extract.as_of_date)
    ocsc_frame = pd.concat(
        [ocsc_extract.workforce_agency, ocsc_extract.workforce_profile],
        ignore_index=True,
    )
    client = clickhouse.connect(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DATABASE", "analytics"),
    )
    try:
        clickhouse.run_migrations(client, context["serving_migrations_dir"])
        counts = clickhouse.publish_frames(
            client,
            run_id=context["run_id"],
            source_file_ids=_stage_from_payload(state["stage_result"]).source_file_ids,
            sources=sources,
            cgd_frame=cgd_extract.budget_execution,
            ocsc_frame=ocsc_frame,
        )
    except Exception as exc:
        postgres.mark_run_failed(postgres_url, context["run_id"], str(exc))
        raise
    finally:
        client.close()
    postgres.mark_serving_published(postgres_url, context["run_id"])
    return {**state, "serving_counts": counts}


def analytics_smoke(state: dict[str, Any]) -> dict[str, Any]:
    """Run read-only analytical queries after serving publication."""
    client = clickhouse.connect(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DATABASE", "analytics"),
    )
    try:
        results = clickhouse.run_smoke_queries(client, state["context"]["query_dir"])
    finally:
        client.close()
    return {"run_id": state["context"]["run_id"], "smoke_counts": results}


def _sources(context: dict[str, Any], cgd_as_of_date: date | None) -> list[Any]:
    ocsc = source_metadata(
        "ocsc_government_manpower",
        context["ocsc_path"],
        context["manifest_path"],
    )
    cgd = source_metadata(
        "cgd_budget_execution",
        context["cgd_path"],
        context["manifest_path"],
    )
    if cgd_as_of_date:
        cgd = replace(cgd, as_of_date=cgd_as_of_date.isoformat())
    return [ocsc, cgd]


def _load_cgd_extract(path: str | Path) -> CgdExtract:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    as_of_date = payload.get("as_of_date")
    return CgdExtract(
        budget_execution=_restore_frame(payload["budget_execution"], "cgd"),
        raw_cells=_restore_frame(payload["raw_cells"], "raw"),
        workbook_sheets=_restore_frame(payload["workbook_sheets"], "sheets"),
        as_of_date=date.fromisoformat(as_of_date) if as_of_date else None,
    )


def _load_ocsc_extract(path: str | Path) -> OcscExtract:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return OcscExtract(
        workforce_agency=_restore_frame(payload["workforce_agency"], "ocsc"),
        workforce_profile=_restore_frame(payload["workforce_profile"], "ocsc"),
        raw_cells=_restore_frame(payload["raw_cells"], "raw"),
        workbook_sheets=_restore_frame(payload["workbook_sheets"], "sheets"),
    )


def _frame_payload(frame: pd.DataFrame) -> dict[str, Any]:
    return {"columns": list(frame.columns), "records": frame.to_dict(orient="records")}


def _restore_frame(payload: dict[str, Any], dataset: str) -> pd.DataFrame:
    frame = pd.DataFrame(payload["records"], columns=payload["columns"])
    integer_columns = {
        "raw": ["sheet_index", "row_number", "column_number"],
        "sheets": [
            "sheet_index",
            "max_row",
            "max_column",
            "non_empty_cells",
            "merged_cell_count",
            "formula_cell_count",
            "blank_row_count",
            "blank_column_count",
        ],
        "cgd": ["sheet_index", "row_number", "fiscal_year", "fiscal_year_be"],
        "ocsc": ["sheet_index", "row_number", "fiscal_year", "fiscal_year_be", "headcount"],
    }
    for column in integer_columns.get(dataset, []):
        if column in frame.columns:
            frame[column] = frame[column].map(_to_int_or_none)
    decimal_columns = {
        "cgd": [
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
        ],
        "ocsc": ["percentage"],
    }
    for column in decimal_columns.get(dataset, []):
        if column in frame.columns:
            frame[column] = frame[column].map(_to_decimal_or_none)
    return frame


def _stage_payload(result: postgres.StageResult) -> dict[str, Any]:
    return {
        "source_file_ids": result.source_file_ids,
        "workbook_sheet_ids": {
            f"{source_hash}|{sheet_index}": workbook_sheet_id
            for (source_hash, sheet_index), workbook_sheet_id in result.workbook_sheet_ids.items()
        },
        "raw_cell_count": result.raw_cell_count,
        "cgd_row_count": result.cgd_row_count,
        "ocsc_row_count": result.ocsc_row_count,
    }


def _stage_from_payload(payload: dict[str, Any]) -> postgres.StageResult:
    return postgres.StageResult(
        source_file_ids={str(key): str(value) for key, value in payload["source_file_ids"].items()},
        workbook_sheet_ids={
            (key.rsplit("|", 1)[0], int(key.rsplit("|", 1)[1])): int(value)
            for key, value in payload["workbook_sheet_ids"].items()
        },
        raw_cell_count=int(payload["raw_cell_count"]),
        cgd_row_count=int(payload["cgd_row_count"]),
        ocsc_row_count=int(payload["ocsc_row_count"]),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _to_int_or_none(value: Any) -> int | None:
    if _is_missing(value):
        return None
    return int(value)


def _to_decimal_or_none(value: Any) -> Decimal | None:
    if _is_missing(value):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _is_missing(value: Any) -> bool:
    if value is None or (isinstance(value, str) and value == ""):
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
