# Development Plan

## Working agreement

นี่คือแผน portfolio build ที่เน้น P0 ให้พิสูจน์ engineering fundamentals ก่อน แล้วค่อยพิจารณา optional work เมื่อ core ผ่านทั้งหมด

กติกาหลักคือทำให้ทุก phase จบด้วย evidence ที่ตรวจได้ และไม่เริ่มงานนอก scope ก่อน P0 จะ green

## Phase plan

| Phase | งาน | ผลลัพธ์ที่ต้องตรวจได้ | สถานะ |
|---|---|---|---|
| 0 | workspace bootstrap, Git, source audit, safety review | canonical root, governance docs, baseline files, reuse boundary | **เสร็จ** |
| 1 | PostgreSQL schema contract → DDL | `raw`, `staging`, `core`, `ops`, constraints, migrations | **เสร็จ** |
| 2 | source ingestion | file identity, raw landing, workbook/sheet/cell evidence | **เสร็จ** |
| 3 | source transforms | OCSC workforce facts และ CGD budget facts ตาม grain | **เสร็จ** |
| 4 | quality checks + gate | bad fixture หยุด downstream publishing | **เสร็จ** |
| 5 | core publish + idempotency | transaction-safe publish และ rerun evidence | **เสร็จ** |
| 6 | ClickHouse serving | serving tables/read model จาก core ที่ผ่าน gate | **เสร็จ** |
| 7 | Airflow DAG | task dependency ตาม contract; DAG บาง | **เสร็จ** |
| 8 | analytical SQL + smoke tests | 4 analytical questions และ caveat | **เสร็จ** |
| 9 | Docker/CI/docs/demo | clean setup, CI, README walkthrough | **เสร็จ; Docker integration pending local daemon** |

## Suggested one-day execution timebox

| Window | Focus | Stop condition |
|---|---|---|
| 0:00–0:30 | approve reuse boundary and schema contract | no unresolved table-grain ambiguity |
| 0:30–2:00 | PostgreSQL DDL + local runtime health | schemas and constraints apply cleanly |
| 2:00–4:30 | adapt OCSC/CGD parser logic | baseline rows and raw evidence are deterministic |
| 4:30–6:00 | DQ contract and tests | bad fixture fails gate; good fixture passes |
| 6:00–7:30 | idempotent core publish | two identical runs do not duplicate data |
| 7:30–8:30 | ClickHouse serving and SQL | all four questions return documented results |
| 8:30–9:30 | Airflow DAG and Docker flow | DAG parses and dependencies are clear |
| 9:30–10:00 | CI, safety scan, README walkthrough | reproducible handoff and no secret artifacts |

## Definition of ready for the next phase

- `docs/PROVENANCE.md` data identity and reproducibility documented
- PostgreSQL/ClickHouse boundary implemented
- exact natural grain for each source confirmed
- baseline files and period caveat accepted
- no need to introduce Kafka/Spark/Kubernetes/Terraform to meet P0

## Definition of done

ดู acceptance criteria ใน [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) และ execution checklist ใน [`QA_CHECKLIST.md`](QA_CHECKLIST.md)

## Known risks and response

| Risk | Response |
|---|---|
| Excel layout เปลี่ยน | เก็บ raw sheet/cell evidence และ fail เมื่อ expected structure ไม่พบ |
| source มี total/subtotal ปะปน | tag `entity_type` และกำหนด query filter/ reconciliation ให้ชัด |
| ชื่อหน่วยงานข้าม source ไม่ตรงกัน | exact normalized name ใช้ได้เพียงเป็น candidate; production ต้องมี reviewed master mapping |
| source periods ต่างกัน | แสดง period ทุก query และห้าม time-aligned inference |
| Docker image/dependency ใช้เวลานาน | ให้ local Python tests เป็นหลักและ lock scope ที่ P0 |
| quality warning ถูกมองข้าม | severity/threshold ที่เป็น gate ต้อง fail closed และไม่ publish downstream |
