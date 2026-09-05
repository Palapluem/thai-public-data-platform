# Incremental, Watermark and Backfill Contract

## Why two identities are needed

An ingestion run answers “did this execution complete?” A content hash answers
“have these exact bytes been seen?” A watermark answers “what business period
has been selected?” They are not interchangeable.

| Concept | Example | Stored in |
|---|---|---|
| execution attempt | UUID for a scheduled run | `ops.pipeline_run.run_id` |
| source release | SHA-256 of a downloaded file | `raw.public_source_release.content_sha256` |
| natural row | deterministic hash of source dimensions | `record_key` |
| business progress | `2026-07-31` | `ops.public_source_watermark` |
| decision audit | advanced/unchanged/backfill | `ops.public_watermark_event` |

## Decision rules

For a source with previous watermark `W` and candidate maximum period `C`:

| Release | Condition | Selected rows | Status | New watermark |
|---|---|---|---|---|
| same hash | release already committed | none | `unchanged` | `W` |
| new hash | `C > W` | `period_end > W` for scheduled run | `advanced` | `C` |
| new hash | `C <= W` | all rows | `backfill` | `W` |
| new hash | no `W` yet | all rows | `advanced` | `C` |
| explicit backfill/replay | any period | all rows | `advanced` or `backfill` | max(`W`,`C`) |

The equal/older case is intentionally processed because a source can correct a
previous period without advancing its maximum date. “Incremental” must not mean
“ignore corrections.”

## State machine

```text
prepared
   ↓ register release and raw evidence
staged
   ↓ DQ checks
validated ── failure ──> quality_failed
   ↓
core_published ── ClickHouse failure ──> failed (watermark unchanged)
   ↓
serving_published ── commit watermark/event
```

The watermark is deliberately committed after ClickHouse. If the worker dies
after serving but before the commit, the next run detects an uncommitted
release and safely retries/repairs it. If ClickHouse fails, leaving the
watermark unchanged means a later retry still selects the needed rows.

## Late data and corrections

“Late” can mean two different things:

1. a new row whose period is older than the watermark; or
2. a correction to an existing natural key.

Both should be retained in raw and versioned in core. A current analytical view
must then choose the latest approved version. This repository uses
`published_at` ordering in PostgreSQL's current view and a
`ReplacingMergeTree` key in ClickHouse. A real system may use a source update
timestamp or an explicit version number when available; ingestion time is a
fallback, not proof that the source is semantically newer.

## Backfill procedure

1. preserve the original file/API response and calculate a new hash;
2. register it as a new release; never overwrite the old release by filename;
3. run with `--run-type backfill` when the full historical release is intended;
4. inspect DQ, selected row count, source watermark event and current-view
   reconciliation;
5. publish only after the gate passes;
6. record the reason, owner, source URL and validation evidence.

## What to monitor

- watermark age versus source SLA;
- candidate period moving backwards unexpectedly;
- many `backfill` events;
- selected rows becoming zero for a supposedly active source;
- source release hash changing without row/period change;
- raw count, selected count, core inserted count and serving count disagreeing;
- a run stuck at `core_published`.

## Exercises against this repository

Use the `public-run` command twice for `unchanged`. Then copy a source file to a
temporary path, alter one value or add a later period, and point a temporary
YAML registry at it. Use `scheduled` to observe selection after the watermark;
use `backfill` to load the complete release. Query both
`core.fact_public_indicator` and `core.v_public_indicator_current` to see why
history and current state are different datasets.
