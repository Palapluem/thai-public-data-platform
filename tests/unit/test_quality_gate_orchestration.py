import pytest

from thai_data_platform import orchestration
from thai_data_platform.quality.gate import QualityGateError


def test_quality_gate_marks_run_failed_when_persisted_evidence_is_invalid(monkeypatch):
    state = {"context": {"run_id": "run-1"}}
    failures = []

    monkeypatch.setattr(orchestration, "_required_env", lambda _: "postgres-url")
    monkeypatch.setattr(
        orchestration.postgres,
        "assert_persisted_quality_gate",
        lambda *_: (_ for _ in ()).throw(QualityGateError("stale gate")),
    )
    monkeypatch.setattr(
        orchestration.postgres,
        "mark_run_failed",
        lambda postgres_url, run_id, message: failures.append(
            (postgres_url, run_id, message)
        ),
    )

    with pytest.raises(QualityGateError, match="stale gate"):
        orchestration.quality_gate(state)

    assert failures == [("postgres-url", "run-1", "stale gate")]
