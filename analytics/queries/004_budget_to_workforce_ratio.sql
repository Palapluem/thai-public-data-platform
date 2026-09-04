/*
   Question: what is the budget-per-civil-servant ratio for names that match
   exactly after conservative whitespace/case normalization?

   Budget basis: use the source's allocated amount when it is populated. The
   baseline agency rows leave that field empty but provide
   budget_after_transfer, so the query falls back explicitly and exposes the
   selected basis in the result instead of returning misleading NULL ratios.

   This is a cross-source exploratory ratio, not a contemporaneous KPI:
   CGD is a FY 2569 snapshot while OCSC is FY 2567. Each side is aggregated
   to entity_key before joining to prevent many-to-many join inflation.
*/
WITH budget AS (
    SELECT
        lowerUTF8(replaceAll(entity_name, ' ', '')) AS entity_key,
        any(entity_name) AS budget_entity_name,
        any(fiscal_year) AS budget_fiscal_year,
        any(fiscal_year_be) AS budget_fiscal_year_be,
        any(as_of_date) AS budget_as_of_date,
        if(
            countIf(allocated_million_baht IS NOT NULL) > 0,
            sumOrNull(allocated_million_baht),
            sumOrNull(budget_after_transfer_million_baht)
        ) AS budget_million_baht,
        if(
            countIf(allocated_million_baht IS NOT NULL) > 0,
            'allocated',
            'budget_after_transfer'
        ) AS budget_basis
    FROM analytics.fact_budget_execution FINAL
    WHERE report_type = 'disbursement'
      AND expense_category = 'total'
      AND entity_type = 'agency'
    GROUP BY entity_key
),
workforce AS (
    SELECT
        lowerUTF8(replaceAll(agency_name, ' ', '')) AS entity_key,
        any(agency_name) AS workforce_agency_name,
        any(fiscal_year) AS workforce_fiscal_year,
        any(fiscal_year_be) AS workforce_fiscal_year_be,
        sumOrNull(fact_workforce_metric.headcount) AS civil_servant_headcount
    FROM analytics.fact_workforce_metric FINAL
    WHERE metric_name = 'civil_servant'
      AND source_unit = 'person'
      AND entity_type = 'agency'
      AND fact_workforce_metric.headcount IS NOT NULL
    GROUP BY entity_key
)
SELECT
    b.budget_entity_name,
    w.workforce_agency_name,
    b.budget_fiscal_year,
    b.budget_fiscal_year_be,
    b.budget_as_of_date,
    w.workforce_fiscal_year,
    w.workforce_fiscal_year_be,
    b.budget_million_baht,
    b.budget_basis,
    w.civil_servant_headcount,
    if(
        w.civil_servant_headcount > 0,
        toFloat64(b.budget_million_baht) / toFloat64(w.civil_servant_headcount),
        NULL
    ) AS budget_million_baht_per_civil_servant,
    'Cross-source exploratory ratio; reporting periods are not aligned.' AS reporting_period_note
FROM budget AS b
INNER JOIN workforce AS w ON b.entity_key = w.entity_key
ORDER BY budget_million_baht_per_civil_servant DESC
LIMIT 100;
