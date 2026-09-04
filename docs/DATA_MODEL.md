# Data Model

เอกสารนี้เป็น implemented model contract; migration และ loader อยู่ใน `sql/postgres/` และ `src/thai_data_platform/warehouse/postgres.py`

## Modeling principles

- เก็บ source evidence ก่อน business-facing model
- ระบุ grain ก่อนเลือก key หรือเขียน analytical SQL
- ใช้ source-file identity ที่ผูกกับ SHA-256 ไม่ใช้ filename เป็น key เดียว
- ให้ PostgreSQL บังคับ structural integrity ด้วย PK/FK/UNIQUE/CHECK และให้ core บังคับ semantic numeric contract หลัง DQ ผ่าน
- ใช้ `NUMERIC` กับเงินและเปอร์เซ็นต์ ไม่ใช้ floating point เป็น canonical storage type
- ให้ run ที่ไม่ผ่าน quality gate คง evidence ไว้ใน `ops` แต่ไม่ publish core/ClickHouse

## Schemas and planned tables

### `raw` — source evidence

| Table | Grain | Key/relationship | Purpose |
|---|---|---|---|
| `raw.source_file` | 1 row ต่อ source release | `source_file_id` PK; `sha256` UNIQUE | filename, URLs, fiscal/as-of metadata, content identity |
| `raw.workbook_sheet` | 1 row ต่อ source file × sheet index | FK → `raw.source_file`; UNIQUE `(source_file_id, sheet_index)` | workbook shape, dimensions, formula/merge counts |
| `raw.cell` | 1 row ต่อ workbook sheet × row × column | FK → `raw.workbook_sheet`; UNIQUE `(workbook_sheet_id, row_number, column_number)` | non-empty cell evidence for audit |

### `staging` — source-aligned normalized boundary

| Table | Grain | Key/relationship | Purpose |
|---|---|---|---|
| `staging.cgd_budget_execution` | source release × sheet × source row × report type × expense category | PK; FK → `raw.source_file`, `ops.pipeline_run`; UNIQUE natural grain | typed CGD measures while preserving report semantics |
| `staging.ocsc_workforce` | source release × sheet × source row × metric | PK; FK → `raw.source_file`, `ops.pipeline_run`; UNIQUE natural grain | typed OCSC workforce metrics and units |

### `core` — canonical relational model

| Table | Grain | Key/relationship | Purpose |
|---|---|---|---|
| `core.entity` | 1 row ต่อ platform entity/mapping record | stable entity PK; source aliases remain traceable | reviewed/conformed entity boundary; not automatic fuzzy matching |
| `core.fact_budget_execution` | source release × entity/source name × report type × expense category × as-of date | PK; FK → source file, run, entity | analyst-ready budget fact from approved staging |
| `core.fact_workforce_metric` | source release × entity/source name × metric × source sheet/row | PK; FK → source file, run, entity | analyst-ready workforce fact from approved staging |

### `ops` — operational evidence

| Table | Grain | Key/relationship | Purpose |
|---|---|---|---|
| `ops.pipeline_run` | 1 row ต่อ execution attempt | `run_id` PK | status, timestamps, requested releases, counts and publish state |
| `ops.dq_result` | 1 row ต่อ run × check | PK; FK → `ops.pipeline_run` | check name, severity, count, sample and pass/fail |
| `ops.source_release_observation` | 1 row ต่อ source check × observed release | PK; FK → source file when known | optional discovery evidence and source availability |

## Required identity and metadata fields

Every source-aligned table should retain or reference:

| Field | Meaning |
|---|---|
| `source_file_id` | internal FK to the source release |
| `sha256` | 64-character content hash; unique source identity in `raw.source_file` |
| `run_id` | operational execution attempt |
| `dataset_name` | `cgd_budget_execution` or `ocsc_government_manpower` |
| `sheet_name` / `sheet_index` | source workbook location |
| `row_number` | source row for parser lineage |
| `fiscal_year` / `fiscal_year_be` | normalized CE/BE representation when present |
| `as_of_date` | CGD snapshot date when present |

## Natural grain constraints

### CGD

```text
source_file_id
× sheet_name
× row_number
× report_type
× entity_name/entity_code
× expense_category
```

The implementation must choose the exact nullable-key strategy in DDL (for example, a normalized natural-grain hash or `NULLS NOT DISTINCT` unique index) so that an absent `entity_code` cannot create duplicate rows. `report_type ∈ {disbursement, expenditure}` and `expense_category ∈ {current, investment, total}`.

### OCSC

```text
source_file_id
× sheet_name
× row_number
× agency_name
× metric_name
```

`metric_group` and `source_unit` are required semantic attributes. `headcount` is used for count metrics, `percentage` for ratio metrics and `average_age` uses a year unit; these values must not be aggregated as if they were the same measure.

## Constraint contract

The PostgreSQL implementation must include:

- primary keys on every table
- foreign keys from staging/core/ops children to their parent records
- unique SHA-256 source identity
- unique source-aligned natural grain
- `NOT NULL` on required keys, dataset, source identity, run and metric/report dimensions
- `CHECK` on enumerated values (`report_type`, `expense_category`, entity type, status and unit) in core/ops tables
- staging retains typed numeric values that fail range DQ so raw/staging/ops evidence survives a blocked run
- `CHECK` that financial measures are non-negative when populated in core
- `CHECK` that bounded percentage fields are between `0` and `100` when populated in core; `monthly_target_gap_pct` is a signed variance bounded to `-100` and `100`
- `CHECK` that `fiscal_year_be = fiscal_year + 543` when both are populated
- `NUMERIC(20,6)` (or stricter compatible precision) for baht-million measures
- `NUMERIC(7,4)` for percentages and `INTEGER` for headcounts
- row-count collapse is compared with the matching baseline hash and, when available, the latest successful run

## Publish semantics

1. Insert source/run/raw/staging evidence in a transaction. Staging is intentionally permissive for numeric values that DQ must explain.
2. Run checks against staging.
3. On blocking failure, commit only raw/staging/ops evidence with failed status; do not publish core or ClickHouse.
4. On pass, publish core and mark the run successful in one controlled transaction.
5. Publish ClickHouse from the approved core run only.

## Reporting-period caveat

The baseline OCSC file represents FY 2567 / 2024. The baseline CGD file represents budget execution as of 3 July 2569 / 2026. A cross-source model must expose both periods and must not imply that workforce and budget values are contemporaneous.
