from pathlib import Path

from thai_data_platform.warehouse.clickhouse import _split_sql

QUERY_DIR = Path("analytics/queries/public")


def test_public_queries_are_single_statement_and_explicit_about_release_semantics():
    queries = sorted(QUERY_DIR.glob("*.sql"))

    assert len(queries) == 4
    assert all("FINAL" in query.read_text(encoding="utf-8") for query in queries)
    assert all(len(_split_sql(query.read_text(encoding="utf-8"))) == 1 for query in queries)
    monthly = (QUERY_DIR / "001_monthly_expenditure_trend.sql").read_text(encoding="utf-8")
    top = (QUERY_DIR / "002_top_ministry_disbursement.sql").read_text(encoding="utf-8")
    labour = (QUERY_DIR / "003_latest_labour_by_region.sql").read_text(encoding="utf-8")
    assert "sum(reference_value)" not in monthly
    assert "sumIf" in top
    assert "max(period_end)" in labour
