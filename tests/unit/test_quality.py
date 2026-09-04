import pandas as pd

from thai_data_platform.quality.checks import run_data_quality_checks
from thai_data_platform.quality.gate import evaluate_quality_gate

SOURCE_HASH = "a" * 64


def _cgd_rows():
    return pd.DataFrame(
        [
            {
                "source_file_hash": SOURCE_HASH,
                "sheet_index": 1,
                "sheet_name": "หน่วยงาน",
                "row_number": 6,
                "report_type": "disbursement",
                "entity_type": "agency",
                "entity_name": "กรมตัวอย่าง",
                "entity_code": "A001",
                "expense_category": "total",
                "budget_after_transfer_million_baht": 100,
                "disbursement_million_baht": 30,
                "disbursement_pct": 30,
                "monthly_target_gap_pct": -20,
            }
        ]
    )


def _ocsc_rows():
    return pd.DataFrame(
        [
            {
                "source_file_hash": SOURCE_HASH,
                "sheet_index": 1,
                "sheet_name": "หน่วยงาน",
                "row_number": 6,
                "entity_type": "agency",
                "agency_name": "กรมตัวอย่าง",
                "metric_name": "civil_servant",
                "metric_group": "employment_type",
                "source_unit": "person",
                "headcount": 25,
                "percentage": None,
            }
        ]
    )


def test_quality_gate_passes_valid_rows_and_signed_gap():
    issues = run_data_quality_checks(
        _cgd_rows(),
        _ocsc_rows(),
        "run-1",
        source_hashes=[SOURCE_HASH],
    )
    gate = evaluate_quality_gate(issues)
    assert gate.passed
    assert gate.blocking_issue_count == 0
    assert issues.iloc[0]["status"] == "passed"


def test_quality_gate_blocks_invalid_values_and_duplicate_grain():
    cgd = pd.concat([_cgd_rows(), _cgd_rows()], ignore_index=True)
    cgd.loc[0, "budget_after_transfer_million_baht"] = -1
    cgd.loc[0, "disbursement_pct"] = 120
    ocsc = _ocsc_rows()
    ocsc.loc[0, "headcount"] = -2

    issues = run_data_quality_checks(cgd, ocsc, "run-1", source_hashes=[SOURCE_HASH])
    gate = evaluate_quality_gate(issues)
    checks = set(issues.loc[issues["status"].eq("failed"), "check_name"])

    assert not gate.passed
    assert "cgd_duplicate_natural_grain" in checks
    assert "cgd_budget_execution_non_negative_budget_after_transfer_million_baht" in checks
    assert "cgd_budget_execution_percentage_bounds_disbursement_pct" in checks
    assert "ocsc_government_manpower_non_negative_headcount" in checks


def test_quality_gate_blocks_empty_extraction():
    issues = run_data_quality_checks(pd.DataFrame(), pd.DataFrame(), "run-1")
    gate = evaluate_quality_gate(issues)
    assert not gate.passed
    assert {"cgd_zero_row_extraction", "ocsc_zero_row_extraction"}.issubset(
        set(issues["check_name"])
    )
