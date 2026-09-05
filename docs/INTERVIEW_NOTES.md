# Interview Notes

## Thirty-second project story

“ผมต่อยอดประสบการณ์ AI Engineer ด้วยการทำ Thai Public Data Platform เพื่อแก้ปัญหา public-sector Excel ที่เป็น report สำหรับมนุษย์อ่าน ไม่ใช่ flat table ผมเก็บ raw evidence ถึงระดับ cell, แยก parser ตาม layout และกำหนด grain ก่อนโหลดเข้า PostgreSQL `raw → staging → core` จากนั้นให้ data-quality gate ตัดสินใจก่อนส่งข้อมูลที่ผ่านไป ClickHouse สำหรับ analyst query โดยใช้ SHA-256 ทำ source identity, versioned schema contract และทำ load ให้ rerun/backfill ได้โดยไม่ duplicate”

## Why this is a Data Engineer project

- source heterogeneity: parser ต้องเข้าใจ merged cells, multi-row headers และ total/subtotal
- data contracts: schema constraints และ natural grain ไม่ใช่แค่ `SELECT *`
- reliability: idempotency, transaction boundary, failed-run behavior และ retry-safe orchestration
- observability: run metadata, row counts, DQ results และ source lineage
- serving: PostgreSQL เป็น truth; ClickHouse เป็น read-optimized downstream
- maintainability: DAG บาง, business logic อยู่ใน package และมี unit/integration tests
- release operations: แยก manual/scheduled/backfill/replay และมี health view สำหรับอ่านสถานะ run

## Questions a reviewer may ask

### ทำไมเลือก PostgreSQL และ ClickHouse?

PostgreSQL เหมาะกับ canonical relational truth เพราะต้องการ PK/FK, transaction, unique grain และ run metadata ที่ตรวจสอบได้ ส่วน ClickHouse เหมาะกับ analytical serving ที่อ่าน/aggregate หนัก จึงแยก write authority ออกจาก read-optimized serving อย่างชัดเจน

### ทำไมเก็บ raw cell?

เพราะ Excel เป็น report layout การมี file hash อย่างเดียวบอกได้ว่าใช้ไฟล์อะไร แต่ไม่พอสำหรับตอบว่า parser อ่าน sheet/row/column ไหน การเก็บ non-empty cell ทำให้ audit และ debug ได้โดยไม่ต้องเดาโครงสร้างย้อนหลัง

### จะกัน duplicate อย่างไร?

ใช้ SHA-256 ระบุตัว source release และ unique natural grain ระบุหนึ่งแถวใน fact พร้อม run id สำหรับ execution attempt เมื่อ rerun bytes เดิมจะเก็บ operational evidence ได้ แต่ไม่สร้าง canonical fact ซ้ำ

### ถ้า DQ ไม่ผ่านจะทำอย่างไร?

เก็บ raw/staging/ops evidence และ mark run failed แต่ไม่ publish core หรือ ClickHouse การ fail closed สำคัญกว่าการทำให้ dashboard มีข้อมูลบางส่วนโดยไม่รู้ว่าผิดตรงไหน

### ทำไมแยก disbursement กับ expenditure?

CGD รายงานสองมุมมองที่ไม่ใช่ metric เดียวกัน การรวมเป็น spend column เดียวจะทำให้ analyst ตีความผิด จึงเก็บ `report_type` และเขียน query ให้ filter ก่อน aggregate

### Join OCSC กับ CGD ได้เลยหรือไม่?

ได้เพียง exact normalized-name เป็น match candidate สำหรับ demo ชื่อหน่วยงานและ reporting period ต่างกัน Production ต้องมี reviewed agency master/alias mapping และต้องแสดงว่าค่ามาจากคนละ period

### ทำไมไม่เริ่ม Kafka/Spark/Kubernetes?

ไม่ใช่ bottleneck ของ one-day build ข้อมูลเป็น Excel batch และ P0 ต้องพิสูจน์ correctness, lineage, constraints, idempotency และ quality gate ก่อนเพิ่ม distributed infrastructure

### ถ้า source release ใหม่เข้ามาจะทำอย่างไร?

ระบบใช้ content hash เป็น release identity แทน filename ถ้า bytes เดิมถูกส่งซ้ำ
ระบบจะข้าม fact ที่มีอยู่แล้ว แต่ถ้าเป็น bytes ใหม่จะเก็บ raw/staging/core/serving
เป็น release ใหม่ โดยบันทึก `run_type=backfill` ได้เมื่อเป็นการแก้ไขข้อมูลย้อนหลัง

### ถ้า schema source เปลี่ยนจะทำอย่างไร?

parser output ต้องผ่าน versioned schema contract ก่อน staging การหายไปของ
required column เป็น breaking change และ fail closed ส่วน additive column ถูก
รายงานเป็น warning เพื่อให้ตัดสินใจอัปเดต contract อย่างมีเจตนา

## Evidence map

| Topic | Evidence |
|---|---|
| architecture | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| data model/grain | [`docs/DATA_MODEL.md`](DATA_MODEL.md) |
| data provenance and reproducibility | [`docs/PROVENANCE.md`](PROVENANCE.md) |
| DQ failure behavior | [`tests/fixtures/bad_data_quality.json`](../tests/fixtures/bad_data_quality.json) |
| execution order | [`docs/DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md) |

## Honest limitations

- baseline OCSC and CGD are not time-aligned
- exact-name mapping is not a production master data solution
- report formulas and totals still require source-specific semantic validation
- local Docker integration has been verified with both the CLI path and the full Airflow DAG
