# Analytics Metric Contract

The files in this directory define the interpretation of analyst-facing
metrics separately from ingestion code. Every metric should state its source,
grain, required filters and caveats before it is used in a report.

This prevents common analytical failures such as:

- adding a published `total` row to its detail rows;
- mixing `disbursement` and `expenditure` as if they were one measure;
- summing workforce percentages as if they were person counts; and
- joining sources from different reporting periods without showing the period.

The contract is intentionally small. It is a readable semantic layer for the
current portfolio project, not a replacement for a full enterprise metrics
store.
