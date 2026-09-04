CREATE TABLE IF NOT EXISTS staging.cgd_budget_execution (
    staging_cgd_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ops.pipeline_run(run_id) ON DELETE RESTRICT,
    source_file_id UUID NOT NULL REFERENCES raw.source_file(source_file_id) ON DELETE RESTRICT,
    workbook_sheet_id BIGINT NOT NULL REFERENCES raw.workbook_sheet(workbook_sheet_id) ON DELETE RESTRICT,
    dataset_name TEXT NOT NULL CHECK (dataset_name = 'cgd_budget_execution'),
    sheet_index INTEGER NOT NULL CHECK (sheet_index > 0),
    sheet_name TEXT NOT NULL,
    row_number INTEGER NOT NULL CHECK (row_number > 0),
    fiscal_year INTEGER,
    fiscal_year_be INTEGER,
    as_of_date DATE,
    report_type TEXT NOT NULL CHECK (report_type IN ('disbursement', 'expenditure')),
    entity_type TEXT NOT NULL CHECK (
        entity_type IN (
            'summary',
            'ministry',
            'agency',
            'province',
            'municipality',
            'provincial_admin_org',
            'state_enterprise',
            'fund',
            'total'
        )
    ),
    entity_name TEXT NOT NULL,
    entity_code TEXT,
    expense_category TEXT NOT NULL CHECK (expense_category IN ('current', 'investment', 'total')),
    budget_after_transfer_million_baht NUMERIC(20, 6),
    allocated_million_baht NUMERIC(20, 6),
    po_reserved_debt_million_baht NUMERIC(20, 6),
    disbursement_million_baht NUMERIC(20, 6),
    disbursement_pct NUMERIC(7, 4),
    expenditure_million_baht NUMERIC(20, 6),
    expenditure_pct NUMERIC(7, 4),
    monthly_target_gap_pct NUMERIC(7, 4),
    remaining_million_baht NUMERIC(20, 6),
    remaining_pct NUMERIC(7, 4),
    source_value JSONB,
    CHECK (fiscal_year IS NULL OR fiscal_year_be IS NULL OR fiscal_year_be = fiscal_year + 543),
    UNIQUE NULLS NOT DISTINCT (
        source_file_id,
        workbook_sheet_id,
        sheet_index,
        row_number,
        report_type,
        entity_name,
        entity_code,
        expense_category
    )
);

CREATE TABLE IF NOT EXISTS staging.ocsc_workforce (
    staging_ocsc_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ops.pipeline_run(run_id) ON DELETE RESTRICT,
    source_file_id UUID NOT NULL REFERENCES raw.source_file(source_file_id) ON DELETE RESTRICT,
    workbook_sheet_id BIGINT NOT NULL REFERENCES raw.workbook_sheet(workbook_sheet_id) ON DELETE RESTRICT,
    dataset_name TEXT NOT NULL CHECK (dataset_name = 'ocsc_government_manpower'),
    sheet_index INTEGER NOT NULL CHECK (sheet_index > 0),
    sheet_name TEXT NOT NULL,
    row_number INTEGER NOT NULL CHECK (row_number > 0),
    fiscal_year INTEGER,
    fiscal_year_be INTEGER,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('ministry', 'agency', 'total')),
    ministry_name TEXT,
    agency_name TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_group TEXT NOT NULL CHECK (metric_group IN ('employment_type', 'age', 'gender', 'education_level', 'total')),
    headcount INTEGER,
    percentage NUMERIC(7, 4),
    source_value TEXT,
    source_unit TEXT NOT NULL CHECK (source_unit IN ('person', 'pct', 'year')),
    CHECK (fiscal_year IS NULL OR fiscal_year_be IS NULL OR fiscal_year_be = fiscal_year + 543),
    CHECK (
        (source_unit = 'person' AND headcount IS NOT NULL AND percentage IS NULL)
        OR (source_unit = 'pct' AND percentage IS NOT NULL AND headcount IS NULL)
        OR (source_unit = 'year' AND headcount IS NULL AND percentage IS NULL)
    ),
    UNIQUE (source_file_id, workbook_sheet_id, sheet_index, row_number, agency_name, metric_name)
);
