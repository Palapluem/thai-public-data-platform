"""Thin Airflow DAG for the reproducible multi-format public-source slice."""

from __future__ import annotations

import os

import pendulum
from airflow.decorators import dag, task

from thai_data_platform.public_sources.dashboard import build_public_dashboard
from thai_data_platform.public_sources.pipeline import (
    connection_kwargs_from_env,
    run_public_pipeline,
)


@dag(
    dag_id="thai_public_multiformat",
    schedule=os.getenv("AIRFLOW_PUBLIC_SCHEDULE") or None,
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Bangkok"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": pendulum.duration(minutes=5)},
    tags=["thai-public-data", "multi-format", "watermark", "analytics"],
)
def thai_public_multiformat_pipeline():
    @task(task_id="run_public_multiformat_pipeline")
    def run_task():
        return run_public_pipeline(
            **connection_kwargs_from_env(),
            source_config_path=os.getenv(
                "PUBLIC_SOURCE_CONFIG",
                "/opt/airflow/config/public_sources.yml",
            ),
            migrations_dir=os.getenv("POSTGRES_MIGRATIONS", "/opt/airflow/sql/postgres"),
            serving_migrations_dir=os.getenv(
                "CLICKHOUSE_MIGRATIONS",
                "/opt/airflow/sql/clickhouse",
            ),
            query_dir=os.getenv(
                "PUBLIC_ANALYTICS_QUERY_DIR",
                "/opt/airflow/analytics/queries/public",
            ),
            run_type=os.getenv("PUBLIC_PIPELINE_RUN_TYPE", "scheduled"),
        ).__dict__

    @task(task_id="build_public_dashboard")
    def dashboard_task(_pipeline_state):
        return build_public_dashboard(
            **connection_kwargs_from_env(),
            output_path=os.getenv(
                "PUBLIC_DASHBOARD_OUTPUT",
                "/opt/airflow/data/processed/public_dashboard/index.html",
            ),
        )

    dashboard_task(run_task())


thai_public_multiformat_pipeline = thai_public_multiformat_pipeline()
