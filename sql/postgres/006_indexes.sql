CREATE INDEX IF NOT EXISTS idx_source_file_dataset ON raw.source_file (dataset_name, fiscal_year, as_of_date);
CREATE INDEX IF NOT EXISTS idx_raw_cell_sheet_row ON raw.cell (workbook_sheet_id, row_number);
CREATE INDEX IF NOT EXISTS idx_cgd_staging_run ON staging.cgd_budget_execution (run_id, source_file_id);
CREATE INDEX IF NOT EXISTS idx_ocsc_staging_run ON staging.ocsc_workforce (run_id, source_file_id);
CREATE INDEX IF NOT EXISTS idx_core_budget_period ON core.fact_budget_execution (fiscal_year, as_of_date, report_type);
CREATE INDEX IF NOT EXISTS idx_core_workforce_period ON core.fact_workforce_metric (fiscal_year, metric_group);
CREATE INDEX IF NOT EXISTS idx_pipeline_status ON ops.pipeline_run (status, started_at);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_source_release_observation_file'
    ) THEN
        ALTER TABLE ops.source_release_observation
            ADD CONSTRAINT fk_source_release_observation_file
            FOREIGN KEY (source_file_id)
            REFERENCES raw.source_file(source_file_id)
            ON DELETE RESTRICT;
    END IF;
END $$;
