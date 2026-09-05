# Thai Public Data Platform — คู่มือภาษาไทย

[English](README.md) · [ภาษาไทย](README_TH.md)

โปรเจกต์ portfolio สำหรับฝึกงาน Data Engineering และ Data Analytics โดยใช้
ข้อมูลสาธารณะด้านงบประมาณ/การเบิกจ่ายและกำลังแรงงาน เหมาะกับคนที่มีพื้นฐาน
AI Engineer และต้องการขยายความสามารถด้านข้อมูลให้ครบตั้งแต่ source ถึง report

## สิ่งที่มีในระบบ

มี pipeline สองเส้นทางที่แยกความหมายกันชัดเจน:

1. เส้นทาง Excel เดิม: parser ตาม layout ของ source, raw cell lineage,
   PostgreSQL `raw → staging → core`, ClickHouse และ Airflow DAG เดิม 8 tasks
2. เส้นทาง multi-format: รองรับ CSV, nested JSON API, HTML table และ tabular
   JSON แล้ว normalize เป็น canonical `public_indicator` พร้อม release hash,
   raw payload, quality gate, watermark และ dashboard

การแยกเส้นทางป้องกันไม่ให้เราเอา grain ของข้อมูลที่ไม่เหมือนกันมารวมกันแบบผิด
ความหมาย แต่ยังใช้หลักเดียวกันเรื่อง idempotency, quality และ lineage

## Architecture

```text
Official public sources
        ↓
Format adapters (CSV / JSON / HTML / Excel)
        ↓
Canonical public_indicator + record_key + period
        ↓
PostgreSQL: raw → staging → core + ops
        ↓
Fail-closed data-quality gate
        ↓
ClickHouse analytical serving
        ↓
Analytical SQL + self-contained dashboard
```

PostgreSQL เป็น relational source of truth และเก็บประวัติ release ส่วน
ClickHouse เป็น read model ที่ rebuild ได้ Airflow จัด dependency/retry และ
package ใน `src/` เป็นเจ้าของ parser, validation และ database work

## Sources และ format ใหม่

Registry อยู่ที่ [`config/public_sources.yml`](config/public_sources.yml) โดยมี
URL ทางการ, parser, role, expected rows, source updated time และ watermark policy
ส่วน canonical field และ semantic rules อยู่ใน
[`config/public_source_contract.json`](config/public_source_contract.json)

| Source | Format | Role | Grain |
|---|---|---|---|
| สรุปงบประมาณกระทรวงการคลัง | CSV | authoritative | department × fiscal year × metric |
| การเบิกจ่ายรายเดือน | nested JSON API | authoritative | ministry × month × metric |
| ตารางสรุป HTML | HTML table | validation | section × ministry × metric |
| กำลังแรงงานตามภูมิภาค/เพศ | tabular JSON | authoritative | region × quarter × sex × metric |
| canonical materialization | Parquet | derived exercise | copy ในรูป columnar |

