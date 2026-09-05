ALTER TABLE ops.pipeline_run
    ADD COLUMN IF NOT EXISTS run_type TEXT NOT NULL DEFAULT 'manual';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'pipeline_run_run_type_check'
    ) THEN
        ALTER TABLE ops.pipeline_run
            ADD CONSTRAINT pipeline_run_run_type_check
            CHECK (run_type IN ('manual', 'scheduled', 'backfill', 'replay'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_pipeline_run_type_status
    ON ops.pipeline_run (run_type, status, started_at);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'ops'
          AND table_name = 'pipeline_run'
          AND column_name = 'public_row_count'
    ) THEN
        EXECUTE $view$
        CREATE OR REPLACE VIEW ops.pipeline_run_health AS
        SELECT
            run_id,
            pipeline_name,
            run_type,
            status,
            started_at,
            ended_at,
            EXTRACT(EPOCH FROM (COALESCE(ended_at, now()) - started_at))::BIGINT AS duration_seconds,
            jsonb_array_length(source_hashes) AS source_count,
            raw_cell_count,
            cgd_row_count,
            ocsc_row_count,
            dq_failed_check_count,
            CASE
                WHEN status = 'serving_published' THEN 'healthy'
                WHEN status IN ('quality_failed', 'failed') THEN 'action_required'
                WHEN status = 'core_published' THEN 'awaiting_serving'
                ELSE 'in_progress'
            END AS health,
            public_row_count,
            watermark_advanced_count
        FROM ops.pipeline_run
        $view$;
    ELSE
        EXECUTE $view$
        CREATE OR REPLACE VIEW ops.pipeline_run_health AS
        SELECT
            run_id,
            pipeline_name,
            run_type,
            status,
            started_at,
            ended_at,
            EXTRACT(EPOCH FROM (COALESCE(ended_at, now()) - started_at))::BIGINT AS duration_seconds,
            jsonb_array_length(source_hashes) AS source_count,
            raw_cell_count,
            cgd_row_count,
            ocsc_row_count,
            dq_failed_check_count,
            CASE
                WHEN status = 'serving_published' THEN 'healthy'
                WHEN status IN ('quality_failed', 'failed') THEN 'action_required'
                WHEN status = 'core_published' THEN 'awaiting_serving'
                ELSE 'in_progress'
            END AS health
        FROM ops.pipeline_run
        $view$;
    END IF;
END $$;
