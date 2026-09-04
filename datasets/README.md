# Baseline Datasets

ไฟล์ในโฟลเดอร์นี้เป็น public baseline สำหรับ local deterministic demo โดยเก็บไว้พร้อม metadata เพื่อให้ parser และ pipeline ทดสอบซ้ำได้

| Dataset | File | Period | Sheets | SHA-256 |
|---|---|---|---:|---|
| OCSC government workforce | `ocsc/thai-gov-manpower-2567.4.xlsx` | FY 2567 / 2024 | 68 | `fcb9ee5644ee235031a0e363e42dc8a207b72248e8d8ac770e6b4de9afad7f9b` |
| CGD budget execution | `cgd/2026.07.03.xlsx` | as of 2026-07-03 / FY 2569 | 15 | `309ad096e8e1372968346f994d2912faa5e89e96a3d389552ea9f9e3b2c58e95` |

Baseline provenance and source-page URLs are recorded in [`config/source_manifest.json`](../config/source_manifest.json) and [`docs/PROVENANCE.md`](../docs/PROVENANCE.md)

ข้อควรระวัง: สองไฟล์เป็นคนละ reporting period และไม่ควรใช้ join เพื่อสรุปความสัมพันธ์เชิงเวลาโดยตรง
