"""Data-quality checks for source-aligned staging data."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class DQIssue:
    check_name: str
    severity: str
    dataset_name: str
    table_name: str
    issue_count: int
    sample: str
    blocking: bool = True
    status: str = "failed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "severity": self.severity,
            "dataset_name": self.dataset_name,
            "table_name": self.table_name,
            "issue_count": self.issue_count,
            "sample": self.sample,
            "blocking": self.blocking,
            "status": self.status,
        }


def run_data_quality_checks(
    cgd_budget_execution: pd.DataFrame,
    ocsc_workforce: pd.DataFrame,
    run_id: str,
    *,
    source_hashes: Iterable[str] | None = None,
    expected_row_counts: dict[str, int] | None = None,
    row_count_threshold: Decimal = Decimal("0.50"),
) -> pd.DataFrame:
    """Return one evidence row per failed check, or one passed summary row."""
    issues: list[DQIssue] = []
    issues.extend(
        _check_cgd(
            cgd_budget_execution,
            source_hashes=set(source_hashes or []),
            expected_row_counts=expected_row_counts or {},
            row_count_threshold=row_count_threshold,
        )
    )
    issues.extend(
        _check_ocsc(
            ocsc_workforce,
            source_hashes=set(source_hashes or []),
            expected_row_counts=expected_row_counts or {},
            row_count_threshold=row_count_threshold,
        )
    )
    if not issues:
        issues.append(
            DQIssue(
                check_name="all_core_checks",
                severity="info",
                dataset_name="all",
                table_name="all",
                issue_count=0,
                sample="All configured core data-quality checks passed.",
                blocking=False,
                status="passed",
            )
        )
    frame = pd.DataFrame([issue.as_dict() for issue in issues])
    frame.insert(0, "ingestion_run_id", run_id)
    return frame


def _check_cgd(
    df: pd.DataFrame,
    *,
    source_hashes: set[str],
    expected_row_counts: dict[str, int],
    row_count_threshold: Decimal,
) -> list[DQIssue]:
    if df.empty:
        return [
            DQIssue(
                check_name="cgd_zero_row_extraction",
                severity="error",
                dataset_name="cgd_budget_execution",
                table_name="staging.cgd_budget_execution",
                issue_count=1,
                sample="No CGD budget rows were extracted.",
            )
        ]
    issues = _required_keys(df, "cgd_budget_execution", "staging.cgd_budget_execution", _CGD_KEYS)
    issues.extend(_source_foreign_key_check(df, "cgd_budget_execution", source_hashes))
    issues.extend(
        _allowed_value_checks(
            df,
            "cgd_budget_execution",
            {
                "report_type": {"disbursement", "expenditure"},
                "entity_type": {
                    "summary",
                    "ministry",
                    "agency",
                    "province",
                    "municipality",
                    "provincial_admin_org",
                    "state_enterprise",
                    "fund",
                    "total",
                },
                "expense_category": {"current", "investment", "total"},
            },
        )
    )
    issues.extend(
        _invalid_numeric_checks(
            df,
            "cgd_budget_execution",
            [*_CGD_AMOUNT_COLUMNS, *_CGD_PERCENTAGE_COLUMNS, *_CGD_SIGNED_PERCENTAGE_COLUMNS],
        )
    )
    issues.extend(_non_negative_checks(df, "cgd_budget_execution", _CGD_AMOUNT_COLUMNS))
    issues.extend(_percentage_checks(df, "cgd_budget_execution", _CGD_PERCENTAGE_COLUMNS))
    issues.extend(
        _bounded_checks(
            df,
            "cgd_budget_execution",
            _CGD_SIGNED_PERCENTAGE_COLUMNS,
            lower=Decimal("-100"),
            upper=Decimal("100"),
            check_prefix="signed_percentage_bounds",
        )
    )
    issues.extend(
        _duplicate_check(
            df,
            "cgd_duplicate_natural_grain",
            "cgd_budget_execution",
            "staging.cgd_budget_execution",
            _CGD_GRAIN,
        )
    )
    issues.extend(_cgd_total_reconciliation(df))
    issues.extend(
        _row_count_collapse(
            df,
            "cgd_budget_execution",
            expected_row_counts.get("cgd_budget_execution"),
            row_count_threshold,
        )
    )
    return issues


def _check_ocsc(
    df: pd.DataFrame,
    *,
    source_hashes: set[str],
    expected_row_counts: dict[str, int],
    row_count_threshold: Decimal,
) -> list[DQIssue]:
    if df.empty:
        return [
            DQIssue(
                check_name="ocsc_zero_row_extraction",
                severity="error",
                dataset_name="ocsc_government_manpower",
                table_name="staging.ocsc_workforce",
                issue_count=1,
                sample="No OCSC workforce rows were extracted.",
            )
        ]
    issues = _required_keys(df, "ocsc_government_manpower", "staging.ocsc_workforce", _OCSC_KEYS)
    issues.extend(_source_foreign_key_check(df, "ocsc_government_manpower", source_hashes))
    issues.extend(
        _allowed_value_checks(
            df,
            "ocsc_government_manpower",
            {
                "entity_type": {"ministry", "agency", "total"},
                "metric_group": {
                    "employment_type",
                    "age",
                    "gender",
                    "education_level",
                    "total",
                },
                "source_unit": {"person", "pct", "year"},
            },
        )
    )
    issues.extend(
        _invalid_numeric_checks(df, "ocsc_government_manpower", ["headcount", "percentage"])
    )
    issues.extend(_non_negative_checks(df, "ocsc_government_manpower", ["headcount"]))
    issues.extend(_percentage_checks(df, "ocsc_government_manpower", ["percentage"]))
    issues.extend(
        _duplicate_check(
            df,
            "ocsc_duplicate_natural_grain",
            "ocsc_government_manpower",
            "staging.ocsc_workforce",
            _OCSC_GRAIN,
        )
    )
    issues.extend(
        _row_count_collapse(
            df,
            "ocsc_government_manpower",
            expected_row_counts.get("ocsc_government_manpower"),
            row_count_threshold,
        )
    )
    return issues


_CGD_KEYS = [
    "source_file_hash",
    "sheet_index",
    "sheet_name",
    "row_number",
    "report_type",
    "entity_type",
    "entity_name",
    "expense_category",
]
_CGD_GRAIN = [
    "source_file_hash",
    "sheet_index",
    "row_number",
    "report_type",
    "entity_name",
    "entity_code",
    "expense_category",
]
_CGD_AMOUNT_COLUMNS = [
    "budget_after_transfer_million_baht",
    "allocated_million_baht",
    "po_reserved_debt_million_baht",
    "disbursement_million_baht",
    "expenditure_million_baht",
    "remaining_million_baht",
]
_CGD_PERCENTAGE_COLUMNS = [
    "disbursement_pct",
    "expenditure_pct",
    "remaining_pct",
]
_CGD_SIGNED_PERCENTAGE_COLUMNS = ["monthly_target_gap_pct"]
_OCSC_KEYS = [
    "source_file_hash",
    "sheet_index",
    "sheet_name",
    "row_number",
    "entity_type",
    "agency_name",
    "metric_name",
    "metric_group",
    "source_unit",
]
_OCSC_GRAIN = ["source_file_hash", "sheet_index", "row_number", "agency_name", "metric_name"]


def _required_keys(
    df: pd.DataFrame,
    dataset_name: str,
    table_name: str,
    required_columns: list[str],
) -> list[DQIssue]:
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        return [
            DQIssue(
                check_name=f"{dataset_name}_required_keys",
                severity="error",
                dataset_name=dataset_name,
                table_name=table_name,
                issue_count=len(missing_columns),
                sample=json.dumps({"missing_columns": missing_columns}, ensure_ascii=False),
            )
        ]
    missing_mask = df[required_columns].isna().any(axis=1)
    for column in required_columns:
        missing_mask = missing_mask | df[column].map(
            lambda value: isinstance(value, str) and not value.strip()
        )
    bad = df[missing_mask]
    if bad.empty:
        return []
    return [
        DQIssue(
            check_name=f"{dataset_name}_required_keys",
            severity="error",
            dataset_name=dataset_name,
            table_name=table_name,
            issue_count=len(bad),
            sample=_sample(bad, required_columns),
        )
    ]


def _source_foreign_key_check(
    df: pd.DataFrame,
    dataset_name: str,
    source_hashes: set[str],
) -> list[DQIssue]:
    if "source_file_hash" not in df.columns:
        return []
    bad = df[df["source_file_hash"].map(lambda value: not _present(value))]
    if source_hashes:
        bad = pd.concat(
            [bad, df[~df["source_file_hash"].astype(str).isin(source_hashes)]],
            ignore_index=True,
        ).drop_duplicates()
    if bad.empty:
        return []
    return [
        DQIssue(
            check_name=f"{dataset_name}_foreign_key_integrity",
            severity="error",
            dataset_name=dataset_name,
            table_name="staging",
            issue_count=len(bad),
            sample=_sample(bad, ["source_file_hash"]),
        )
    ]


def _non_negative_checks(df: pd.DataFrame, dataset_name: str, columns: list[str]) -> list[DQIssue]:
    issues: list[DQIssue] = []
    for column in columns:
        if column not in df.columns:
            continue
        bad = df[df[column].map(lambda value: (_parse_decimal(value) or Decimal("0")) < 0)]
        if not bad.empty:
            issues.append(
                DQIssue(
                    check_name=f"{dataset_name}_non_negative_{column}",
                    severity="error",
                    dataset_name=dataset_name,
                    table_name="staging",
                    issue_count=len(bad),
                    sample=_sample(bad, _sample_columns(bad, column)),
                )
            )
    return issues


def _percentage_checks(df: pd.DataFrame, dataset_name: str, columns: list[str]) -> list[DQIssue]:
    return _bounded_checks(
        df,
        dataset_name,
        columns,
        lower=Decimal("0"),
        upper=Decimal("100"),
        check_prefix="percentage_bounds",
    )


def _bounded_checks(
    df: pd.DataFrame,
    dataset_name: str,
    columns: list[str],
    *,
    lower: Decimal,
    upper: Decimal,
    check_prefix: str,
) -> list[DQIssue]:
    issues: list[DQIssue] = []
    for column in columns:
        if column not in df.columns:
            continue
        bad = df[
            df[column].map(
                lambda value: (
                    _present(value)
                    and (
                        (_parse_decimal(value) is not None)
                        and (_parse_decimal(value) < lower or _parse_decimal(value) > upper)
                    )
                )
            )
        ]
        if not bad.empty:
            issues.append(
                DQIssue(
                    check_name=f"{dataset_name}_{check_prefix}_{column}",
                    severity="error",
                    dataset_name=dataset_name,
                    table_name="staging",
                    issue_count=len(bad),
                    sample=_sample(bad, _sample_columns(bad, column)),
                )
            )
    return issues


def _invalid_numeric_checks(
    df: pd.DataFrame,
    dataset_name: str,
    columns: list[str],
) -> list[DQIssue]:
    issues: list[DQIssue] = []
    for column in columns:
        if column not in df.columns:
            continue
        bad = df[df[column].map(lambda value: _present(value) and _parse_decimal(value) is None)]
        if not bad.empty:
            issues.append(
                DQIssue(
                    check_name=f"{dataset_name}_numeric_validity_{column}",
                    severity="error",
                    dataset_name=dataset_name,
                    table_name="staging",
                    issue_count=len(bad),
                    sample=_sample(bad, _sample_columns(bad, column)),
                )
            )
    return issues


def _allowed_value_checks(
    df: pd.DataFrame,
    dataset_name: str,
    allowed_values: dict[str, set[str]],
) -> list[DQIssue]:
    issues: list[DQIssue] = []
    for column, allowed in allowed_values.items():
        if column not in df.columns:
            continue
        bad = df[
            df[column].map(
                lambda value, allowed_values=allowed: (
                    _present(value) and str(value) not in allowed_values
                )
            )
        ]
        if not bad.empty:
            issues.append(
                DQIssue(
                    check_name=f"{dataset_name}_allowed_values_{column}",
                    severity="error",
                    dataset_name=dataset_name,
                    table_name="staging",
                    issue_count=len(bad),
                    sample=_sample(bad, _sample_columns(bad, column)),
                )
            )
    return issues


def _parse_decimal(value: Any) -> Decimal | None:
    if not _present(value):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _duplicate_check(
    df: pd.DataFrame,
    check_name: str,
    dataset_name: str,
    table_name: str,
    columns: list[str],
) -> list[DQIssue]:
    if not all(column in df.columns for column in columns):
        return []
    duplicated = df[df.duplicated(columns, keep=False)]
    if duplicated.empty:
        return []
    return [
        DQIssue(
            check_name=check_name,
            severity="error",
            dataset_name=dataset_name,
            table_name=table_name,
            issue_count=len(duplicated),
            sample=_sample(duplicated, columns),
        )
    ]


def _cgd_total_reconciliation(df: pd.DataFrame) -> list[DQIssue]:
    group_cols = ["source_file_hash", "sheet_name", "report_type", "expense_category"]
    if not all(column in df.columns for column in [*group_cols, "entity_type"]):
        return []
    issues: list[DQIssue] = []
    for group_key, group in df.groupby(group_cols, dropna=False):
        total_rows = group[group["entity_type"] == "total"]
        detail_rows = group[group["entity_type"] != "total"]
        if len(total_rows) != 1 or detail_rows.empty:
            continue
        measure = "disbursement_million_baht"
        if measure not in group.columns:
            continue
        published = total_rows[measure].dropna()
        detail = detail_rows[measure].dropna()
        if len(published) != 1 or detail.empty:
            continue
        published_value = _parse_decimal(published.iloc[0])
        detail_values = [_parse_decimal(value) for value in detail]
        if published_value is None or any(value is None for value in detail_values):
            continue
        detail_value = sum(
            (value for value in detail_values if value is not None),
            Decimal("0"),
        )
        difference = detail_value - published_value
        tolerance = max(Decimal("0.01"), abs(published_value) * Decimal("0.000001"))
        if abs(difference) <= tolerance:
            continue
        issues.append(
            DQIssue(
                check_name="cgd_detail_to_published_total_reconciliation",
                severity="error",
                dataset_name="cgd_budget_execution",
                table_name="staging.cgd_budget_execution",
                issue_count=1,
                sample=(
                    f"sheet={group_key[1]!r}, published={published_value}, "
                    f"detail_sum={detail_value}, difference={difference}"
                ),
            )
        )
    return issues


def _row_count_collapse(
    df: pd.DataFrame,
    dataset_name: str,
    expected_count: int | None,
    threshold: Decimal,
) -> list[DQIssue]:
    if not expected_count or expected_count <= 0:
        return []
    actual = len(df)
    if Decimal(actual) >= Decimal(expected_count) * threshold:
        return []
    return [
        DQIssue(
            check_name=f"{dataset_name}_unexpected_row_count_collapse",
            severity="error",
            dataset_name=dataset_name,
            table_name="staging",
            issue_count=1,
            sample=f"expected_at_least={Decimal(expected_count) * threshold}, actual={actual}",
        )
    ]


def _sample(df: pd.DataFrame, columns: list[str]) -> str:
    available = [column for column in columns if column in df.columns]
    return json.dumps(df[available].head(3).to_dict("records"), ensure_ascii=False, default=str)


def _sample_columns(df: pd.DataFrame, column: str) -> list[str]:
    preferred = ["sheet_name", "row_number", "entity_name", "agency_name", column]
    return [item for item in preferred if item in df.columns]


def _present(value: Any) -> bool:
    if value is None:
        return False
    try:
        return not bool(pd.isna(value))
    except (TypeError, ValueError):
        return True
