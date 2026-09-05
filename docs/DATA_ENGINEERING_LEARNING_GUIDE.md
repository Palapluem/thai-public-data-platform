# Data Engineering Learning Guide for an AI Engineer

This project is a laboratory, not just a collection of technologies. The
important skill is learning how to make data trustworthy for another person,
service or report to consume repeatedly.

## 1. The mental model

Think in five questions before thinking about tools:

1. **What does one row represent?** This is the grain. If the answer is vague,
   the table and every aggregate built on it are unsafe.
2. **Where did the row come from?** Keep source identity, release hash, URL and
   source coordinates or raw payload.
3. **When is the row true?** Separate business period (`period_end`) from
   ingestion time (`retrieved_at`/`published_at`).
4. **Can the operation be repeated?** A retry must not double-count data.
5. **What happens when the source is late, corrected or changed?** The design
   needs a deliberate policy instead of an accidental overwrite.

An AI Engineer often starts with `input → transform → model → output`. A data
platform adds a long-lived contract around the input and output:

| AI framing | Data Engineering framing | This repository |
|---|---|---|
| input file/API | source release with identity and provenance | `config/public_sources.yml`, `datasets/public/` |
| preprocessing | source-specific adapter plus canonical normalization | `public_sources/readers.py` |
| training/evaluation checks | data-quality checks and fail-closed gate | `public_sources/quality.py` |
| model artifact | versioned core/read model | PostgreSQL core, ClickHouse serving |
| inference job | scheduled/retriable workflow | Airflow DAG |
| experiment tracking | run, source, DQ and watermark evidence | `ops.*` |
| model monitoring | freshness, volume, schema and metric monitoring | health view, DQ, watermark events |

## 2. Read this repository in layer order

### Source and landing

`datasets/public/` contains deterministic snapshots. The important idea is
that a filename is not an identity; SHA-256 content hash is. A source registry
also records the official page and download/API URL so a reviewer can reproduce
or refresh the snapshot.

The adapters intentionally use different parsing strategies:

- CSV: header mapping, Thai fiscal year normalization and two metrics per
  department row;
- nested JSON API: one ministry object is flattened into ministry × month
  rows, while the repeated annual budget remains an explicit reference field;
- HTML: the table and section are parsed as validation evidence;
- tabular JSON: uppercase source columns become region × quarter × sex rows;
- Parquet: a derived columnar materialization, not a second authoritative
  source.

### Raw

Raw evidence should be close to what the source delivered. For the new path,
`raw.public_source_release` records file-level identity and
`raw.public_record` stores the source row number, record key, watermark value
and JSON payload. Raw data is not the place to hide ambiguity with aggressive
business transformations.

### Staging

Staging is the typed, source-aligned boundary. It is where a parser's output is
checked before it becomes an analyst-facing fact. It can retain rejected
evidence so an engineer can diagnose a failed run.

### Core

Core is the approved relational model. It has explicit constraints and keeps
release history. `core.v_public_indicator_current` is a convenience current
view that selects the latest published version for a natural key; it does not
erase history.

### Serving and marts

ClickHouse is optimized for analytical reads and can be rebuilt from approved
PostgreSQL data. The public serving table uses `ReplacingMergeTree` with the
semantic current key `(source_id, record_key, metric_name)`. Queries use `FINAL`
when they need the deduplicated current view.

The dashboard is a small analytical product, not a decorative UI. It declares
audience questions, units, grain, source role, freshness and caveats.

## 3. SQL and modeling skills to practise

### Grain before schema

Write the grain in plain language and in a candidate key. Examples:

```text
CSV: one department × fiscal year × metric
MOF API: one ministry × calendar month × metric
NSO: one region × quarter × sex × metric
```

Then ask whether a row can be repeated because of a total, subtotal, version or
join. Do not solve a grain problem with `SELECT DISTINCT`; fix the model or
make the deduplication rule explicit.

### Measures versus attributes

`value` is the measure. `reference_value` is not automatically additive. A
monthly row can carry an annual budget for context, but summing that repeated
budget produces a false total. Percentages should usually be recomputed from
numerator and denominator rather than averaged.

### Joins and double counting

Before a join, record the cardinality: one-to-one, one-to-many or many-to-many.
If both sides are many, aggregate to the intended grain first. For this
project, finance and labour sources have different populations and periods;
they are not automatically joinable just because both mention public-sector
entities or regions.

