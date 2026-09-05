"""Application workflow for the multi-format public-indicator slice."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thai_data_platform.ingestion.metadata import new_run_id
from thai_data_platform.public_sources.quality import run_public_quality_checks
from thai_data_platform.public_sources.readers import parse_public_sources
from thai_data_platform.public_sources.watermark import decide_watermark, select_incremental_records
from thai_data_platform.quality.gate import QualityGateError, evaluate_quality_gate
from thai_data_platform.warehouse import clickhouse, postgres


@dataclass(frozen=True)
class PublicPipelineResult:
    run_id: str
    run_type: str
    status: str
    source_summaries: list[dict[str, Any]]
    stage_counts: dict[str, int]
    core_counts: dict[str, int]
    serving_counts: dict[str, int]
    watermark_status: dict[str, str]
    watermark_advanced_count: int
    dq_failed_checks: int
    smoke_counts: dict[str, int]


def run_public_pipeline(
    *,
    postgres_url: str,
    clickhouse_host: str,
    clickhouse_port: int,
    clickhouse_user: str,
    clickhouse_password: str,
    clickhouse_database: str = "analytics",
    source_config_path: str | Path = "config/public_sources.yml",
    migrations_dir: str | Path = "sql/postgres",
    serving_migrations_dir: str | Path = "sql/clickhouse",
    query_dir: str | Path = "analytics/queries/public",
    run_type: str = "scheduled",
    source_ids: set[str] | None = None,
) -> PublicPipelineResult:
    """Run parse → raw/staging → DQ gate → core → ClickHouse publication.

    The workflow is intentionally separate from the original Excel pipeline:
    source-specific adapters return one canonical frame, while this function
    owns the same operational guarantees (run state, DQ evidence, idempotent
    releases and post-serving watermark commit).
    """
    parsed_sources = parse_public_sources(source_config_path, source_ids=source_ids)
    run_id = new_run_id()
    postgres.run_migrations(postgres_url, migrations_dir)
    postgres.prepare_run(
        postgres_url,
        run_id,
        [source.content_sha256 for source in parsed_sources],
        pipeline_name="thai_public_multiformat",
        run_type=run_type,
    )
    try:
        existing = postgres.public_release_exists(postgres_url, parsed_sources)
        committed = postgres.public_release_committed(postgres_url, parsed_sources)
        previous = postgres.public_watermarks(
            postgres_url,
            [source.spec.source_id for source in parsed_sources],
        )
        selected_records = {}
        for source in parsed_sources:
            source_id = source.spec.source_id
            decision = decide_watermark(
                previous.get(source_id),
                source.watermark,
                is_new_release=not existing[source_id] or not committed[source_id],
            )
            selected_records[source_id] = select_incremental_records(
                source.records,
                decision,
                run_type=run_type,
                watermark_field=source.spec.watermark_field,
            )

        stage_result = postgres.stage_public_sources(
            postgres_url,
            run_id,
            parsed_sources,
            selected_records,
            run_type=run_type,
        )
        quality_frame = run_public_quality_checks(parsed_sources, run_id)
        gate = evaluate_quality_gate(quality_frame)
        postgres.record_quality_results(
            postgres_url,
            run_id,
            quality_frame,
            passed=gate.passed,
        )
        if not gate.passed:
            raise QualityGateError(
                f"Public quality gate blocked publication with {gate.blocking_issue_count} checks"
            )
        core_counts = postgres.publish_public_core(postgres_url, run_id)
        postgres.assert_persisted_quality_gate(postgres_url, run_id)

        client = clickhouse.connect(
            host=clickhouse_host,
            port=clickhouse_port,
            username=clickhouse_user,
            password=clickhouse_password,
            database=clickhouse_database,
        )
        try:
            clickhouse.run_migrations(client, serving_migrations_dir)
            serving_counts = clickhouse.publish_public_indicators(
                client,
                run_id=run_id,
                stage_result=stage_result,
                sources=parsed_sources,
                selected_records=selected_records,
            )
            smoke_counts = clickhouse.run_public_smoke_queries(client, query_dir)
        finally:
            client.close()

        advanced_count = postgres.mark_public_watermarks(postgres_url, run_id, stage_result)
        postgres.mark_serving_published(postgres_url, run_id)
        return PublicPipelineResult(
            run_id=run_id,
            run_type=run_type,
            status="serving_published",
            source_summaries=[source.as_summary() for source in parsed_sources],
            stage_counts={
                "raw_source_records": sum(stage_result.record_counts.values()),
                "selected_public_indicators": stage_result.selected_row_count,
            },
            core_counts=core_counts,
            serving_counts=serving_counts,
            watermark_status={
                source_id: decision.status
                for source_id, decision in stage_result.decisions.items()
            },
            watermark_advanced_count=advanced_count,
            dq_failed_checks=int(quality_frame["status"].eq("failed").sum()),
            smoke_counts=smoke_counts,
        )
    except QualityGateError:
        raise
    except Exception as exc:
        postgres.mark_run_failed(postgres_url, run_id, str(exc))
        raise


def connection_kwargs_from_env() -> dict[str, Any]:
    """Build non-secret CLI/DAG connection arguments from environment variables."""
    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        raise RuntimeError("Missing required environment variable: POSTGRES_URL")
    return {
        "postgres_url": postgres_url,
        "clickhouse_host": os.getenv("CLICKHOUSE_HOST", "localhost"),
        "clickhouse_port": int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
        "clickhouse_user": os.getenv("CLICKHOUSE_USER", "default"),
        "clickhouse_password": os.getenv("CLICKHOUSE_PASSWORD", ""),
        "clickhouse_database": os.getenv("CLICKHOUSE_DATABASE", "analytics"),
    }
