from pathlib import Path


def test_dag_contains_required_task_ids_and_thin_adapter_boundary():
    dag_path = Path("dags/thai_public_data_pipeline.py")
    text = dag_path.read_text(encoding="utf-8")

    required = [
        "prepare_run",
        "ingest_cgd",
        "ingest_ocsc",
        "validate_staging",
        "publish_core",
        "quality_gate",
        "publish_clickhouse",
        "analytics_smoke",
    ]
    assert all(f'task_id="{task_id}"' in text for task_id in required)
    assert "orchestration.prepare_run_context" in text
    assert (
        "orchestration.ingest_cgd"
        not in text.split("def ingest_cgd_task", 1)[1].split(")", 1)[0]
    )
    assert text.index("validated = validate_staging_task") < text.index(
        "core_published = publish_core_task"
    )
    assert text.index("core_published = publish_core_task") < text.index(
        "gated = quality_gate_task"
    )


def test_multiformat_dag_keeps_pipeline_and_dashboard_tasks_thin():
    dag_path = Path("dags/thai_public_multiformat_pipeline.py")
    text = dag_path.read_text(encoding="utf-8")

    assert 'dag_id="thai_public_multiformat"' in text
    assert 'task_id="run_public_multiformat_pipeline"' in text
    assert 'task_id="build_public_dashboard"' in text
    assert "run_public_pipeline" in text
    assert "build_public_dashboard" in text
