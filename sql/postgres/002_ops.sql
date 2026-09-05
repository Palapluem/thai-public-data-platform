CREATE TABLE IF NOT EXISTS ops.pipeline_run (
    run_id UUID PRIMARY KEY,
    pipeline_name TEXT NOT NULL DEFAULT 'thai_public_data_platform',
    run_type TEXT NOT NULL DEFAULT 'manual' CHECK (
        run_type IN ('manual', 'scheduled', 'backfill', 'replay')
    ),
    status TEXT NOT NULL CHECK (
        status IN (
            'prepared',
            'staged',
            'validated',
            'quality_failed',
            'core_published',
            'serving_published',
            'failed'
        )
    ),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    source_hashes JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(source_hashes) = 'array'),
    raw_cell_count BIGINT NOT NULL DEFAULT 0 CHECK (raw_cell_count >= 0),
    cgd_row_count BIGINT NOT NULL DEFAULT 0 CHECK (cgd_row_count >= 0),
    ocsc_row_count BIGINT NOT NULL DEFAULT 0 CHECK (ocsc_row_count >= 0),
    dq_failed_check_count BIGINT NOT NULL DEFAULT 0 CHECK (dq_failed_check_count >= 0),
    core_published_at TIMESTAMPTZ,
    serving_published_at TIMESTAMPTZ,
    error_message TEXT,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE IF NOT EXISTS ops.dq_result (
    dq_result_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ops.pipeline_run(run_id) ON DELETE RESTRICT,
    check_name TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    dataset_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    issue_count BIGINT NOT NULL CHECK (issue_count >= 0),
    sample JSONB,
    blocking BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL CHECK (status IN ('passed', 'failed')),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, check_name, dataset_name, table_name)
);

CREATE TABLE IF NOT EXISTS ops.source_release_observation (
    observation_id BIGSERIAL PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    source_page_url TEXT NOT NULL,
    observed_filename TEXT,
    observed_file_url TEXT,
    observed_publish_date DATE,
    source_status TEXT NOT NULL CHECK (source_status IN ('discovered', 'unchanged', 'new_data', 'unavailable')),
    checked_at TIMESTAMPTZ NOT NULL,
    source_file_id UUID,
    message TEXT
);
