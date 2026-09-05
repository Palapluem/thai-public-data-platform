"""Adapters for CSV, nested JSON, HTML tables, tabular JSON and Parquet."""

from __future__ import annotations

import calendar
import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from bs4 import BeautifulSoup

from thai_data_platform.ingestion.metadata import sha256_file
from thai_data_platform.public_sources.models import (
    PUBLIC_INDICATOR_COLUMNS,
    ParsedPublicSource,
    PublicSourceSpec,
)


def load_public_source_specs(
    config_path: str | Path = "config/public_sources.yml",
    *,
    source_ids: set[str] | None = None,
    include_disabled: bool = False,
) -> list[PublicSourceSpec]:
    payload = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    specs = []
    for item in payload.get("sources", []):
        spec = PublicSourceSpec.from_mapping(item)
        if not include_disabled and not spec.enabled:
            continue
        if source_ids and spec.source_id not in source_ids:
            continue
        specs.append(spec)
    if not specs:
        raise ValueError(f"No enabled public sources found in {config_path}")
    return specs


def parse_public_sources(
    config_path: str | Path = "config/public_sources.yml",
    *,
    source_ids: set[str] | None = None,
) -> list[ParsedPublicSource]:
    specs = load_public_source_specs(config_path, source_ids=source_ids)
    return [parse_public_source(spec) for spec in specs]


def parse_public_source(spec: PublicSourceSpec) -> ParsedPublicSource:
    if not spec.path.is_file():
        raise FileNotFoundError(spec.path)
    readers: dict[str, Callable[[PublicSourceSpec], tuple[pd.DataFrame, dict[str, Any]]]] = {
        "mof_budget_csv": _read_mof_budget_csv,
        "mof_budget_monthly_json_api": _read_mof_budget_monthly_json_api,
        "mof_budget_html_table": _read_mof_budget_html_table,
        "nso_tabular_json": _read_nso_tabular_json,
        "canonical_parquet": _read_canonical_parquet,
    }
    try:
        reader = readers[spec.parser]
    except KeyError as exc:
        raise ValueError(f"Unsupported public source parser: {spec.parser}") from exc
    records, metadata = reader(spec)
    records = _normalize_records(records)
    source_updated_at = _parse_datetime(spec.source_updated_at or metadata.get("source_updated_at"))
    return ParsedPublicSource(
        spec=spec,
        records=records,
        content_sha256=sha256_file(spec.path),
        file_size_bytes=spec.path.stat().st_size,
        source_updated_at=source_updated_at,
        metadata=metadata,
    )


