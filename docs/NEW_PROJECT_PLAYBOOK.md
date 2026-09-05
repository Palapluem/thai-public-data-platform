# New Data Project Playbook

Use this before writing a DAG or choosing a warehouse. The goal is to discover
the contract and failure modes of the project first.

## 1. Understand the business decision

Write:

- who consumes the data;
- what decision/report/model depends on it;
- required freshness and acceptable lateness;
- what happens if the data is wrong or unavailable;
- whether the output is descriptive, operational or predictive.

Ask for one real example of a correct and incorrect output.

## 2. Inventory source ownership

For each source record:

| Field | Question |
|---|---|
| owner | Who can explain the meaning and approve changes? |
| access | File, API, database, event stream or manual upload? |
| identity | How do we know two deliveries are the same release? |
| update time | When did the producer create/change it? |
| business period | What period do the values describe? |
| schema | Which fields are required, optional or derived? |
| volume | Typical, peak and growth rate? |
| SLA | Freshness, completeness and availability expectations? |
| sensitivity | PII, confidential, regulated or public? |

Never assume filename or ingestion time is the business key.

## 3. Write the grain and metric contract

For every table/stream answer “one row represents what?” Then write:

```text
grain = dimension(s) × period × metric × version rule
primary/natural key = ...
additive measures = ...
non-additive attributes = ...
valid joins = ...
```

If stakeholders cannot agree on grain, stop and resolve it before modeling.

## 4. Design lifecycle and failure behavior

Draw:

```text
source → landing → raw → staging → quality → core → serving → consumer
```

For each boundary specify:

- transaction owner;
- retry behavior;
- duplicate behavior;
- schema failure behavior;
- partial-data behavior;
- replay/backfill entry point;
- retention and deletion policy.

Make raw evidence immutable or versioned. Avoid destructive “replace the file”
operations when a correction can be represented as a new release.

## 5. Choose architecture from constraints

| Constraint | Start with | Escalate when |
|---|---|---|
| small batch files | Python/pandas + PostgreSQL | volume or memory becomes measurable |
| analytical scans | warehouse/read model | latency or concurrency requires specialization |
| hourly/daily workflow | Airflow or managed scheduler | event latency/ownership demands streams |
| columnar history | Parquet/object storage | retention and scan volume justify lake layout |
| many producers/consumers | contracts + queue/stream | decoupling and replay needs are proven |

Document the rejected alternatives and the measurement that would change the
decision.

## 6. Define quality and observability

Minimum checks:

- schema and required columns;
- key uniqueness and referential integrity;
- null/validity/range checks;
- period and freshness coverage;
- source-to-target row/reconciliation counts;
- volume/shape drift;
- consumer metric smoke tests.

For each check specify severity, sample, owner, alert threshold and whether the
pipeline blocks. Log run ID, source release, duration, counts and status.

## 7. Security and operations

Confirm:

- service identities and least-privilege roles;
- secret storage and rotation;
- encryption and network boundary;
- data classification and retention;
- audit trail and incident response;
- backup/restore and disaster recovery objective;
- deployment and rollback procedure.

For a portfolio project, say what is simulated locally and what would use a
managed cloud service.

## 8. First-week delivery plan

1. profile one source without transforming it;
2. document grain and source contract;
3. land raw evidence with content identity;
4. build a small typed staging slice;
5. add a failing fixture before adding more features;
6. make the same release rerunnable;
7. publish one useful metric with a contract;
8. add operational state and a runbook;
9. test a correction/backfill;
10. only then expand formats, volume or infrastructure.

## 9. Handoff template

At handoff, include:

- architecture diagram and ownership table;
- source registry and refresh instructions;
- table grains and metric definitions;
- DQ checks and latest evidence;
- run/retry/backfill commands;
- freshness/volume dashboards;
- known caveats and non-goals;
- incident and rollback runbooks;
- resume/interview explanation that distinguishes implemented from planned.
