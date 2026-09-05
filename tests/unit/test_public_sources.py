import json
from dataclasses import replace
from datetime import date

from thai_data_platform.public_sources.models import PUBLIC_INDICATOR_COLUMNS, PublicSourceSpec
from thai_data_platform.public_sources.quality import run_public_quality_checks
from thai_data_platform.public_sources.readers import (
    parse_public_source,
    parse_public_sources,
    write_canonical_parquet,
)


def test_registered_public_sources_cover_multiple_wire_formats_and_pass_quality_gate():
    sources = parse_public_sources("config/public_sources.yml")

    assert {source.spec.format for source in sources} == {"csv", "json", "html"}
    assert {source.spec.parser for source in sources} == {
        "mof_budget_csv",
        "mof_budget_monthly_json_api",
        "mof_budget_html_table",
        "nso_tabular_json",
    }
    assert {source.spec.source_role for source in sources} == {"authoritative", "validation"}
    assert {source.spec.source_id for source in sources} == {
        "mof_budget_summary_csv_2568",
        "mof_budget_monthly_json_api_2026",
        "mof_budget_summary_html_2026",
        "nso_labour_region_sex_json_2569",
    }

    issues = run_public_quality_checks(sources, "unit-run")

    assert issues.iloc[0]["status"] == "passed"
    assert issues.iloc[0]["ingestion_run_id"] == "unit-run"
    assert all(source.records["record_key"].notna().all() for source in sources)
    assert all(source.records["source_url"].str.startswith("http").all() for source in sources)


def test_public_parsers_normalize_periods_and_keep_repeated_reference_values_explicitly():
    sources = {source.spec.source_id: source for source in parse_public_sources()}

    csv = sources["mof_budget_summary_csv_2568"].records
    assert set(csv["metric_name"]) == {
        "budget_received_million_baht",
        "disbursed_million_baht",
    }
    assert csv.iloc[0]["period_start"] == date(2024, 10, 1)
    assert csv.iloc[0]["period_end"] == date(2025, 9, 30)
    assert set(csv["fiscal_year_be"]) == {2568}

    monthly = sources["mof_budget_monthly_json_api_2026"].records
    assert set(monthly["period_grain"]) == {"month"}
    assert set(monthly["reference_metric"]) == {"annual_budget_million_baht"}
    assert monthly["period_end"].max() == date(2026, 7, 31)

    html = sources["mof_budget_summary_html_2026"].records
    assert set(html["source_role"]) == {"validation"}
    assert {"current_budget", "capital_budget"}.issubset(set(html["category"]))

    nso = sources["nso_labour_region_sex_json_2569"].records
    assert set(nso["metric_unit"]) == {"thousand_persons"}
    assert nso.iloc[0]["period_start"] == date(2018, 1, 1)
    assert nso.iloc[0]["calendar_year_be"] == 2561


def test_public_contract_is_explicit_about_required_fields_and_semantic_policy():
    contract = json.loads(
        open("config/public_source_contract.json", encoding="utf-8").read()
    )

    assert set(contract["required_columns"]).issubset(PUBLIC_INDICATOR_COLUMNS)
    assert contract["grain"] == "release_id × record_key × metric_name"
    assert contract["policy"]["reference_value_is_non_additive"] is True


def test_canonical_parquet_round_trip_is_a_supported_columnar_format(tmp_path):
    source = parse_public_sources(
        source_ids={"nso_labour_region_sex_json_2569"},
    )[0]
    parquet_path = tmp_path / "nso_labour.parquet"
    write_canonical_parquet(source, parquet_path)

    derived_spec = PublicSourceSpec(
        source_id="nso_labour_region_sex_parquet_test",
        dataset_name=source.spec.dataset_name,
        source_name="Parquet test materialization",
        source_page_url=source.spec.source_page_url,
        file_url=None,
        path=parquet_path,
        format="parquet",
        parser="canonical_parquet",
        source_role="derived",
    )
    parsed = parse_public_source(derived_spec)

    assert len(parsed.records) == len(source.records)
    assert set(parsed.records["source_id"]) == {"nso_labour_region_sex_parquet_test"}
    assert all(isinstance(payload, dict) for payload in parsed.records["raw_payload"])


def test_public_quality_gate_blocks_a_negative_measure():
    source = parse_public_sources(
        source_ids={"nso_labour_region_sex_json_2569"},
    )[0]
    records = source.records.copy()
    records.loc[records.index[0], "value"] = -1
    invalid_source = replace(source, records=records)

    issues = run_public_quality_checks([invalid_source], "invalid-run")

    assert "failed" in set(issues["status"])
    assert "public_nso_labour_force_non_negative_value" in set(issues["check_name"])
