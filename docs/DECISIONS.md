# Decisions

บันทึกนี้เป็น index ของ architectural decisions ที่มีผลต่อการทำงานต่อใน repository

## D-001 — PostgreSQL เป็น canonical relational truth

**Status:** accepted

ใช้ PostgreSQL เป็นเจ้าของข้อมูล `raw`, `staging`, `core` และ referential integrity เพราะระบบเป้าหมายต้องมี transaction, PK/FK, unique grain และ numeric constraints ที่ตรวจสอบได้จากฐานข้อมูลเดียว

รายละเอียด: [`docs/adr/0001-postgresql-canonical-clickhouse-serving.md`](adr/0001-postgresql-canonical-clickhouse-serving.md)

## D-002 — ClickHouse เป็น analytical serving เท่านั้น

**Status:** accepted

ClickHouse รับข้อมูลที่ผ่าน quality gate จาก PostgreSQL core เพื่อการอ่าน/aggregate ไม่รับบทเป็น authoritative write model และสามารถ rebuild ได้

## D-003 — Local raw first; GCS optional

**Status:** accepted

local landing ทำให้ demo หนึ่งวัน deterministic และตรวจซ้ำได้ทันที ส่วน GCS จะทำหลัง P0 green เพื่อไม่เพิ่ม cloud credentials และ operational surface ก่อนจำเป็น

## D-004 — Preserve raw workbook evidence

**Status:** accepted

เก็บ source file metadata, sheet inventory และ non-empty cell coordinates/value เพื่อรองรับ audit และ debugging ของ Excel parser

## D-005 — Airflow DAG บาง

**Status:** accepted

DAG รู้จัก task dependency, retries และ run context เท่านั้น; parser, cleaning, transforms, DQ และ load behavior อยู่ใต้ `src/`

## D-006 — Quality gate fail closed

**Status:** accepted

เมื่อ blocking DQ check ไม่ผ่าน ต้องหยุด core/ClickHouse publishing แต่ยังเก็บ raw/staging/ops evidence เพื่อสืบสวนและ replay

## D-007 — SHA-256 เป็น source identity

**Status:** accepted

filename อาจเปลี่ยนแม้ content เดิมหรืออาจซ้ำกันคนละ content จึงใช้ SHA-256 เป็น unique content identity และใช้ run id แยก execution attempt

## D-008 — No scope creep in the first day

**Status:** accepted

Kafka, Spark, Kubernetes, Terraform, frontend, ML, LLM และ dashboard ที่ไม่จำเป็นถูกเลื่อนไว้ เพื่อรักษา P0 ที่พิสูจน์ความน่าเชื่อถือของ pipeline ได้จริง

## D-009 — Permissive staging, strict core

**Status:** accepted

staging ต้องเก็บ typed rejected values และ raw lineage ไว้ให้ DQ อธิบายได้
เมื่อ run ถูก block ขณะที่ `core` บังคับ numeric/range/unit constraints เต็มรูปแบบ
เพื่อไม่ให้ข้อมูลเสียถูก publish
