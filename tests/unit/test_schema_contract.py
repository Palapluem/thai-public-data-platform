from pathlib import Path

import pandas as pd
import pytest

from thai_data_platform.quality.schema_contract import (
    SchemaContractError,
    validate_extract_contracts,
)
from thai_data_platform.transform.cgd import CGD_COLUMNS, CgdExtract
from thai_data_platform.transform.ocsc import OcscExtract

CONTRACT_PATH = Path("config/schema_contracts.json")


def _extracts(cgd_columns=None, *, extra_ocsc_column=False):
    cgd_columns = cgd_columns or CGD_COLUMNS
    ocsc_columns = [
        "ingestion_run_id",
        "dataset_name",
        "source_file_hash",
        "sheet_index",
        "sheet_name",
        "row_number",
        "fiscal_year",
        "fiscal_year_be",
        "entity_type",
        "ministry_name",
        "agency_name",
        "metric_name",
        "metric_group",
        "headcount",
        "percentage",
        "source_value",
        "source_unit",
    ]
    if extra_ocsc_column:
        ocsc_columns.append("new_optional_measure")
    return CgdExtract(
        budget_execution=pd.DataFrame(columns=cgd_columns),
        raw_cells=pd.DataFrame(),
        workbook_sheets=pd.DataFrame(),
        as_of_date=None,
    ), OcscExtract(
        workforce_agency=pd.DataFrame(columns=ocsc_columns),
        workforce_profile=pd.DataFrame(columns=ocsc_columns),
        raw_cells=pd.DataFrame(),
        workbook_sheets=pd.DataFrame(),
    )


def test_schema_contract_accepts_current_extract_shapes():
    cgd, ocsc = _extracts()

    report = validate_extract_contracts(cgd, ocsc, CONTRACT_PATH)

    assert report.contract_version == "1.0.0"
    assert report.checked_extracts == 3
    assert report.warnings == ()


def test_schema_contract_allows_additive_columns_as_warning():
    cgd, ocsc = _extracts(extra_ocsc_column=True)

    report = validate_extract_contracts(cgd, ocsc, CONTRACT_PATH)

    assert any("new_optional_measure" in warning for warning in report.warnings)


def test_schema_contract_blocks_missing_columns_before_staging():
    cgd, ocsc = _extracts(cgd_columns=[column for column in CGD_COLUMNS if column != "report_type"])

    with pytest.raises(SchemaContractError, match="missing columns=report_type"):
        validate_extract_contracts(cgd, ocsc, CONTRACT_PATH)
