# Analytical Story: Public Finance and Labour Signals

## Audience and decision

The audience is a reviewer, analyst or data-product stakeholder who needs a
quick descriptive view of public spending and labour-force scale while being
able to audit how each number was produced. The dashboard is not designed to
make causal claims or combine incomparable reporting periods.

## Questions

### 1. Momentum

**Question:** How does monthly expenditure move over the available month-end
window?

- source: Ministry of Finance nested JSON API;
- grain: one ministry × month × metric before aggregation;
- displayed grain: one month;
- measure: sum of `monthly_expenditure_million_baht`;
- rule: never sum the repeated annual budget reference value;
- chart: line, because the series has more than eight time points.

### 2. Concentration

**Question:** Which ministry groups account for the largest annual disbursement
amount?

- source: Ministry of Finance CSV;
- grain: department × fiscal year × metric before aggregation;
- displayed grain: ministry group;
- measure: sum of department-level disbursed amount;
- rate: recompute total disbursed ÷ total budget received;
- chart: ranked horizontal bars.

### 3. Context

**Question:** How does the latest available labour-force estimate vary by
region?

- source: National Statistical Office tabular JSON;
- grain: region × quarter × sex × metric before aggregation;
- displayed grain: region for a selected quarter;
- measure: sum across the two sex rows;
- unit: thousand persons;
- chart: ranked bars with a quarter selector.

### 4. Trust

**Question:** Can the reader see whether the data is current and whether
representations were mixed incorrectly?

The dashboard shows source format, source role, row count, period range and
committed watermark. The HTML table is retained as `validation` evidence. It is
not included in finance totals because it is a separate representation of
budget execution and contains a different section grain.

## Interpretation rules

1. A high monthly value is a descriptive observation, not evidence of why it
   changed.
2. A high ministry total reflects the chosen fiscal release and department
   aggregation; it is not automatically efficiency.
3. Labour-force estimates are survey/statistical observations in thousand
   persons, not employee-level records.
4. Finance and labour sources have different time coverage and populations; do
   not join them to claim an outcome relationship without a separate design.
5. A chart is not fresh merely because the HTML was generated recently. Check
   source updated time, business watermark and pipeline status.

## Validation checklist for a new chart

- audience and question are explicit;
- source and official URL are visible;
- row grain and aggregation are known;
- additive and non-additive fields are separated;
- filters exclude validation/derived rows when appropriate;
- unit and time period are shown;
- latest watermark and DQ status are available;
- caveat is written next to interpretation;
- SQL returns a stable shape and has a smoke test.
