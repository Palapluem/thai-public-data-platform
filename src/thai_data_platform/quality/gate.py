"""Fail-closed evaluation of persisted data-quality results."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    blocking_issue_count: int
    issues: pd.DataFrame


def evaluate_quality_gate(issues: pd.DataFrame) -> QualityGateResult:
    if issues.empty:
        return QualityGateResult(passed=False, blocking_issue_count=1, issues=issues)
    failed = issues[issues["status"].eq("failed")] if "status" in issues.columns else issues
    if "blocking" in failed.columns:
        blocking = failed[failed["blocking"].fillna(True).astype(bool)]
    else:
        blocking = (
            failed[failed["severity"].eq("error")]
            if "severity" in failed.columns
            else failed
        )
    return QualityGateResult(
        passed=blocking.empty,
        blocking_issue_count=len(blocking),
        issues=issues,
    )


def assert_quality_gate(issues: pd.DataFrame) -> QualityGateResult:
    result = evaluate_quality_gate(issues)
    if not result.passed:
        checks = ", ".join(issues.loc[issues["status"].eq("failed"), "check_name"].astype(str))
        raise QualityGateError(f"Quality gate blocked publication: {checks}")
    return result


class QualityGateError(RuntimeError):
    """Raised when blocking DQ evidence prevents downstream publication."""
