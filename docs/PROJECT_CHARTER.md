# Project Charter — Thai Public Data Platform

## Project intent

สร้างผลงาน portfolio แบบ end-to-end ที่ต่อยอดประสบการณ์ AI Engineer ไปสู่งาน
Data Engineering และ Data Analytics โดยแสดงให้เห็นว่าเราสามารถนำ public-sector
Excel reports ที่ออกแบบเพื่อให้มนุษย์อ่าน มาเปลี่ยนเป็นข้อมูลที่โหลดซ้ำได้
ตรวจสอบย้อนกลับได้ และส่งต่อให้ analyst ใช้งานได้อย่างปลอดภัย

## Target role

**AI Engineer / Data Engineer / Data Analyst portfolio**

## Problem statement

OCSC และ CGD เผยแพร่ข้อมูลใน workbook ที่มีหลาย sheet, merged cells, multi-row headers, formula, subtotal/total และรูปแบบต่างกันระหว่างแหล่งข้อมูล การอ่านเข้า database โดยตรงจะเสี่ยงต่อการตีความผิด, duplicate, double count และไม่สามารถ trace กลับไปยัง cell ต้นทางได้

## Outcomes

1. มี Python source adapters แยกตาม layout ของ OCSC และ CGD
2. มี raw evidence ระดับ source file, sheet และ cell
3. มี PostgreSQL layers `raw`, `staging`, `core` และ operational schema `ops`
4. มี transaction-safe, idempotent load ที่ใช้ SHA-256 source identity
5. มี quality gate ที่ fail closed และป้องกัน downstream publish เมื่อข้อมูลเสีย
6. มี ClickHouse serving model และ analytical SQL ที่กำหนด grain ก่อน aggregate
7. มี Airflow DAG ที่ทำหน้าที่เฉพาะ orchestration
8. มี tests, CI และ documentation ที่ reviewer เปิดตามได้

## In scope — P0

- Python 3.11+ และ `openpyxl`/`pandas` สำหรับ ingestion/transform
- Local raw landing ที่ออกแบบให้เพิ่ม GCS ได้ภายหลัง
- PostgreSQL เป็น canonical relational truth
- ClickHouse เป็น analytical serving layer
- Apache Airflow บน Docker Compose
- SHA-256, run metadata, idempotency และ lineage
- Required data-quality checks ตาม contract
- Analytical SQL สำหรับ budget allocation, below-median disbursement, workforce distribution และ budget-to-workforce ratio
- Unit/integration tests และ GitHub Actions CI

## Optional after core is green

- GCS object storage adapter
- source discovery automation ที่ไม่กระทบ deterministic local demo
- เพิ่ม monitoring/alerting เชิง production

## P1 production-hardening slice

- Versioned parser-output schema contract ที่ fail closed ก่อน staging
- Explicit operational run type สำหรับ manual, scheduled, backfill และ replay
- Multi-release integration evidence และ `ops.pipeline_run_health` view
- Analyst metric contract ที่ระบุ grain, filter และ caveat ก่อน aggregate

## Explicit non-goals for the one-day build

Kafka, Spark, Kubernetes, Terraform, frontend, ML, LLM และ dashboard ที่ไม่จำเป็นต่อ proof of engineering ไม่อยู่ใน scope วันนี้

## Acceptance criteria

- `python -m pytest` และ `python -m ruff check .` ผ่านใน clean environment
- สามารถอธิบาย grain และ lineage ของทุก fact table ได้
- source release เดิมโหลดซ้ำแล้วไม่สร้าง rows ซ้ำ
- bad-data fixture ทำให้ quality gate หยุด core/ClickHouse publish
- transaction ที่ fail ไม่ทิ้ง partial publish ไว้ใน canonical/serving layer
- PostgreSQL constraints ป้องกัน key, FK, duplicate grain และ invalid numeric values
- analytical SQL ไม่รวม total กับ detail หรือ disbursement กับ expenditure โดยไม่ตั้งใจ
- README อธิบาย setup, run, test, caveat และ architecture ได้ครบ
- ไม่มี secrets หรือ generated database artifacts ใน Git

## Domain caveat

Baseline OCSC เป็น FY 2567 / ค.ศ. 2024 ขณะที่ baseline CGD เป็น snapshot ปีงบประมาณ 2569 ณ 3 กรกฎาคม 2569 / ค.ศ. 2026 ดังนั้น cross-source analysis ต้องแสดง reporting period และไม่สรุปเป็น time-aligned causal comparison

## Current status

P0 implementation เสร็จแล้ว ครอบคลุม source parsing, raw/staging/core model,
DQ gate, idempotent serving, Airflow orchestration, analytical SQL, tests และ
local runbook โดยยังไม่ commit secrets หรือ push remote
