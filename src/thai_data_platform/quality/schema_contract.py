"""Versioned contracts for parser output before it reaches the warehouse."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from thai_data_platform.transform.cgd import CgdExtract
from thai_data_platform.transform.ocsc import OcscExtract

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchemaContractReport:
    """Evidence returned when all required extract columns are present."""

    contract_version: str
    checked_extracts: int
    warnings: tuple[str, ...] = ()


class SchemaContractError(ValueError):
    """Raised when a breaking parser-output change would reach the warehouse."""

    def __init__(self, contract_version: str, violations: list[str]) -> None:
        self.contract_version = contract_version
        self.violations = tuple(violations)
        detail = "; ".join(violations)
        super().__init__(
            f"Schema contract {contract_version} blocked publication: {detail}"
        )


def validate_extract_contracts(
    cgd_extract: CgdExtract,
    ocsc_extract: OcscExtract,
    contract_path: str | Path = "config/schema_contracts.json",
) -> SchemaContractReport:
    """Validate typed parser outputs before raw/staging persistence.

    Missing required columns are breaking changes and fail closed. Additive
    columns are logged as non-breaking warnings so a forward-compatible parser
    can evolve without silently accepting a malformed handoff.
    """
    payload = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    contract_version = str(payload.get("contract_version", "unknown"))
    datasets = payload.get("datasets")
    if not isinstance(datasets, dict):
        raise SchemaContractError(contract_version, ["contract has no datasets mapping"])

    extracts: dict[tuple[str, str], pd.DataFrame] = {
        ("cgd_budget_execution", "budget_execution"): cgd_extract.budget_execution,
        ("ocsc_government_manpower", "workforce_agency"): ocsc_extract.workforce_agency,
        ("ocsc_government_manpower", "workforce_profile"): ocsc_extract.workforce_profile,
    }
    violations: list[str] = []
    warnings: list[str] = []

    for (dataset_name, extract_name), frame in extracts.items():
        dataset_contract = datasets.get(dataset_name, {})
        extract_contract = dataset_contract.get("extracts", {}).get(extract_name)
        if not isinstance(extract_contract, dict):
            violations.append(f"{dataset_name}.{extract_name} has no contract definition")
            continue

        required = {str(column) for column in extract_contract.get("required_columns", [])}
        actual = {str(column) for column in frame.columns}
        missing = sorted(required - actual)
        if missing:
            violations.append(
                f"{dataset_name}.{extract_name} missing columns={','.join(missing)}"
            )

        extra = sorted(actual - required)
        if extra and extract_contract.get("allow_additional_columns", True):
            warnings.append(
                f"{dataset_name}.{extract_name} additive columns={','.join(extra)}"
            )
        elif extra:
            violations.append(
                f"{dataset_name}.{extract_name} unexpected columns={','.join(extra)}"
            )

    if violations:
        raise SchemaContractError(contract_version, violations)
    for warning in warnings:
        LOGGER.warning("Schema contract warning: %s", warning)
    return SchemaContractReport(
        contract_version=contract_version,
        checked_extracts=len(extracts),
        warnings=tuple(warnings),
    )
