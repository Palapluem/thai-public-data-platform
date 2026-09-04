from pathlib import Path

QUERY_DIR = Path("analytics/queries")


def test_analytical_queries_are_explicit_about_grain_and_source_semantics():
    queries = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(QUERY_DIR.glob("*.sql"))
    }

    assert set(queries) == {
        "001_largest_budget_allocations.sql",
        "002_below_median_disbursement.sql",
        "003_workforce_distribution.sql",
        "004_budget_to_workforce_ratio.sql",
    }
    assert all("FINAL" in query for query in queries.values())
    assert "report_type = 'disbursement'" in queries["001_largest_budget_allocations.sql"]
    assert "quantileExact" in queries["002_below_median_disbursement.sql"]
    assert "source_unit = 'person'" in queries["003_workforce_distribution.sql"]
    assert "fact_workforce_metric.headcount IS NOT NULL" in queries[
        "003_workforce_distribution.sql"
    ]
    assert "GROUP BY entity_key" in queries["004_budget_to_workforce_ratio.sql"]
    assert "budget_after_transfer_million_baht" in queries["004_budget_to_workforce_ratio.sql"]
    assert "budget_basis" in queries["004_budget_to_workforce_ratio.sql"]
    assert "budget_million_baht_per_civil_servant" in queries[
        "004_budget_to_workforce_ratio.sql"
    ]
    assert "reporting periods are not aligned" in queries["004_budget_to_workforce_ratio.sql"]
