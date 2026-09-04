from datetime import date
from decimal import Decimal

from thai_data_platform.transform.clean import (
    canonical_entity_name,
    normalize_header,
    normalize_text,
    parse_thai_date,
    to_decimal,
)


def test_cleaning_preserves_thai_text_and_normalizes_numbers():
    assert normalize_text("  กรม\n  ตัวอย่าง  ") == "กรม ตัวอย่าง"
    assert canonical_entity_name("12. กรมตัวอย่าง") == "กรมตัวอย่าง"
    assert normalize_header("วงเงินงบประมาณ หลังโอนเปลี่ยนแปลง") == "budget_after_transfer"
    assert to_decimal("๑,๒๓๔.๕๐") == Decimal("1234.50")
    assert to_decimal("(10.25)") == Decimal("-10.25")


def test_thai_be_date_is_normalized_to_ce():
    assert parse_thai_date("ข้อมูล ณ วันที่ 3 กรกฎาคม 2569") == date(2026, 7, 3)
    assert parse_thai_date("03/07/2569") == date(2026, 7, 3)
