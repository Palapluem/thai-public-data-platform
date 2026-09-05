# Data Engineering / Analytics Interview Guide for an AI Engineer

## 30-second project pitch

“I built a local public-data platform that ingests heterogeneous Thai government
sources—Excel, CSV, nested JSON API, HTML and tabular JSON—into a canonical
indicator model. PostgreSQL preserves raw evidence, release history, DQ
results and watermark state; ClickHouse serves analytical queries and a
source-aware dashboard. I made retries idempotent with content hashes and
natural keys, treated same-period changes as corrections/backfills, and delayed
watermark commit until serving succeeded. I can show both unit tests and a
Docker/Airflow integration run.”

Then state the boundary: local production-like evidence is implemented; cloud
IAM, streaming and automated CD rollback are next extensions, not claims.

## A reliable answer structure

For almost any question, answer in this order:

1. business requirement and SLA;
2. row grain and source contract;
3. happy-path design;
4. retry/duplicate/correction behavior;
5. quality and observability;
6. security and scale trade-off;
7. evidence or test you would run.

This prevents a tool list from replacing engineering reasoning.

## Questions and answer anchors

### How do you make a pipeline idempotent?

Separate run identity, source-release identity and natural-row identity. Hash
the source bytes, register the release once, use unique constraints for the
canonical grain, and make serving inserts/retries safe. Then test the same
release twice and inspect counts rather than trusting a successful exit code.

### What is a watermark and how is it different from a source hash?

A hash identifies exact content; a watermark identifies business-time progress.
A new hash can contain a correction at an old period, so equal/older candidate
periods are processed as backfill. The watermark must never move backwards.

### What if the source changes schema?

Validate at the parser-to-staging boundary. Additive fields can be warnings if
not required; missing or renamed required fields block publication. Preserve
the raw release for diagnosis, version the contract, and add a fixture test.

### What if data arrives late?

Keep raw history, classify late rows, and use a correction/backfill path. The
current serving view needs an explicit latest-version rule. I would monitor
late-arrival rate and reconcile historical periods after backfill.

### How do you prevent double counting?

Declare grain before writing SQL, aggregate each side before many-to-many joins,
filter totals/subtotals, and distinguish additive measures from repeated
reference attributes. For this project, annual budget on every monthly API row
is context, not a monthly additive measure.

### What happens if a task fails halfway?

The run remains observable. Raw/staging evidence can remain for diagnosis; core
publication is gated; ClickHouse failure leaves the watermark unchanged so a
retry can select the release. A production design may add a publish manifest or
atomic serving swap because PostgreSQL and ClickHouse are separate systems.

### How do you know the data is complete?

Use source-specific row expectations, duplicate/key checks, period coverage,
reconciliation totals, freshness/watermark checks and serving row counts. No
single row count proves completeness; the evidence must match the source's
grain and semantics.

### Why PostgreSQL and ClickHouse?

PostgreSQL owns constraints, lineage, transactions and operational truth.
ClickHouse is a rebuildable analytical read model for scans and aggregates. I
would benchmark the workload before choosing a different warehouse.

### When would you use Spark or Kafka?

When measured data volume, latency, parallelism or producer/consumer boundaries
justify their operational cost. For small public snapshots, pandas and a
transactional batch pipeline are easier to test and explain.

### What does CI/CD mean here?

CI validates code, contracts, tests, SQL and image build on every change. CD
would promote an immutable image/config through environments, apply compatible
migrations, run health checks, publish safely and provide a rollback path. The
repository has strong CI/runtime evidence but not a production cloud CD claim.

### How do you secure the platform?

Keep secrets outside Git, use least-privilege database roles, bind local
services to loopback, separate read/write access, restrict service accounts,
audit operational actions and scan dependencies/images. Public data does not
remove the need for infrastructure security.

## Analyst questions

### How would you present a dashboard result?

State metric, unit, grain, source, period and caveat before interpretation. Use
weighted rates from amounts, label validation data, show freshness, and avoid a
causal statement when the data is descriptive or periods are misaligned.

### What makes a good metric definition?

Name, question, entity grain, numerator/denominator, filters, unit, source,
refresh expectation, owner and known exclusions. A dashboard is a product
contract, not merely a chart query.

## Follow-up questions to ask the interviewer

- What is the data product's freshness SLA and acceptable late-arrival window?
- Who owns source schema changes and quality incidents?
- Are backfills common, and how are they approved?
- What is the canonical metric/semantic layer?
- How are migrations, deployments and rollbacks operated?
- Which data volume and query latency make the current architecture insufficient?

These questions show production thinking without pretending every team needs the
same stack.