### PostgreSQL versus ClickHouse

PostgreSQL is the place for constraints, transaction boundaries, lineage and
operational truth. ClickHouse is the place for high-volume scans, aggregates
and serving-friendly read models. The choice is about workload and ownership,
not prestige.

## 4. Reliability skills

### Idempotency

There are several identities, and they answer different questions:

- `run_id`: which execution attempt?
- content hash: which exact source bytes?
- `release_id`: which registered source release?
- `record_key`: which business/natural row?
- watermark: how far into business time has the source been processed?

An idempotent system can rerun after a timeout without creating duplicate
facts. It should also be safe when the first run reached ClickHouse but died
before updating the watermark; this repository repairs that state on retry.

### Data quality

Quality checks should be tied to a failure mode: missing keys, zero rows,
duplicate grain, invalid numbers, negative values, invalid periods, volume
collapse and source-role mistakes. A check is useful only when its severity,
sample and action are visible. The gate is fail-closed for blocking errors.

### Schema evolution

Distinguish additive columns, renamed columns, type changes and semantic
changes. An additive field may be a warning; a missing required field should
block. Database migrations also need to be rerunnable. The view migration in
P2 demonstrates why an old migration must remain compatible with a schema that
has already received later columns.

### Failure and atomicity

The safe sequence is:

```text
register release + raw evidence + staging
        ↓
record DQ evidence
        ↓ (only if passed)
publish PostgreSQL core
        ↓
publish ClickHouse serving
        ↓
commit watermark and serving status
```

There are still two database systems, so this is not a distributed two-phase
commit. The design makes the PostgreSQL handoff recoverable and delays the
watermark until serving succeeds. A production system may add a publish
manifest, atomic table swap or reconciliation job.

## 5. Orchestration and CI/CD

Airflow should express dependency, retries, schedule, parameters and task
observability. It should not contain parser logic. The new DAG keeps the
pipeline call and dashboard build in reusable package functions.

CI should answer “can this change be merged?”:

- lint and import checks;
- unit tests for pure transforms and state decisions;
- contract validation for JSON/YAML/SQL;
- integration tests against disposable or local services;
- image build and, later, vulnerability/dependency scanning.

CD answers “how does an approved artifact reach an environment?” It needs
immutable image tags, environment configuration, migration ordering, health
checks, rollout strategy and rollback. This local project demonstrates CI and
runtime orchestration; it does not claim a cloud CD deployment.

## 6. Security and scale

The minimum security model is least privilege, local-only bind addresses,
secret injection outside Git, audit logs and separate read/write identities.
Public data is not automatically risk-free: URLs, downloaded files, runtime
logs and credentials still need review.

Scale by measuring first:

- storage: compression, Parquet partitioning and retention;
- compute: batch size, indexes, partition pruning and query profiles;
- orchestration: concurrency, retries, backfill windows and pools;
- data volume: whether pandas remains appropriate before moving to Spark;
- serving: pre-aggregations, materialized views and workload isolation.

Do not add Kafka or Spark because a roadmap lists them. Add them when latency,
volume, parallelism or organizational boundaries justify the operational cost.

## 7. What to learn next from the AI side

Prioritize these gaps:

1. advanced SQL: window functions, query plans, indexes, isolation and
   slowly-changing dimensions;
2. warehouse modeling: fact/dimension design, semantic layers and metric
   contracts;
3. batch reliability: incremental loads, late data, backfills, replay and
   reconciliation;
4. Linux/container/cloud basics: processes, networks, storage, IAM and
   observability;
5. analyst communication: define a metric, choose a chart, state uncertainty
   and separate description from causal inference;
6. production operations: SLAs/SLOs, alert routing, runbooks and rollback.

The existing AI background is an advantage in Python, testing, experimentation
and model/data interface design. The deliberate practice area is operating a
shared data contract after the first successful run.

## 8. Readiness checklist

Before calling a pipeline production-like, explain:

- the row grain and key for every table;
- exact behavior on retry, duplicate source, correction and late data;
- what survives a task failure and how the run is repaired;
- how completeness and freshness are measured;
- how a dashboard number traces to source evidence;
- which joins are safe and which are not;
- who can read/write each layer;
- how deployment rollback and schema rollback would work.

Use [`PRACTICE_EXERCISES.md`](PRACTICE_EXERCISES.md) to turn each item into
observable evidence.
