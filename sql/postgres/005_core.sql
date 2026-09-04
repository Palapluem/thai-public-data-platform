CREATE TABLE IF NOT EXISTS core.entity (
    entity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_name TEXT NOT NULL CHECK (dataset_name IN ('cgd_budget_execution', 'ocsc_government_manpower')),
    source_entity_name TEXT NOT NULL,
    source_entity_type TEXT NOT NULL,
    source_entity_code TEXT,
    ministry_name TEXT,
    canonical_name TEXT,
    mapping_status TEXT NOT NULL DEFAULT 'unmapped' CHECK (mapping_status IN ('unmapped', 'candidate', 'approved')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dataset_name, source_entity_name, source_entity_type)
);

CREATE TABLE IF NOT EXISTS core.fact_budget_execution (
    core_budget_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ops.pipeline_run(run_id) ON DELETE RESTRICT,
    source_file_id UUID NOT NULL REFERENCES raw.source_file(source_file_id) ON DELETE RESTRICT,
    workbook_sheet_id BIGINT NOT NULL REFERENCES raw.workbook_sheet(workbook_sheet_id) ON DELETE RESTRICT,
    entity_id UUID NOT NULL REFERENCES core.entity(entity_id) ON DELETE RESTRICT,
    dataset_name TEXT NOT NULL CHECK (dataset_name = 'cgd_budget_execution'),
    sheet_index INTEGER NOT NULL CHECK (sheet_index > 0),
    sheet_name TEXT NOT NULL,
    row_number INTEGER NOT NULL CHECK (row_number > 0),
    fiscal_year INTEGER,
    fiscal_year_be INTEGER,
    as_of_date DATE,
    report_type TEXT NOT NULL CHECK (report_type IN ('disbursement', 'expenditure')),
    entity_type TEXT NOT NULL,
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
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (fiscal_year IS NULL OR fiscal_year_be IS NULL OR fiscal_year_be = fiscal_year + 543),
    CHECK (report_type IN ('disbursement', 'expenditure')),
    CHECK (
        entity_type IN (
            'summary', 'ministry', 'agency', 'province', 'municipality',
            'provincial_admin_org', 'state_enterprise', 'fund', 'total'
        )
    ),
    CHECK (budget_after_transfer_million_baht IS NULL OR budget_after_transfer_million_baht >= 0),
    CHECK (allocated_million_baht IS NULL OR allocated_million_baht >= 0),
    CHECK (po_reserved_debt_million_baht IS NULL OR po_reserved_debt_million_baht >= 0),
    CHECK (disbursement_million_baht IS NULL OR disbursement_million_baht >= 0),
    CHECK (expenditure_million_baht IS NULL OR expenditure_million_baht >= 0),
    CHECK (remaining_million_baht IS NULL OR remaining_million_baht >= 0),
    CHECK (disbursement_pct IS NULL OR disbursement_pct BETWEEN 0 AND 100),
    CHECK (expenditure_pct IS NULL OR expenditure_pct BETWEEN 0 AND 100),
    CHECK (monthly_target_gap_pct IS NULL OR monthly_target_gap_pct BETWEEN -100 AND 100),
    CHECK (remaining_pct IS NULL OR remaining_pct BETWEEN 0 AND 100),
    CHECK (expense_category IN ('current', 'investment', 'total')),
    CHECK (monthly_target_gap_pct IS NULL OR monthly_target_gap_pct BETWEEN -100 AND 100),
    UNIQUE NULLS NOT DISTINCT (
        source_file_id,
        workbook_sheet_id,
        sheet_index,
        row_number,
        entity_id,
        report_type,
        expense_category
    )
);

CREATE TABLE IF NOT EXISTS core.fact_workforce_metric (
    core_workforce_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ops.pipeline_run(run_id) ON DELETE RESTRICT,
    source_file_id UUID NOT NULL REFERENCES raw.source_file(source_file_id) ON DELETE RESTRICT,
    workbook_sheet_id BIGINT NOT NULL REFERENCES raw.workbook_sheet(workbook_sheet_id) ON DELETE RESTRICT,
    entity_id UUID NOT NULL REFERENCES core.entity(entity_id) ON DELETE RESTRICT,
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
    metric_group TEXT NOT NULL,
    headcount INTEGER,
    percentage NUMERIC(7, 4),
    source_value TEXT,
    source_unit TEXT NOT NULL CHECK (source_unit IN ('person', 'pct', 'year')),
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (fiscal_year IS NULL OR fiscal_year_be IS NULL OR fiscal_year_be = fiscal_year + 543),
    CHECK (headcount IS NULL OR headcount >= 0),
    CHECK (percentage IS NULL OR percentage BETWEEN 0 AND 100),
    CHECK (metric_group IN ('employment_type', 'age', 'gender', 'education_level', 'total')),
    CHECK (
        (source_unit = 'person' AND headcount IS NOT NULL AND percentage IS NULL)
        OR (source_unit = 'pct' AND percentage IS NOT NULL AND headcount IS NULL)
        OR (source_unit = 'year' AND headcount IS NULL AND percentage IS NULL)
    ),
    UNIQUE (source_file_id, workbook_sheet_id, sheet_index, row_number, entity_id, metric_name)
);
