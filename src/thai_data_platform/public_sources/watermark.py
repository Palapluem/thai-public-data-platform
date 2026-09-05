"""Watermark decisions for reproducible incremental and backfill behavior."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class WatermarkDecision:
    previous: date | None
    candidate: date | None
    selected: date | None
    status: str
    is_new_release: bool


def decide_watermark(
    previous: date | None,
    candidate: date | None,
    *,
    is_new_release: bool,
) -> WatermarkDecision:
    """Classify a release without ever moving a watermark backwards.

    A new release with an equal or older maximum period is still processed as
    ``backfill`` because it may contain corrections to already-seen periods.
    """
    if not is_new_release:
        return WatermarkDecision(previous, candidate, previous, "unchanged", False)
    if previous is None and candidate is not None:
        return WatermarkDecision(None, candidate, candidate, "advanced", True)
    if candidate is not None and (previous is None or candidate > previous):
        return WatermarkDecision(previous, candidate, candidate, "advanced", True)
    if candidate is None:
        return WatermarkDecision(previous, None, previous, "backfill", True)
    return WatermarkDecision(previous, candidate, previous, "backfill", True)


def select_incremental_records(
    records: pd.DataFrame,
    decision: WatermarkDecision,
    *,
    run_type: str = "scheduled",
    watermark_field: str = "period_end",
) -> pd.DataFrame:
    """Select new periods while retaining corrections and explicit backfills.

    ``backfill`` and ``replay`` deliberately load the complete release. A
    scheduled release with a later watermark loads only later periods. A new
    release whose watermark does not advance is treated as a correction and
    loads all rows so the caller can reconcile it explicitly.
    """
    if records.empty or not decision.is_new_release:
        return records.iloc[0:0].copy()
    if run_type in {"backfill", "replay"} or decision.status == "backfill":
        return records.copy()
    if decision.previous is None or watermark_field not in records.columns:
        return records.copy()
    mask = records[watermark_field].map(
        lambda value: value is not None and value > decision.previous
    )
    return records.loc[mask].copy()


def json_safe_watermark(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
