ALTER TABLE ops.pipeline_run
    ADD COLUMN IF NOT EXISTS public_row_count BIGINT NOT NULL DEFAULT 0;

ALTER TABLE ops.pipeline_run
    ADD COLUMN IF NOT EXISTS watermark_advanced_count BIGINT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS raw.public_source_release (
    release_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES ops.pipeline_run(run_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    source_format TEXT NOT NULL CHECK (source_format IN ('csv', 'json', 'html', 'parquet')),
    source_role TEXT NOT NULL CHECK (source_role IN ('authoritative', 'validation', 'derived')),
    source_url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    content_sha256 CHAR(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    source_updated_at TIMESTAMPTZ,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    record_count BIGINT NOT NULL CHECK (record_count >= 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_id, content_sha256)
);

CREATE TABLE IF NOT EXISTS raw.public_record (
    raw_public_record_id BIGSERIAL PRIMARY KEY,
    release_id UUID NOT NULL REFERENCES raw.public_source_release(release_id) ON DELETE RESTRICT,
    source_record_number INTEGER NOT NULL CHECK (source_record_number > 0),
    record_key TEXT NOT NULL,
    watermark_value DATE,
    payload JSONB NOT NULL,
    UNIQUE (release_id, record_key)
);

CREATE TABLE IF NOT EXISTS staging.public_indicator (
    staging_public_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ops.pipeline_run(run_id) ON DELETE RESTRICT,
    release_id UUID NOT NULL REFERENCES raw.public_source_release(release_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    content_sha256 CHAR(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    source_format TEXT NOT NULL CHECK (source_format IN ('csv', 'json', 'html', 'parquet')),
    source_role TEXT NOT NULL CHECK (source_role IN ('authoritative', 'validation', 'derived')),
    record_key TEXT NOT NULL,
    source_record_number INTEGER NOT NULL CHECK (source_record_number > 0),
    period_start DATE,
    period_end DATE,
    period_grain TEXT NOT NULL,
    calendar_year INTEGER,
    calendar_year_be INTEGER,
    fiscal_year INTEGER,
    fiscal_year_be INTEGER,
    entity_type TEXT NOT NULL,
    entity_code TEXT,
    entity_name TEXT NOT NULL,
    geography_type TEXT,
    geography_code TEXT,
    geography_name TEXT,
    category TEXT,
    subcategory TEXT,
    metric_name TEXT NOT NULL,
    metric_unit TEXT NOT NULL,
    value NUMERIC(24, 6),
    reference_metric TEXT,
    reference_value NUMERIC(24, 6),
    source_url TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    staged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (period_start IS NULL OR period_end IS NULL OR period_start <= period_end),
    CHECK (value IS NULL OR value >= 0),
    UNIQUE (release_id, record_key, metric_name)
);

CREATE TABLE IF NOT EXISTS core.fact_public_indicator (
    core_public_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ops.pipeline_run(run_id) ON DELETE RESTRICT,
    release_id UUID NOT NULL REFERENCES raw.public_source_release(release_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    content_sha256 CHAR(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    source_format TEXT NOT NULL CHECK (source_format IN ('csv', 'json', 'html', 'parquet')),
    source_role TEXT NOT NULL CHECK (source_role IN ('authoritative', 'validation', 'derived')),
    record_key TEXT NOT NULL,
    source_record_number INTEGER NOT NULL CHECK (source_record_number > 0),
    period_start DATE,
    period_end DATE,
    period_grain TEXT NOT NULL,
    calendar_year INTEGER,
    calendar_year_be INTEGER,
    fiscal_year INTEGER,
    fiscal_year_be INTEGER,
    entity_type TEXT NOT NULL,
    entity_code TEXT,
    entity_name TEXT NOT NULL,
    geography_type TEXT,
    geography_code TEXT,
    geography_name TEXT,
    category TEXT,
    subcategory TEXT,
    metric_name TEXT NOT NULL,
    metric_unit TEXT NOT NULL,
    value NUMERIC(24, 6),
    reference_metric TEXT,
    reference_value NUMERIC(24, 6),
    source_url TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (period_start IS NULL OR period_end IS NULL OR period_start <= period_end),
    CHECK (value IS NULL OR value >= 0),
    UNIQUE (release_id, record_key, metric_name)
);

CREATE TABLE IF NOT EXISTS ops.public_source_watermark (
    source_id TEXT PRIMARY KEY,
    watermark_field TEXT NOT NULL,
    watermark_value DATE,
    last_release_id UUID REFERENCES raw.public_source_release(release_id) ON DELETE RESTRICT,
    last_run_id UUID REFERENCES ops.pipeline_run(run_id) ON DELETE RESTRICT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.public_watermark_event (
    watermark_event_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ops.pipeline_run(run_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    release_id UUID REFERENCES raw.public_source_release(release_id) ON DELETE RESTRICT,
    previous_watermark DATE,
    selected_watermark DATE,
    selected_record_count BIGINT NOT NULL DEFAULT 0 CHECK (selected_record_count >= 0),
    status TEXT NOT NULL CHECK (status IN ('advanced', 'unchanged', 'backfill', 'failed')),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_public_release_source
    ON raw.public_source_release (source_id, retrieved_at DESC);
CREATE INDEX IF NOT EXISTS idx_public_record_release_watermark
    ON raw.public_record (release_id, watermark_value);
CREATE INDEX IF NOT EXISTS idx_public_staging_run
    ON staging.public_indicator (run_id, source_id, period_end);
CREATE INDEX IF NOT EXISTS idx_public_core_metric_period
    ON core.fact_public_indicator (source_id, metric_name, period_end);
CREATE INDEX IF NOT EXISTS idx_public_watermark_events
    ON ops.public_watermark_event (source_id, recorded_at DESC);

CREATE OR REPLACE VIEW core.v_public_indicator_current AS
SELECT DISTINCT ON (source_id, record_key, metric_name)
    core_public_id,
    run_id,
    release_id,
    source_id,
    content_sha256,
    source_format,
    source_role,
    record_key,
    source_record_number,
    period_start,
    period_end,
    period_grain,
    calendar_year,
    calendar_year_be,
    fiscal_year,
    fiscal_year_be,
    entity_type,
    entity_code,
    entity_name,
    geography_type,
    geography_code,
    geography_name,
    category,
    subcategory,
    metric_name,
    metric_unit,
    value,
    reference_metric,
    reference_value,
    source_url,
    raw_payload,
    published_at
FROM core.fact_public_indicator
ORDER BY source_id, record_key, metric_name, published_at DESC, core_public_id DESC;

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
FROM ops.pipeline_run;
