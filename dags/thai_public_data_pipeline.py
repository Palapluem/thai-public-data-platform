"""Thin Airflow orchestration for the Thai Public Data Platform."""

from __future__ import annotations

import os

import pendulum
from airflow.decorators import dag, task

from thai_data_platform import orchestration


@dag(
    dag_id="thai_public_data_platform",
    schedule=os.getenv("AIRFLOW_SCHEDULE") or None,
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Bangkok"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": pendulum.duration(minutes=5)},
    tags=["thai-public-data", "data-engineering"],
)
def thai_public_data_pipeline():
    """Orchestrate reusable package functions without embedding business rules."""

    @task(task_id="prepare_run")
    def prepare_run_task():
        return orchestration.prepare_run_context(
            ocsc_path=os.getenv(
                "OCSC_SOURCE_PATH",
                "datasets/ocsc/thai-gov-manpower-2567.4.xlsx",
            ),
            cgd_path=os.getenv("CGD_SOURCE_PATH", "datasets/cgd/2026.07.03.xlsx"),
            raw_root=os.getenv("RAW_ROOT", "data/raw"),
            manifest_path=os.getenv("SOURCE_MANIFEST", "config/source_manifest.json"),
            migrations_dir=os.getenv("POSTGRES_MIGRATIONS", "sql/postgres"),
            serving_migrations_dir=os.getenv(
                "CLICKHOUSE_MIGRATIONS",
                "sql/clickhouse",
            ),
            query_dir=os.getenv("ANALYTICS_QUERY_DIR", "analytics/queries"),
        )

    @task(task_id="ingest_cgd")
    def ingest_cgd_task(context):
        return orchestration.ingest_cgd(context)

    @task(task_id="ingest_ocsc")
    def ingest_ocsc_task(context):
        return orchestration.ingest_ocsc(context)

    @task(task_id="validate_staging")
    def validate_staging_task(cgd_handoff, ocsc_handoff):
        return orchestration.validate_staging(cgd_handoff, ocsc_handoff)

    @task(task_id="publish_core")
    def publish_core_task(state):
        return orchestration.publish_core(state)

    @task(task_id="quality_gate")
    def quality_gate_task(state):
        return orchestration.quality_gate(state)

    @task(task_id="publish_clickhouse")
    def publish_clickhouse_task(state):
        return orchestration.publish_clickhouse(state)

    @task(task_id="analytics_smoke")
    def analytics_smoke_task(state):
        return orchestration.analytics_smoke(state)

    run_context = prepare_run_task()
    cgd_handoff = ingest_cgd_task(run_context)
    ocsc_handoff = ingest_ocsc_task(run_context)
    validated = validate_staging_task(cgd_handoff, ocsc_handoff)
    core_published = publish_core_task(validated)
    gated = quality_gate_task(core_published)
    serving_published = publish_clickhouse_task(gated)
    analytics_smoke_task(serving_published)


thai_public_data_pipeline = thai_public_data_pipeline()
