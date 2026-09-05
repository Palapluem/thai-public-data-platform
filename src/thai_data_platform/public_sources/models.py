"""Data contracts for the multi-format public-indicator pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

PUBLIC_INDICATOR_COLUMNS = [
    "source_id",
    "source_format",
    "source_role",
    "record_key",
    "source_record_number",
    "period_start",
    "period_end",
    "period_grain",
    "calendar_year",
    "calendar_year_be",
    "fiscal_year",
    "fiscal_year_be",
    "entity_type",
    "entity_code",
    "entity_name",
    "geography_type",
    "geography_code",
    "geography_name",
    "category",
    "subcategory",
    "metric_name",
    "metric_unit",
    "value",
    "reference_metric",
    "reference_value",
    "source_url",
    "raw_payload",
]


@dataclass(frozen=True)
class PublicSourceSpec:
    source_id: str
    dataset_name: str
    source_name: str
    source_page_url: str
    file_url: str | None
    path: Path
    format: str
    parser: str
    source_role: str
    source_updated_at: str | None = None
    watermark_field: str = "period_end"
    watermark_strategy: str = "max"
    expected_min_rows: int | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, item: dict[str, Any]) -> PublicSourceSpec:
        path = Path(str(item["path"]))
        known = {
            "source_id",
            "dataset_name",
            "source_name",
            "source_page_url",
            "file_url",
            "path",
            "format",
            "parser",
            "source_role",
            "source_updated_at",
            "watermark_field",
            "watermark_strategy",
            "expected_min_rows",
            "enabled",
        }
        return cls(
            source_id=str(item["source_id"]),
            dataset_name=str(item["dataset_name"]),
            source_name=str(item["source_name"]),
            source_page_url=str(item["source_page_url"]),
            file_url=str(item["file_url"]) if item.get("file_url") else None,
            path=path,
            format=str(item["format"]),
            parser=str(item["parser"]),
            source_role=str(item["source_role"]),
            source_updated_at=(
                str(item["source_updated_at"]) if item.get("source_updated_at") else None
            ),
            watermark_field=str(item.get("watermark_field", "period_end")),
            watermark_strategy=str(item.get("watermark_strategy", "max")),
            expected_min_rows=(
                int(item["expected_min_rows"]) if item.get("expected_min_rows") else None
            ),
            enabled=bool(item.get("enabled", True)),
            metadata={key: value for key, value in item.items() if key not in known},
        )


@dataclass(frozen=True)
class ParsedPublicSource:
    spec: PublicSourceSpec
    records: pd.DataFrame
    content_sha256: str
    file_size_bytes: int
    source_updated_at: datetime | None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def watermark(self) -> date | None:
        if self.records.empty or "period_end" not in self.records:
            return None
        values = [value for value in self.records["period_end"].tolist() if value is not None]
        return max(values) if values else None

    def as_summary(self) -> dict[str, Any]:
        return {
            "source_id": self.spec.source_id,
            "dataset_name": self.spec.dataset_name,
            "format": self.spec.format,
            "parser": self.spec.parser,
            "source_role": self.spec.source_role,
            "sha256": self.content_sha256,
            "file_size_bytes": self.file_size_bytes,
            "record_count": len(self.records),
            "watermark": self.watermark.isoformat() if self.watermark else None,
            "source_updated_at": (
                self.source_updated_at.isoformat() if self.source_updated_at else None
            ),
            "metadata": self.metadata,
        }
