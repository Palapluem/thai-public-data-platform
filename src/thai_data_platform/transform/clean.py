"""Shared normalization rules for Thai public-data workbooks."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

THAI_MONTHS = {
    "มกราคม": 1,
    "ม.ค.": 1,
    "กุมภาพันธ์": 2,
    "ก.พ.": 2,
    "มีนาคม": 3,
    "มี.ค.": 3,
    "เมษายน": 4,
    "เม.ย.": 4,
    "พฤษภาคม": 5,
    "พ.ค.": 5,
    "มิถุนายน": 6,
    "มิ.ย.": 6,
    "กรกฎาคม": 7,
    "ก.ค.": 7,
    "สิงหาคม": 8,
    "ส.ค.": 8,
    "กันยายน": 9,
    "ก.ย.": 9,
    "ตุลาคม": 10,
    "ต.ค.": 10,
    "พฤศจิกายน": 11,
    "พ.ย.": 11,
    "ธันวาคม": 12,
    "ธ.ค.": 12,
}

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def normalize_text(value: Any) -> str:
    """Return a whitespace-normalized string without changing Thai content."""
    if value is None:
        return ""
    text = str(value).translate(THAI_DIGITS).replace("\n", " ").replace("\r", " ")
    text = text.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_header(value: Any) -> str:
    """Map source header variants to stable snake_case names."""
    text = normalize_text(value).lower()
    text = text.replace("%", "percent")
    text = re.sub(r"[()/+.,:;]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        "วงเงิน งบประมาณ หลังโอน เปลี่ยนแปลง": "budget_after_transfer",
        "วงเงินงบประมาณ หลังโอนเปลี่ยนแปลง": "budget_after_transfer",
        "วงเงินงบประมาณหลังโอนเปลี่ยนแปลง": "budget_after_transfer",
        "po สำรอง เงินมีหนี้": "po_reserved_debt",
        "po สำรองเงิน มีหนี้": "po_reserved_debt",
        "po สำรอง เงิน มีหนี้": "po_reserved_debt",
        "po": "po_reserved_debt",
        "จัดสรร": "allocated",
        "แผนการ ใช้จ่าย": "planned_expenditure",
        "แผนการใช้จ่าย": "planned_expenditure",
        "เบิกจ่าย": "disbursement",
        "การใช้จ่าย": "expenditure",
        "สูง ต่ำกว่า เป้าหมายการ ใช้จ่าย รายเดือน": "monthly_target_gap",
        "สูง ต่ำกว่า เป้าหมายการใช้จ่าย รายเดือน": "monthly_target_gap",
        "ร้อยละ": "pct",
        "คงเหลือยังไม่เบิกจ่าย": "remaining_not_disbursed",
        "ลำดับ ที่": "rank",
        "ลำดับ": "rank",
        "หน่วยงาน": "agency_name",
        "กระทรวง": "ministry_name",
        "จังหวัด": "province_name",
        "รายการ": "item_name",
        "รหัสกรมจังหวัด": "entity_code",
        "รหัสกรม": "entity_code",
    }
    return replacements.get(text, slugify(text))


def slugify(text: str) -> str:
    text = normalize_text(text).lower()
    text = text.replace("%", "pct")
    text = re.sub(r"[^\wก-๙]+", "_", text, flags=re.UNICODE)
    return re.sub(r"_+", "_", text).strip("_")


def canonical_entity_name(value: Any) -> str:
    """Remove report ordering prefixes while preserving the source label."""
    text = normalize_text(value)
    text = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", text)
    return normalize_text(text)


def to_decimal(value: Any) -> Decimal | None:
    """Parse report numbers exactly enough for PostgreSQL NUMERIC columns."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    text = normalize_text(value)
    if not text or text in {"-", "–", "—", "#REF!", "#DIV/0!", "#VALUE!", "N/A"}:
        return None
    text = text.replace(",", "").replace("%", "")
    is_parenthesized_negative = text.startswith("(") and text.endswith(")")
    if is_parenthesized_negative:
        text = text[1:-1].strip()
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return -number if is_parenthesized_negative else number


def to_number(value: Any) -> Decimal | None:
    """Compatibility name for parser code that expects a numeric conversion."""
    return to_decimal(value)


def to_int(value: Any) -> int | None:
    number = to_decimal(value)
    return int(number.quantize(Decimal("1"))) if number is not None else None


def thai_be_year_to_ce(year: int) -> int:
    return year - 543 if year >= 2400 else year


def parse_thai_date(text: str) -> date | None:
    value = normalize_text(text)
    match = re.search(r"(\d{1,2})\s*([ก-๙.]+)\s*(\d{4})", value)
    if match:
        day = int(match.group(1))
        month = THAI_MONTHS.get(match.group(2))
        if month is not None:
            try:
                return date(thai_be_year_to_ce(int(match.group(3))), month, day)
            except ValueError:
                return None
    numeric_match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", value)
    if numeric_match:
        day, month, year = (int(part) for part in numeric_match.groups())
        try:
            return date(thai_be_year_to_ce(year), month, day)
        except ValueError:
            return None
    return None


def extract_first_thai_date(text: str) -> date | None:
    return parse_thai_date(text)


def is_total_label(value: Any) -> bool:
    text = canonical_entity_name(value)
    return text in {"รวม", "รวมทั้งสิ้น", "รวมทั้งหมด", "ร้อยละ"} or text.startswith("รวม")


def fiscal_year_from_filename(filename: str) -> tuple[int | None, int | None]:
    match = re.search(r"(25\d{2}|20\d{2})", filename)
    if not match:
        return None, None
    raw = int(match.group(1))
    if raw >= 2500:
        return thai_be_year_to_ce(raw), raw
    return raw, raw + 543
