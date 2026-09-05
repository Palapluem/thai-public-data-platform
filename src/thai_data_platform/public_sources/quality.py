"""Quality checks specific to the canonical multi-format indicator model."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from thai_data_platform.public_sources.models import PUBLIC_INDICATOR_COLUMNS, ParsedPublicSource


def run_public_quality_checks(
    sources: list[ParsedPublicSource],
    run_id: str,
) -> pd.DataFrame:
    issues: list[dict[str, Any]] = []
    for source in sources:
        frame = source.records
        dataset = source.spec.dataset_name
        table = "staging.public_indicator"
        if frame.empty:
            issues.append(
                _issue("zero_row_extraction", dataset, table, 1, "No canonical rows parsed.")
            )
            continue
        missing = [column for column in PUBLIC_INDICATOR_COLUMNS if column not in frame.columns]
        if missing:
            issues.append(
                _issue(
                    "required_columns",
                    dataset,
                    table,
                    len(missing),
                    json.dumps({"missing_columns": missing}),
                )
            )
            continue
        required = ["record_key", "source_id", "source_role", "entity_name", "metric_name"]
        missing_mask = frame[required].isna().any(axis=1)
        for column in required:
            missing_mask |= frame[column].map(
                lambda value: isinstance(value, str) and not value.strip()
            )
        if missing_mask.any():
            issues.append(
                _issue(
                    "required_keys",
                    dataset,
                    table,
                    int(missing_mask.sum()),
                    _sample(frame.loc[missing_mask], required),
                )
            )
        duplicate_mask = frame.duplicated(subset=["record_key", "metric_name"], keep=False)
        if duplicate_mask.any():
            issues.append(
                _issue(
                    "duplicate_natural_grain",
                    dataset,
                    table,
                    int(duplicate_mask.sum()),
                    _sample(frame.loc[duplicate_mask], ["record_key", "metric_name"]),
                )
            )
        invalid_value = frame["value"].map(lambda value: value is None or pd.isna(value))
        if invalid_value.any():
            issues.append(
                _issue(
                    "value_required",
                    dataset,
                    table,
                    int(invalid_value.sum()),
                    _sample(frame.loc[invalid_value], ["record_key", "metric_name"]),
                )
            )
        negative = frame["value"].map(
            lambda value: value is not None and not pd.isna(value) and value < 0
        )
        if negative.any():
            issues.append(
                _issue(
                    "non_negative_value",
                    dataset,
                    table,
                    int(negative.sum()),
                    _sample(frame.loc[negative], ["record_key", "value"]),
                )
            )
        bad_period = frame.apply(
            lambda row: row["period_start"] is None
            or row["period_end"] is None
            or row["period_start"] > row["period_end"],
            axis=1,
        )
        if bad_period.any():
            issues.append(
                _issue(
                    "period_validity",
                    dataset,
                    table,
                    int(bad_period.sum()),
                    _sample(frame.loc[bad_period], ["record_key", "period_start", "period_end"]),
                )
            )
        if source.spec.expected_min_rows and len(frame) < source.spec.expected_min_rows:
            issues.append(
                _issue(
                    "row_count_minimum",
                    dataset,
                    table,
                    1,
                    json.dumps(
                        {"actual": len(frame), "expected_minimum": source.spec.expected_min_rows}
                    ),
                )
            )

    if not issues:
        issues.append(
            {
                "ingestion_run_id": run_id,
                "check_name": "all_public_source_checks",
                "severity": "info",
                "dataset_name": "all_public_sources",
                "table_name": "staging.public_indicator",
                "issue_count": 0,
                "sample": "All public-source canonical checks passed.",
                "blocking": False,
                "status": "passed",
            }
        )
    else:
        for issue in issues:
            issue["ingestion_run_id"] = run_id
    return pd.DataFrame(issues)


def _issue(check_name: str, dataset: str, table: str, count: int, sample: str) -> dict[str, Any]:
    return {
        "ingestion_run_id": None,
        "check_name": f"public_{dataset}_{check_name}",
        "severity": "error",
        "dataset_name": dataset,
        "table_name": table,
        "issue_count": count,
        "sample": sample,
        "blocking": True,
        "status": "failed",
    }


def _sample(frame: pd.DataFrame, columns: list[str]) -> str:
    return json.dumps(
        frame[columns].head(3).to_dict(orient="records"),
        ensure_ascii=False,
        default=str,
    )
