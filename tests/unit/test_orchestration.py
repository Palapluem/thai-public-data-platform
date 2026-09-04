from decimal import Decimal

import pandas as pd

from thai_data_platform.orchestration import (
    _frame_payload,
    _restore_frame,
    _stage_from_payload,
    _stage_payload,
)
from thai_data_platform.warehouse.postgres import StageResult


def test_extract_handoff_roundtrip_keeps_decimal_values():
    frame = pd.DataFrame(
        [{"amount": Decimal("10.25"), "sheet_index": 1, "row_number": 4}]
    )

    restored = _restore_frame(_frame_payload(frame), "cgd")

    assert restored.loc[0, "amount"] == Decimal("10.25")
    assert restored.loc[0, "sheet_index"] == 1


def test_extract_handoff_roundtrip_converts_json_nan_to_null():
    frame = pd.DataFrame(
        [{"headcount": None, "percentage": None, "sheet_index": 1, "row_number": 4}]
    )

    restored = _restore_frame(_frame_payload(frame), "ocsc")

    assert restored.loc[0, "headcount"] is None
    assert restored.loc[0, "percentage"] is None


def test_stage_result_roundtrip_is_json_safe():
    result = StageResult(
        source_file_ids={"a" * 64: "source-1"},
        workbook_sheet_ids={("a" * 64, 1): 10},
        raw_cell_count=20,
        cgd_row_count=2,
        ocsc_row_count=3,
    )

    restored = _stage_from_payload(_stage_payload(result))

    assert restored == result
