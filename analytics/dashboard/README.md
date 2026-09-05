# Public dashboard

The dashboard is generated from ClickHouse serving data and PostgreSQL
operational metadata. It is a self-contained HTML artifact with inline CSS,
SVG and JavaScript, so it can be opened locally without a frontend build or
network dependency.

```powershell
python -m thai_data_platform public-dashboard `
  --postgres-url $env:POSTGRES_URL `
  --clickhouse-host 127.0.0.1 `
  --clickhouse-port 8123 `
  --clickhouse-password $env:CLICKHOUSE_PASSWORD
python -m http.server 8090 --directory data/processed/public_dashboard
```

Open `http://127.0.0.1:8090`. The generated folder contains `index.html` and
`snapshot.json`; both are ignored runtime artifacts and can be regenerated.

The dashboard deliberately separates authoritative and validation sources and
shows the grain/unit/caveat beside each visual. It is a descriptive analytical
product, not a causal model or production BI deployment.
