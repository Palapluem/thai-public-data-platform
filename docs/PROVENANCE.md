# Data Provenance

## Baseline purpose

The two Excel workbooks under `datasets/` are public baseline releases kept
inside the repository so that parsing, validation and serving can be replayed
deterministically on a local machine. The project does not treat the checked-in
files as the latest releases.

## Source identity

`config/source_manifest.json` is the machine-readable registry for:

- public source page URL
- local filename and dataset name
- SHA-256 source identity
- reporting period and as-of date
- workbook shape and expected parsed row count

The pipeline uses SHA-256 plus dataset metadata as the source-release identity;
the filename alone is not sufficient for idempotency or lineage.

## Reporting periods

The baseline OCSC workbook represents FY 2567 / 2024. The baseline CGD
workbook represents FY 2569 / 2026 as of 3 July 2569. They are intentionally
kept as separate source releases, and cross-source outputs expose both periods
so that an analyst does not mistake them for a contemporaneous snapshot.

## Reproducibility boundary

The checked-in baseline is used for local tests and Docker demonstrations. A
future source refresh should create a new source release, recalculate its
profile and hash, pass the same quality contract, and remain queryable through
the raw-to-staging-to-core lineage.