แหล่งอ้างอิง: [Government Spending data.go.th](https://data.go.th/dataset/gfsummary),
[MOF Data Services](https://dataservices.mof.go.th/menu4?id=3&lang=en) และ
[NSO labour dataset](https://data.go.th/en/dataset/0706_02_0001) รายละเอียด hash
และวันที่ดึงอยู่ใน [`datasets/public/README.md`](datasets/public/README.md)

## Grain ที่ต้องจำ

canonical row มี `source_id`, `source_format`, `source_role`, `record_key`,
`source_record_number`, ช่วงเวลา/ปี, entity/geography, `metric_name`,
`metric_unit`, `value`, reference metric/value, URL และ `raw_payload`

database grain คือ `(release_id, record_key, metric_name)` PostgreSQL เก็บทุก
version ใน `raw.public_source_release` และ `core.fact_public_indicator` ส่วน
`core.v_public_indicator_current` เลือก version ล่าสุดของ natural key

จุดที่ห้ามพลาด:

- budget รายปีที่ซ้ำในทุก monthly API row เป็น `reference_value` ห้าม sum เป็น
  ยอดรายเดือน
- HTML มี `source_role = validation` เก็บไว้ reconcile แต่ไม่รวมในยอด
  authoritative
- finance กับ labour เป็นคนละ reporting population/เวลา ห้ามสรุป causal
  relationship จาก dashboard นี้

## Incremental และ watermark

- bytes เหมือนเดิม → `unchanged`, selected rows เป็น 0
- bytes ใหม่และ period ใหม่กว่า → เลือกเฉพาะ period หลัง watermark, `advanced`
- bytes ใหม่แต่ max period เท่าเดิม/เก่ากว่า → process เป็น correction `backfill`
  และไม่ขยับ watermark ถอยหลัง
- `--run-type backfill` หรือ `replay` → โหลดทั้ง release อย่างตั้งใจ
- commit watermark หลัง ClickHouse publish สำเร็จเท่านั้น

หลักฐานอยู่ใน `ops.public_source_watermark` และ
`ops.public_watermark_event`

## วิธีรันด้วย Docker

```powershell
python -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# เปลี่ยน password placeholder ใน .env เป็นค่า local เท่านั้น
docker compose up -d --build
docker compose ps
```

ตั้ง connection ใน PowerShell session เดียวกัน โดยใช้ PostgreSQL port ใน `.env`
(environment เดิมใช้ `55432`):

```powershell
$env:POSTGRES_URL = "postgresql://platform:<password>@127.0.0.1:55432/thai_data_platform"
$env:CLICKHOUSE_PASSWORD = "<clickhouse-password>"
```

รัน public pipeline:

```powershell
python -m thai_data_platform public-run `
  --postgres-url $env:POSTGRES_URL `
  --clickhouse-host 127.0.0.1 `
  --clickhouse-port 8123 `
  --clickhouse-password $env:CLICKHOUSE_PASSWORD `
  --run-type scheduled
```

รันซ้ำอีกครั้งควรได้ watermark `unchanged` ทั้ง 4 source, selected rows = 0
และ `skipped_existing_sources = 4`

สร้างและเปิด dashboard:

```powershell
python -m thai_data_platform public-dashboard `
  --postgres-url $env:POSTGRES_URL `
  --clickhouse-host 127.0.0.1 `
  --clickhouse-port 8123 `
  --clickhouse-password $env:CLICKHOUSE_PASSWORD
python -m http.server 8090 --directory data/processed/public_dashboard
```

เปิด `http://127.0.0.1:8090` จะเห็น KPI, monthly trend, top ministries, selector
ของ labour-force quarter, source coverage และ caveat โดยไม่พึ่ง CDN

สร้าง Parquet เพื่อฝึก columnar storage:

```powershell
python -m thai_data_platform public-parquet `
  --source-id nso_labour_region_sex_json_2569
```

รัน Airflow DAG ใหม่:

```powershell
docker compose exec -T airflow-scheduler airflow dags unpause thai_public_multiformat
docker compose exec -T airflow-scheduler airflow dags trigger thai_public_multiformat --run-id public_local_test_01
```

ดู Docker walkthrough แบบละเอียดที่ [`docs/DOCKER_TEST_RUNBOOK.md`](docs/DOCKER_TEST_RUNBOOK.md)

## Analytical story

dashboard ตอบคำถามเชิงพรรณนา 4 ชั้น:

1. **Momentum:** การเบิกจ่ายรายเดือนเคลื่อนไหวอย่างไรในช่วงที่ source มีข้อมูล
2. **Concentration:** ministry group ใดมี disbursement สูงสุดจาก CSV รายปี
3. **Context:** labour force ล่าสุดกระจายตาม region อย่างไร
4. **Trust:** source role, period, watermark, row count และ caveat เพียงพอให้
   ตรวจความน่าเชื่อถือก่อนสรุปหรือไม่

SQL อยู่ใน [`analytics/queries/public`](analytics/queries/public) และ narrative
อยู่ใน [`docs/ANALYTICAL_STORY.md`](docs/ANALYTICAL_STORY.md)

## Learning pack สำหรับคนมาจาก AI Engineer

1. [`docs/DATA_ENGINEERING_LEARNING_GUIDE.md`](docs/DATA_ENGINEERING_LEARNING_GUIDE.md)
   — ภาพรวม layers, trade-off และความรู้ที่ควรเติม
2. [`docs/INCREMENTAL_WATERMARK.md`](docs/INCREMENTAL_WATERMARK.md) — release,
   retry, late data และ correction
3. [`docs/PRACTICE_EXERCISES.md`](docs/PRACTICE_EXERCISES.md) — แบบฝึกหัดพร้อม
   expected evidence
4. [`docs/INTERVIEW_GUIDE_AI_TO_DATA.md`](docs/INTERVIEW_GUIDE_AI_TO_DATA.md)
   — แนวตอบสัมภาษณ์และ project pitch
5. [`docs/NEW_PROJECT_PLAYBOOK.md`](docs/NEW_PROJECT_PLAYBOOK.md) — วิธีเริ่ม
   โปรเจกต์ data ใหม่ในทีมจริง

## Test และขอบเขต

```powershell
python -m pytest tests/unit
$env:RUN_PUBLIC_INTEGRATION = "1"
$env:RUN_FULL_INTEGRATION = "1"
python -m pytest tests/integration
python -m ruff check .
```

CI ตรวจ lint, JSON/YAML, compilation, unit tests และ build image โดยไม่ใช้
production credentials ส่วน cloud storage, Spark, streaming, IAM, alerting,
secret management และ automated rollback เป็น production extensions ที่แยกไว้
อย่างชัดเจน

อย่า commit `.env`, credentials, generated database files หรือ runtime output
