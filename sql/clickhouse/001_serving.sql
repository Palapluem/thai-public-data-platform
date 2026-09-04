CREATE DATABASE IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.fact_budget_execution
(
    run_id UUID,
    source_file_id UUID,
    source_file_hash String,
    sheet_index UInt32,
    sheet_name LowCardinality(String),
    row_number UInt32,
    fiscal_year Nullable(Int32),
    fiscal_year_be Nullable(Int32),
    as_of_date Nullable(Date),
    report_type LowCardinality(String),
    entity_type LowCardinality(String),
    entity_name String,
    entity_code Nullable(String),
    expense_category LowCardinality(String),
    budget_after_transfer_million_baht Nullable(Decimal(20, 6)),
    allocated_million_baht Nullable(Decimal(20, 6)),
    po_reserved_debt_million_baht Nullable(Decimal(20, 6)),
    disbursement_million_baht Nullable(Decimal(20, 6)),
    disbursement_pct Nullable(Decimal(7, 4)),
    expenditure_million_baht Nullable(Decimal(20, 6)),
    expenditure_pct Nullable(Decimal(7, 4)),
    monthly_target_gap_pct Nullable(Decimal(7, 4)),
    remaining_million_baht Nullable(Decimal(20, 6)),
    remaining_pct Nullable(Decimal(7, 4)),
    published_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(published_at)
ORDER BY (source_file_hash, sheet_index, row_number, entity_name, report_type, expense_category);

CREATE TABLE IF NOT EXISTS analytics.fact_workforce_metric
(
    run_id UUID,
    source_file_id UUID,
    source_file_hash String,
    sheet_index UInt32,
    sheet_name LowCardinality(String),
    row_number UInt32,
    fiscal_year Nullable(Int32),
    fiscal_year_be Nullable(Int32),
    entity_type LowCardinality(String),
    ministry_name Nullable(String),
    agency_name String,
    metric_name LowCardinality(String),
    metric_group LowCardinality(String),
    headcount Nullable(Int32),
    percentage Nullable(Decimal(7, 4)),
    source_value Nullable(String),
    source_unit LowCardinality(String),
    published_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(published_at)
ORDER BY (source_file_hash, sheet_index, row_number, agency_name, metric_name);
