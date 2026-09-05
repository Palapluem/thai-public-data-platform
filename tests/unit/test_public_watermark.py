from datetime import date

import pandas as pd

from thai_data_platform.public_sources.watermark import (
    decide_watermark,
    select_incremental_records,
)


def test_watermark_advances_only_for_a_newer_release():
    decision = decide_watermark(
        date(2026, 3, 31),
        date(2026, 6, 30),
        is_new_release=True,
    )
    assert decision.status == "advanced"
    assert decision.selected == date(2026, 6, 30)

    frame = pd.DataFrame(
        {"record_key": ["old", "new"], "period_end": [date(2026, 3, 31), date(2026, 6, 30)]}
    )
    selected = select_incremental_records(frame, decision)
    assert selected["record_key"].tolist() == ["new"]


def test_same_or_older_new_release_is_a_correction_backfill_and_does_not_move_back():
    decision = decide_watermark(
        date(2026, 6, 30),
        date(2026, 3, 31),
        is_new_release=True,
    )
    assert decision.status == "backfill"
    assert decision.selected == date(2026, 6, 30)

    frame = pd.DataFrame(
        {"record_key": ["corrected-old"], "period_end": [date(2026, 3, 31)]}
    )
    assert len(select_incremental_records(frame, decision)) == 1


def test_same_content_release_is_not_staged_again():
    decision = decide_watermark(
        date(2026, 6, 30),
        date(2026, 6, 30),
        is_new_release=False,
    )
    assert decision.status == "unchanged"
    assert not select_incremental_records(
        pd.DataFrame({"period_end": [date(2026, 6, 30)]}),
        decision,
    ).any().any()
