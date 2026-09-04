# Thai Public Data Context

อภิธานศัพท์กลางของ Thai Public Data Platform เพื่อให้คำว่า source, period, grain และ metric มีความหมายเดียวกันตลอด pipeline และ analytical layer

## Source and time

**Public source**:
ข้อมูลที่หน่วยงานรัฐเผยแพร่ต่อสาธารณะและสามารถอ้างอิงกลับไปยังหน้าเผยแพร่หรือไฟล์ต้นฉบับได้
_Avoid_: official truth (ไฟล์สาธารณะอาจมีข้อผิดพลาดหรือความหมายที่ต้องยืนยันกับเจ้าของข้อมูล)

**Source release**:
ไฟล์หรือชุดไฟล์หนึ่งชุดที่เผยแพร่ ณ release เดียวกันและใช้เป็น snapshot ของข้อมูลต้นทาง
_Avoid_: live table, current truth

**Reporting period**:
ช่วงเวลาที่ตัวเลขใน source อธิบาย เช่น ปีงบประมาณหรือวันที่ snapshot ไม่ใช่เวลาที่ pipeline โหลดข้อมูล
_Avoid_: ingestion date

**As-of date**:
วันที่ที่รายงานระบุว่าตัวเลขมีผล ณ วันนั้น โดยเฉพาะรายงาน budget execution ของ CGD
_Avoid_: loaded date, publish timestamp

## Grain and measures

**Reporting grain**:
สิ่งที่หนึ่งแถวแทนจริง ๆ เช่น source release × sheet × entity × metric หรือ source release × entity × report type × expense category
_Avoid_: row count, record size

**Entity**:
หน่วยงานหรือขอบเขตที่รายงานกล่าวถึง เช่น ministry, agency, province หรือ total
_Avoid_: customer, account

**Budget execution**:
ตัวเลขด้านงบประมาณที่ source แยกเป็นมุมมอง เช่น budget, allocation, disbursement และ expenditure ซึ่งอาจมีความหมายต่างกัน
_Avoid_: revenue, spend (เมื่อยังไม่ได้กำหนดนิยาม)

**Workforce metric**:
ตัวชี้วัดกำลังพลหนึ่งรายการของ entity เช่น จำนวนข้าราชการ, กลุ่มอายุ, เพศ หรือระดับการศึกษา
_Avoid_: employee row (เพราะหนึ่ง entity มีหลาย metric)

**Published total**:
ยอดรวมที่ source รายงานไว้เองและเก็บไว้เพื่อ reconciliation กับ detail rows
_Avoid_: calculated total (เว้นแต่ระบุว่าเป็นยอดที่คำนวณใน platform)

## Quality and identity

**Source identity**:
ตัวตนของ source release ที่ผูกกับเนื้อหาไฟล์ด้วย SHA-256 และ metadata ของ dataset
_Avoid_: filename only

**Data-quality gate**:
จุดตัดสินใจที่ตรวจว่า staging data ผ่าน contract ก่อนอนุญาตให้ publish เป็น core หรือ analytical serving data
_Avoid_: warning log, best effort publish

**Agency mapping candidate**:
คู่ชื่อ entity ที่อาจเป็นหน่วยงานเดียวกันข้าม source แต่ยังไม่ใช่ master mapping ที่รับรองแล้ว
_Avoid_: automatically correct join