def write_canonical_parquet(parsed: ParsedPublicSource, output_path: str | Path) -> Path:
    """Materialize canonical records for a columnar-storage exercise."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame = parsed.records.copy()
    frame["raw_payload"] = frame["raw_payload"].map(
        lambda value: json.dumps(value, ensure_ascii=False, default=str)
    )
    try:
        frame.to_parquet(target, index=False)
    except ImportError as exc:
        raise RuntimeError(
            "Parquet materialization requires the optional pyarrow dependency"
        ) from exc
    return target


def _read_mof_budget_csv(spec: PublicSourceSpec) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.read_csv(spec.path, encoding="utf-8-sig", dtype=object)
    rows: list[dict[str, Any]] = []
    for index, source_row in frame.iterrows():
        fiscal_year_be = _integer(source_row.get("ปีงบประมาณ"))
        if fiscal_year_be is None:
            continue
        fiscal_year = fiscal_year_be - 543
        period_start, period_end = _fiscal_period(fiscal_year)
        ministry_name = _text(source_row.get("ชื่อหน่วยงานกระทรวง"))
        agency_code = _text(source_row.get("รหัสหน่วยงานกรม"))
        agency_name = _text(source_row.get("ชื่อหน่วยงานกรม")) or "Unknown agency"
        base_key = [spec.source_id, agency_code, agency_name, str(fiscal_year_be)]
        rate = _number(source_row.get("เบิกจ่ายไป(%)"))
        source_payload = {
            str(key): _json_value(value) for key, value in source_row.to_dict().items()
        }
        for metric_name, column_name in [
            ("budget_received_million_baht", "ได้รับงบประมาณ(ลบ.)"),
            ("disbursed_million_baht", "เบิกจ่ายไป(ลบ.)"),
        ]:
            value = _number(source_row.get(column_name))
            if value is None:
                continue
            rows.append(
                _record(
                    spec,
                    record_key=_stable_key(*base_key, metric_name),
                    source_record_number=index + 2,
                    period_start=period_start,
                    period_end=period_end,
                    period_grain="fiscal_year",
                    calendar_year=None,
                    calendar_year_be=None,
                    fiscal_year=fiscal_year,
                    fiscal_year_be=fiscal_year_be,
                    entity_type="department",
                    entity_code=agency_code,
                    entity_name=agency_name,
                    geography_type=None,
                    geography_code=None,
                    geography_name=None,
                    category=ministry_name or "Unknown ministry",
                    subcategory="budget_execution",
                    metric_name=metric_name,
                    metric_unit="million_baht",
                    value=value,
                    reference_metric="disbursement_rate_percent",
                    reference_value=rate,
                    raw_payload=source_payload,
                )
            )
    return pd.DataFrame(rows), {"input_columns": list(frame.columns)}


def _read_mof_budget_monthly_json_api(
    spec: PublicSourceSpec,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    payload = json.loads(spec.path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    record_number = 0
    for ministry in payload.get("data", []):
        ministry_name = _text(ministry.get("name")) or "Unknown ministry"
        for item in ministry.get("items", []):
            year = _integer(item.get("year"))
            month = _integer(item.get("month"))
            value = _number(item.get("expd"))
            if year is None or month is None or value is None:
                continue
            record_number += 1
            period_start, period_end = _month_period(year, month)
            fiscal_year = year + 1 if month >= 10 else year
            rows.append(
                _record(
                    spec,
                    record_key=_stable_key(spec.source_id, ministry_name, year, month, "monthly"),
                    source_record_number=record_number,
                    period_start=period_start,
                    period_end=period_end,
                    period_grain="month",
                    calendar_year=year,
                    calendar_year_be=year + 543,
                    fiscal_year=fiscal_year,
                    fiscal_year_be=fiscal_year + 543,
                    entity_type="ministry",
                    entity_code=None,
                    entity_name=ministry_name,
                    geography_type=None,
                    geography_code=None,
                    geography_name=None,
                    category="government_expenditure",
                    subcategory="ministry",
                    metric_name="monthly_expenditure_million_baht",
                    metric_unit="million_baht",
                    value=value,
                    reference_metric="annual_budget_million_baht",
                    reference_value=_number(ministry.get("budget")),
                    raw_payload={"ministry": ministry_name, "item": item},
                )
            )
    data_date = payload.get("data_date") or {}
    return pd.DataFrame(rows), {
        "api_data_date": data_date,
        "source_updated_at": data_date.get("data_update") if isinstance(data_date, dict) else None,
        "category_list": payload.get("category_list"),
    }


def _read_mof_budget_html_table(spec: PublicSourceSpec) -> tuple[pd.DataFrame, dict[str, Any]]:
    soup = BeautifulSoup(spec.path.read_text(encoding="utf-8"), "html.parser")
    target = None
    for table in soup.find_all("table"):
        first_row = [cell.get_text(" ", strip=True) for cell in table.find_all("tr")[:1]]
        header_text = " | ".join(first_row)
        if all(token in header_text for token in ["Item Name", "Budget", "Total"]):
            target = table
            break
    if target is None:
        raise ValueError("Could not find the Ministry of Finance summary table in HTML")

    rows: list[dict[str, Any]] = []
    table_rows = target.find_all("tr")
    section = "current_budget"
    for index, table_row in enumerate(table_rows[1:], start=2):
        cells = [cell.get_text(" ", strip=True) for cell in table_row.find_all(["th", "td"])]
        if len(cells) < 3 or not cells[0]:
            continue
        name = cells[0]
        budget = _number(cells[1])
        total = _number(cells[2])
        if total is None:
            continue
        if name.casefold() == "capital budgets":
            section = "capital_budget"
        is_summary = name.casefold() in {"current budget", "capital budgets"}
        rows.append(
            _record(
                spec,
                record_key=_stable_key(spec.source_id, section, name, "total"),
                source_record_number=index,
                period_start=date(2025, 10, 1),
                period_end=_source_date(spec) or date(2026, 7, 20),
                period_grain="release_to_date",
                calendar_year=2026,
                calendar_year_be=2569,
                fiscal_year=2026,
                fiscal_year_be=2569,
                entity_type="summary" if is_summary else "ministry",
                entity_code=None,
                entity_name=name,
                geography_type=None,
                geography_code=None,
                geography_name=None,
                category=section,
                subcategory="validation_only",
                metric_name="reported_total_million_baht",
                metric_unit="million_baht",
                value=total,
                reference_metric="budget_million_baht",
                reference_value=budget,
                raw_payload={"columns": cells[: len(cells)], "source_row": index},
            )
        )
    return pd.DataFrame(rows), {"table_name": "budget_summary", "source_role": "validation"}


def _read_nso_tabular_json(spec: PublicSourceSpec) -> tuple[pd.DataFrame, dict[str, Any]]:
    payload = json.loads(spec.path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("data", [])
    rows: list[dict[str, Any]] = []
    for index, source_row in enumerate(payload, start=1):
        year_be = _integer(source_row.get("YEAR"))
        quarter_text = _text(source_row.get("QUARTER")) or ""
        quarter_match = re.search(r"(\d+)", quarter_text)
        quarter = int(quarter_match.group(1)) if quarter_match else None
        value = _number(source_row.get("VALUE"))
        region = _text(source_row.get("REGION")) or "Unknown region"
        sex = _text(source_row.get("SEX")) or "Unknown"
        if year_be is None or quarter not in {1, 2, 3, 4} or value is None:
            continue
        period_start, period_end = _quarter_period(year_be - 543, quarter)
        rows.append(
            _record(
                spec,
                record_key=_stable_key(spec.source_id, year_be, quarter, region, sex),
                source_record_number=index,
                period_start=period_start,
                period_end=period_end,
                period_grain="quarter",
                calendar_year=year_be - 543,
                calendar_year_be=year_be,
                fiscal_year=None,
                fiscal_year_be=None,
                entity_type="region",
                entity_code=None,
                entity_name=region,
                geography_type="region",
                geography_code=None,
                geography_name=region,
                category="labour_force",
                subcategory=sex,
                metric_name="labour_force_thousand_persons",
                metric_unit="thousand_persons",
                value=value,
                reference_metric=None,
                reference_value=None,
                raw_payload={str(key): _json_value(item) for key, item in source_row.items()},
            )
        )
    return pd.DataFrame(rows), {"columns": list(payload[0]) if payload else []}


def _read_canonical_parquet(spec: PublicSourceSpec) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.read_parquet(spec.path)
    if "raw_payload" in frame.columns:
        frame["raw_payload"] = frame["raw_payload"].map(
            lambda value: json.loads(value) if isinstance(value, str) else value
        )
    frame["source_id"] = spec.source_id
    frame["source_format"] = spec.format
    frame["source_role"] = spec.source_role
    frame["source_url"] = spec.file_url or spec.source_page_url
    return frame, {"derived_from": "canonical parquet"}


def _record(spec: PublicSourceSpec, **values: Any) -> dict[str, Any]:
    return {
        "source_id": spec.source_id,
        "source_format": spec.format,
        "source_role": spec.source_role,
        "source_url": spec.file_url or spec.source_page_url,
        **values,
    }


def _normalize_records(frame: pd.DataFrame) -> pd.DataFrame:
    for column in PUBLIC_INDICATOR_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    frame = frame[PUBLIC_INDICATOR_COLUMNS].copy()
    if frame.empty:
        return frame
    for column in ["period_start", "period_end"]:
        frame[column] = frame[column].map(_date_value)
    for column in [
        "source_record_number",
        "calendar_year",
        "calendar_year_be",
        "fiscal_year",
        "fiscal_year_be",
    ]:
        frame[column] = frame[column].map(_integer)
    for column in ["value", "reference_value"]:
        frame[column] = frame[column].map(_number)
    frame["raw_payload"] = frame["raw_payload"].map(
        lambda value: value if isinstance(value, dict) else {"value": _json_value(value)}
    )
    return frame


def _stable_key(*parts: Any) -> str:
    material = "|".join("" if part is None else str(part).strip() for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _number(value: Any) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "–", "—", "nan", "None"}:
        return None
    text = text.replace("%", "")
    try:
        return Decimal(text)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _json_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _date_value(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=parsed.tzinfo or UTC)


def _source_date(spec: PublicSourceSpec) -> date | None:
    parsed = _parse_datetime(spec.source_updated_at)
    return parsed.date() if parsed else None


def _fiscal_period(fiscal_year: int) -> tuple[date, date]:
    return date(fiscal_year - 1, 10, 1), date(fiscal_year, 9, 30)


def _month_period(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _quarter_period(year: int, quarter: int) -> tuple[date, date]:
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    return date(year, start_month, 1), date(
        year,
        end_month,
        calendar.monthrange(year, end_month)[1],
    )
