CREATE TABLE IF NOT EXISTS raw.source_file (
    source_file_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_name TEXT NOT NULL CHECK (dataset_name IN ('cgd_budget_execution', 'ocsc_government_manpower')),
    source_name TEXT NOT NULL,
    filename TEXT NOT NULL,
    source_path TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL UNIQUE CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    source_page_url TEXT,
    file_url TEXT,
    fiscal_year INTEGER,
    fiscal_year_be INTEGER,
    as_of_date DATE,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes >= 0),
    landed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dataset_name, filename, sha256),
    CHECK (
        fiscal_year IS NULL
        OR fiscal_year_be IS NULL
        OR fiscal_year_be = fiscal_year + 543
    )
);

CREATE TABLE IF NOT EXISTS raw.workbook_sheet (
    workbook_sheet_id BIGSERIAL PRIMARY KEY,
    source_file_id UUID NOT NULL REFERENCES raw.source_file(source_file_id) ON DELETE RESTRICT,
    sheet_index INTEGER NOT NULL CHECK (sheet_index > 0),
    sheet_name TEXT NOT NULL,
    max_row INTEGER NOT NULL CHECK (max_row >= 0),
    max_column INTEGER NOT NULL CHECK (max_column >= 0),
    non_empty_cells INTEGER NOT NULL CHECK (non_empty_cells >= 0),
    merged_cell_count INTEGER NOT NULL CHECK (merged_cell_count >= 0),
    formula_cell_count INTEGER NOT NULL CHECK (formula_cell_count >= 0),
    blank_row_count INTEGER NOT NULL CHECK (blank_row_count >= 0),
    blank_column_count INTEGER NOT NULL CHECK (blank_column_count >= 0),
    guessed_header_row INTEGER CHECK (guessed_header_row IS NULL OR guessed_header_row > 0),
    sheet_type TEXT NOT NULL,
    UNIQUE (source_file_id, sheet_index),
    UNIQUE (source_file_id, sheet_name)
);

CREATE TABLE IF NOT EXISTS raw.cell (
    raw_cell_id BIGSERIAL PRIMARY KEY,
    workbook_sheet_id BIGINT NOT NULL REFERENCES raw.workbook_sheet(workbook_sheet_id) ON DELETE RESTRICT,
    row_number INTEGER NOT NULL CHECK (row_number > 0),
    column_number INTEGER NOT NULL CHECK (column_number > 0),
    cell_value TEXT NOT NULL,
    UNIQUE (workbook_sheet_id, row_number, column_number)
);
