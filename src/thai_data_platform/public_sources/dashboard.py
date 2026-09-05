"""Build a self-contained, reproducible dashboard from the serving layer."""

# The dashboard is an intentionally inline, portable HTML artifact. Its CSS
# and JavaScript lines are kept close to the rendered markup for easy review.
# ruff: noqa: E501

from __future__ import annotations

import html
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from thai_data_platform.warehouse import clickhouse, postgres


def build_public_dashboard(
    *,
    postgres_url: str,
    clickhouse_host: str,
    clickhouse_port: int,
    clickhouse_user: str,
    clickhouse_password: str,
    clickhouse_database: str = "analytics",
    output_path: str | Path = "data/processed/public_dashboard/index.html",
) -> dict[str, Any]:
    """Query ClickHouse/PostgreSQL and write HTML plus a JSON snapshot."""
    client = clickhouse.connect(
        host=clickhouse_host,
        port=clickhouse_port,
        username=clickhouse_user,
        password=clickhouse_password,
        database=clickhouse_database,
    )
    try:
        snapshot = _query_snapshot(client, postgres_url)
    finally:
        client.close()
    target = Path(output_path)
    if target.suffix.lower() != ".html":
        target = target / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path = target.with_name("snapshot.json")
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    target.write_text(render_dashboard_html(snapshot), encoding="utf-8")
    return {
        "html": str(target),
        "snapshot": str(snapshot_path),
        "generated_at": snapshot["generated_at"],
        "latest_period": snapshot["metadata"]["latest_labour_period"],
    }


