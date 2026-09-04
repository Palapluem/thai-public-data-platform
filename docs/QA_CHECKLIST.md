# QA Checklist

## Bootstrap and provenance — completed

- [x] Workspace path is exactly `D:\thai-public-data-platform`
- [x] Existing files were listed before any write; workspace was empty
- [x] Git repository initialized on `main`
- [x] Public source pages, release periods and hashes are recorded
- [x] Baseline files are stored for deterministic local reproduction
- [x] Required folders and governance files exist
- [x] `.env.example` contains placeholders only
- [x] `.gitignore` excludes secrets and generated database artifacts
- [x] Bad-data fixture exists
- [x] Safety scan found no high-confidence secret patterns
- [x] Remote push was not attempted

## PostgreSQL implementation

- [x] `docs/DATA_MODEL.md` matches the implemented migrations
- [x] PK/FK strategy is present
- [x] Unique natural grain includes nullable source codes via `NULLS NOT DISTINCT`
- [x] `NUMERIC` precision is used for financial measures
- [x] Transaction boundary and failed-run behavior are implemented
- [x] Schema names are exactly `raw`, `staging`, `core`, `ops`

## P0 implementation verification

- [x] Clean install succeeds on Python 3.12
- [x] Baseline profile and parser counts match manifest/evidence
- [x] CGD and OCSC parser unit tests pass
- [x] Required-key and zero-row checks pass/fail as expected
- [x] Negative monetary value is blocking
- [x] Percentage bounds and signed target variance are enforced
- [x] Duplicate natural grain is blocking
- [x] Reconciliation mismatch is recorded and gates when configured blocking
- [x] Foreign-key/source identity integrity is checked before core publish
- [x] Row-count collapse threshold is checked against the matching baseline hash
- [x] Bad-data fixture prevents downstream publication
- [x] Repeat same source release has idempotent guards
- [x] Failed validation stops core/ClickHouse downstream tasks
- [x] ClickHouse publisher accepts only the approved handoff
- [x] Airflow DAG task IDs match contract and the full DAG run passed in Docker
- [x] Analytical smoke queries use explicit grain/period filters
- [x] All four analytical queries returned rows from ClickHouse
- [x] Same-source rerun returned idempotent skip counts with no duplicate core rows
- [x] Bad-data fixture exited non-zero with blocking issues
- [x] CI passes lint and tests locally

## Final safety review

- [x] `git status --short --branch` reviewed
- [x] high-confidence secret scan run on project text files
- [x] no `.env`, credential JSON, private key, log, `.duckdb` or generated DB artifact tracked
- [x] source URLs and provenance notes are documented
- [x] no remote push without explicit instruction