def render_dashboard_html(snapshot: dict[str, Any]) -> str:
    """Return a portable dashboard with no CDN, JavaScript package or secret."""
    payload = json.dumps(snapshot, ensure_ascii=False, default=_json_default)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    periods = snapshot["metadata"].get("labour_periods", [])
    period_options = "".join(
        f'<option value="{html.escape(str(period))}">{html.escape(str(period))}</option>'
        for period in periods
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Thai Public Data Signals</title>
  <style>
    :root {{ --ink:#17212b; --muted:#607080; --line:#dce4ea; --paper:#f6f8fa;
      --navy:#12344d; --teal:#0d7c86; --gold:#e6a23c; --red:#bd4b45; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; color:var(--ink); background:var(--paper);
      font:15px/1.5 Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; }}
    main {{ max-width:1240px; margin:0 auto; padding:36px 24px 56px; }}
    header {{ display:flex; justify-content:space-between; gap:24px; align-items:flex-end;
      border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:22px; }}
    h1 {{ margin:0; font-size:clamp(28px,4vw,48px); line-height:1.05; letter-spacing:-.04em; }}
    h2 {{ margin:0 0 4px; font-size:18px; }} h3 {{ margin:0 0 5px; font-size:15px; }}
    p {{ margin:0; }} .eyebrow {{ color:var(--teal); font-size:12px; font-weight:800;
      letter-spacing:.13em; text-transform:uppercase; margin-bottom:8px; }}
    .dek {{ color:var(--muted); max-width:700px; margin-top:12px; }}
    .asof {{ color:var(--muted); font-size:12px; text-align:right; min-width:210px; }}
    .grid {{ display:grid; gap:14px; }} .kpis {{ grid-template-columns:repeat(4,minmax(0,1fr)); }}
    .two {{ grid-template-columns:1.35fr 1fr; }} .card {{ background:#fff; border:1px solid var(--line);
      border-radius:14px; padding:18px; box-shadow:0 2px 8px rgba(18,52,77,.04); }}
    .kpi-label {{ color:var(--muted); font-size:12px; }} .kpi-value {{ color:var(--navy);
      font-size:28px; font-weight:750; letter-spacing:-.03em; margin:4px 0; }}
    .kpi-note {{ color:var(--muted); font-size:12px; }} .section {{ margin-top:14px; }}
    .section-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px;
      margin-bottom:12px; }} .section-head p, .note {{ color:var(--muted); font-size:13px; }}
    svg {{ width:100%; height:auto; display:block; overflow:visible; }} .axis {{ stroke:var(--line); stroke-width:1; }}
    .line {{ fill:none; stroke:var(--teal); stroke-width:3; stroke-linecap:round; stroke-linejoin:round; }}
    .dot {{ fill:#fff; stroke:var(--teal); stroke-width:2; }} .bar {{ fill:var(--navy); }}
    .bar.alt {{ fill:var(--teal); }} .chart-label {{ fill:var(--muted); font-size:11px; }}
    .legend {{ color:var(--muted); font-size:12px; margin-top:8px; }}
    select {{ border:1px solid var(--line); border-radius:8px; background:#fff; color:var(--ink);
      padding:7px 10px; font:inherit; }} table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th,td {{ text-align:left; border-bottom:1px solid var(--line); padding:9px 6px; vertical-align:top; }}
    th {{ color:var(--muted); font-size:11px; letter-spacing:.06em; text-transform:uppercase; }}
    .pill {{ display:inline-block; border-radius:999px; background:#e6f4f2; color:#12656c;
      padding:2px 8px; font-size:11px; font-weight:700; }} .story {{ display:grid; gap:10px; }}
    .story-item {{ border-left:3px solid var(--gold); padding-left:12px; }}
    .foot {{ color:var(--muted); font-size:12px; margin-top:18px; }} a {{ color:var(--teal); }}
    @media (max-width:850px) {{ header {{ display:block; }} .asof {{ text-align:left; margin-top:14px; }}
      .kpis, .two {{ grid-template-columns:1fr 1fr; }} }}
    @media (max-width:560px) {{ main {{ padding:24px 14px 40px; }} .kpis, .two {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <div class="eyebrow">Thai Public Data Platform · analytical serving</div>
      <h1>Public finance &amp; labour signals</h1>
      <p class="dek">A source-aware view of budget execution and regional labour-force scale. Every chart states its grain and uses the current version of a corrected natural key.</p>
    </div>
    <div class="asof">Generated<br><strong>{html.escape(str(snapshot["generated_at"]))}</strong><br><span id="latest-period"></span></div>
  </header>

  <section class="grid kpis">
    <div class="card"><div class="kpi-label">Budget received</div><div class="kpi-value" id="kpi-budget">—</div><div class="kpi-note">million baht · FY 2568 CSV</div></div>
    <div class="card"><div class="kpi-label">Disbursed</div><div class="kpi-value" id="kpi-disbursed">—</div><div class="kpi-note">million baht · FY 2568 CSV</div></div>
    <div class="card"><div class="kpi-label">Calculated execution rate</div><div class="kpi-value" id="kpi-rate">—</div><div class="kpi-note">disbursed ÷ received; weighted</div></div>
    <div class="card"><div class="kpi-label">Latest labour force</div><div class="kpi-value" id="kpi-labour">—</div><div class="kpi-note">thousand persons · latest quarter</div></div>
  </section>

  <section class="grid two section">
    <div class="card"><div class="section-head"><div><h2>Monthly expenditure trend</h2><p>One point per month; sum of monthly expenditure only.</p></div><span class="pill">22 available months</span></div><svg id="trend" viewBox="0 0 900 300" role="img" aria-label="Monthly expenditure line chart"></svg><div class="legend">Unit: million baht · MOF nested JSON API · period end is month end</div></div>
    <div class="card"><div class="section-head"><div><h2>Latest labour force by region</h2><p>Aggregated across male and female rows.</p></div><label class="note">Quarter <select id="labour-period">{period_options}</select></label></div><svg id="regions" viewBox="0 0 620 360" role="img" aria-label="Labour force by region bar chart"></svg><div class="legend">Unit: thousand persons · NSO tabular JSON</div></div>
  </section>

  <section class="grid two section">
    <div class="card"><div class="section-head"><div><h2>Where is disbursement concentrated?</h2><p>Top eight ministry groups from department-level CSV rows.</p></div></div><svg id="ministries" viewBox="0 0 900 430" role="img" aria-label="Top ministries bar chart"></svg><div class="legend">Unit: million baht · calculated rate is not an average of row percentages</div></div>
    <div class="card"><div class="section-head"><div><h2>Analytical story</h2><p>Questions this slice is designed to answer.</p></div></div><div class="story"><div class="story-item"><h3>1 · Momentum</h3><p class="note">Does monthly expenditure accelerate, dip, or show a year-end pattern?</p></div><div class="story-item"><h3>2 · Concentration</h3><p class="note">Which ministry groups explain most of the annual disbursement amount?</p></div><div class="story-item"><h3>3 · Context</h3><p class="note">How large is the latest regional labour-force base, and how does it vary?</p></div><div class="story-item"><h3>4 · Trust</h3><p class="note">Are the source roles, periods, watermarks, and lineage evidence visible before a conclusion is made?</p></div></div></div>
  </section>

  <section class="card section"><div class="section-head"><div><h2>Source coverage &amp; operational freshness</h2><p>Validation representation is visible but excluded from authoritative totals.</p></div></div><div id="coverage"></div><p class="foot">Caveats: the finance sources have different reporting grains; the API repeats annual budget as a reference attribute per month; labour rows are survey estimates in thousand persons; this dashboard is descriptive, not causal.</p></section>
</main>
<script>
const snapshot = {payload};
const q = (id) => document.getElementById(id);
const n = (x, digits=1) => Number(x || 0).toLocaleString('en-US', {{maximumFractionDigits:digits}});
const money = (x) => n(x, 1);
const esc = (x) => String(x).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
function lineChart(id, rows) {{
  const svg=q(id), w=900, h=300, p={{l:48,r:18,t:18,b:36}}, vals=rows.map(x=>Number(x.value)), max=Math.max(...vals,1), min=Math.min(...vals,0);
  const x=i=>p.l+i*(w-p.l-p.r)/Math.max(rows.length-1,1), y=v=>h-p.b-(v-min)*(h-p.t-p.b)/Math.max(max-min,1);
  let out=''; [0,.5,1].forEach(t=>{{const yy=p.t+t*(h-p.t-p.b);out+=`<line class="axis" x1="${{p.l}}" x2="${{w-p.r}}" y1="${{yy}}" y2="${{yy}}"/><text class="chart-label" x="4" y="${{yy+4}}">${{money(max-(max-min)*t)}}</text>`;}});
  const points=rows.map((r,i)=>`${{x(i)}},${{y(Number(r.value))}}`).join(' '); out+=`<polyline class="line" points="${{points}}"/>`;
  rows.forEach((r,i)=>{{out+=`<circle class="dot" cx="${{x(i)}}" cy="${{y(Number(r.value))}}" r="3"/><text class="chart-label" text-anchor="middle" x="${{x(i)}}" y="${{h-10}}">${{String(r.period).slice(0,7)}}</text>`;}}); svg.innerHTML=out;
}}
function barChart(id, rows, labelKey, valueKey) {{
  const svg=q(id), w=Number(svg.viewBox.baseVal.width), h=Number(svg.viewBox.baseVal.height), p={{l:190,r:42,t:14,b:16}}, max=Math.max(...rows.map(x=>Number(x[valueKey])),1), rowH=(h-p.t-p.b)/Math.max(rows.length,1); let out='';
  rows.forEach((r,i)=>{{const value=Number(r[valueKey]), yy=p.t+i*rowH+rowH*.18, bh=rowH*.62, bw=(w-p.l-p.r)*value/max;out+=`<text class="chart-label" text-anchor="end" x="${{p.l-8}}" y="${{yy+bh*.68}}">${{esc(r[labelKey])}}</text><rect class="bar ${{i%2?'alt':''}}" x="${{p.l}}" y="${{yy}}" width="${{bw}}" height="${{bh}}" rx="4"/><text class="chart-label" x="${{p.l+bw+7}}" y="${{yy+bh*.68}}">${{money(value)}}</text>`;}}); svg.innerHTML=out;
}}
function renderLabour(period) {{ const rows=snapshot.labour_by_period[period] || []; barChart('regions', rows, 'region', 'value'); q('kpi-labour').textContent=money(rows.reduce((a,x)=>a+Number(x.value),0)); q('latest-period').textContent='Latest labour period: '+period; }}
q('kpi-budget').textContent=money(snapshot.kpis.budget_received_million_baht); q('kpi-disbursed').textContent=money(snapshot.kpis.disbursed_million_baht); q('kpi-rate').textContent=n(snapshot.kpis.calculated_rate_pct,1)+'%';
lineChart('trend', snapshot.monthly_trend); barChart('ministries', snapshot.top_ministries, 'ministry', 'disbursed_million_baht');
const periods=Object.keys(snapshot.labour_by_period); const selector=q('labour-period'); selector.value=snapshot.metadata.latest_labour_period || periods[periods.length-1]; renderLabour(selector.value); selector.addEventListener('change', e=>renderLabour(e.target.value));
q('coverage').innerHTML='<table><thead><tr><th>Source</th><th>Format / role</th><th>Rows</th><th>Period</th><th>Watermark</th></tr></thead><tbody>'+snapshot.coverage.map(r=>`<tr><td>${{esc(r.source_id)}}</td><td>${{esc(r.source_format)}} · ${{esc(r.source_role)}}</td><td>${{n(r.row_count,0)}}</td><td>${{esc(r.min_period_end)}} → ${{esc(r.max_period_end)}}</td><td>${{esc(r.watermark || 'not committed')}}</td></tr>`).join('')+'</tbody></table>';
</script>
</body></html>"""


def _query_snapshot(client: Any, postgres_url: str) -> dict[str, Any]:
    kpi_rows = client.query(
        """
        SELECT
            sumIf(value, metric_name = 'budget_received_million_baht') AS budget_received,
            sumIf(value, metric_name = 'disbursed_million_baht') AS disbursed
        FROM fact_public_indicator FINAL
        WHERE source_id = 'mof_budget_summary_csv_2568'
          AND source_role = 'authoritative'
        """
    ).result_rows
    budget, disbursed = (kpi_rows[0] if kpi_rows else (0, 0))
    budget = _number(budget)
    disbursed = _number(disbursed)
    monthly = client.query(
        """
        SELECT period_end, sum(value) AS value
        FROM fact_public_indicator FINAL
        WHERE source_id = 'mof_budget_monthly_json_api_2026'
          AND source_role = 'authoritative'
          AND metric_name = 'monthly_expenditure_million_baht'
        GROUP BY period_end ORDER BY period_end
        """
    ).result_rows
    ministries = client.query(
        """
        SELECT category AS ministry, sumIf(value, metric_name = 'disbursed_million_baht') AS disbursed_million_baht
        FROM fact_public_indicator FINAL
        WHERE source_id = 'mof_budget_summary_csv_2568'
          AND source_role = 'authoritative' AND entity_type = 'department'
        GROUP BY ministry ORDER BY disbursed_million_baht DESC LIMIT 8
        """
    ).result_rows
    labour = client.query(
        """
        SELECT period_end, geography_name AS region, sum(value) AS value
        FROM fact_public_indicator FINAL
        WHERE source_id = 'nso_labour_region_sex_json_2569'
          AND source_role = 'authoritative'
          AND metric_name = 'labour_force_thousand_persons'
        GROUP BY period_end, region ORDER BY period_end, value DESC
        """
    ).result_rows
    coverage = client.query(
        """
        SELECT source_id, source_format, source_role, count() AS row_count,
               min(period_end) AS min_period_end, max(period_end) AS max_period_end
        FROM fact_public_indicator FINAL
        GROUP BY source_id, source_format, source_role
        ORDER BY source_role, source_id
        """
    ).result_rows
    watermarks = _postgres_dashboard_metadata(postgres_url)
    labour_by_period: dict[str, list[dict[str, Any]]] = {}
    for period, region, value in labour:
        key = _json_default(period)
        labour_by_period.setdefault(key, []).append({"region": region, "value": _number(value)})
    latest_period = max(labour_by_period) if labour_by_period else None
    watermark_map = {row["source_id"]: row["watermark"] for row in watermarks["watermarks"]}
    coverage_rows = []
    for source_id, source_format, source_role, row_count, min_period, max_period in coverage:
        coverage_rows.append(
            {
                "source_id": source_id,
                "source_format": source_format,
                "source_role": source_role,
                "row_count": int(row_count),
                "min_period_end": _json_default(min_period),
                "max_period_end": _json_default(max_period),
                "watermark": watermark_map.get(source_id),
            }
        )
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "kpis": {
            "budget_received_million_baht": budget,
            "disbursed_million_baht": disbursed,
            "calculated_rate_pct": (100 * disbursed / budget) if budget else 0,
        },
        "monthly_trend": [
            {"period": _json_default(period), "value": _number(value)}
            for period, value in monthly
        ],
        "top_ministries": [
            {"ministry": ministry, "disbursed_million_baht": _number(value)}
            for ministry, value in ministries
        ],
        "labour_by_period": labour_by_period,
        "coverage": coverage_rows,
        "metadata": {
            "latest_labour_period": latest_period,
            "labour_periods": sorted(labour_by_period),
            "watermarks": watermarks["watermarks"],
            "latest_pipeline_run": watermarks["latest_run"],
            "source_roles": {
                "authoritative": "Used in metrics and charts.",
                "validation": "Retained for reconciliation; excluded from totals.",
            },
        },
    }


def _postgres_dashboard_metadata(postgres_url: str) -> dict[str, Any]:
    with postgres.connect(postgres_url) as connection:
        watermark_rows = connection.execute(
            """
            SELECT source_id, watermark_value, updated_at
            FROM ops.public_source_watermark
            ORDER BY source_id
            """
        ).fetchall()
        latest = connection.execute(
            """
            SELECT run_id, status, started_at, public_row_count, watermark_advanced_count
            FROM ops.pipeline_run
            WHERE pipeline_name = 'thai_public_multiformat'
            ORDER BY started_at DESC LIMIT 1
            """
        ).fetchone()
    return {
        "watermarks": [
            {"source_id": source_id, "watermark": _json_default(value), "updated_at": _json_default(updated)}
            for source_id, value, updated in watermark_rows
        ],
        "latest_run": (
            {
                "run_id": str(latest[0]),
                "status": latest[1],
                "started_at": _json_default(latest[2]),
                "public_row_count": int(latest[3]),
                "watermark_advanced_count": int(latest[4]),
            }
            if latest
            else None
        ),
    }


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)
