# Project Architecture

> Only the parts that do not depend on which datasets we pick.
> Research questions, table schemas, data quality rules and features are added
> **after** the team selects sources.

## Data folders
| Folder | What is inside | Rule |
|---|---|---|
| `data/raw/<source>/<download_date>/` | Original files exactly as downloaded / returned by API | Never edited; new download = new date folder |
| `data/cleaned/<source>/` | One cleaned table per source | Fix types, missing values, duplicates, country names → codes |
| `data/integrated/` | All sources joined into one table | Join keys decided after data selection |
| `data/analytical/` | Final dataset for EDA, models, web app | Also loaded into the database |

## Workflow (full)
```
[0] เริ่มต้น — ตัดสินใจก่อนลงมือ (คน)
    0.1 เลือกแหล่งข้อมูล A–E (source, license, ช่วงเวลา)
    0.2 ตั้ง Research Questions
    0.3 ร่าง Hypothesis (H0 / H1) จาก RQ  ← ตั้งก่อน แต่ทดสอบหลัง EDA

[Airflow DAG] — กดรันครั้งเดียว อัปเดตทุกอย่าง (รันซ้ำได้ ผลเหมือนเดิม)
  Data Engineering
    1. ดาวน์โหลด (Python / API / ไฟล์)                 → data/raw/
    2. ทำความสะอาด (PySpark)                            → data/cleaned/
    3. แปลง + join ทุกแหล่ง (PySpark)                  → data/integrated/
    4. ตรวจคุณภาพตาม DQ rules (PySpark)               → data/analytical/ + DQ report
       ไม่ผ่าน = DAG หยุด ไม่มี task ไหนหลังจากนี้ทำงาน
    5. โหลดเข้า Database (SQLite)
  Data Science (scripts ใน src/analysis/, query จาก DB)
    6. สร้างกราฟ EDA                                    → reports/figures/
    7. รัน hypothesis tests                             → DB: hypothesis_results
    8. สร้าง features                                   → DB: features
    9. train baseline + models, evaluate (split ตามเวลา) → DB: model_metrics
   10. คำนวณ feature importance                         → DB: feature_importance

[คน] — ทำระหว่างพัฒนา แล้วเขียนผลการตัดสินใจลงเป็นโค้ดใน DAG
    • ดู EDA → ถ้าเจอปัญหาข้อมูล ย้อนไปแก้ขั้น 2
    • เลือก statistical test ให้เหมาะกับข้อมูล (ขั้น 7)
    • เลือก feature ที่ EDA/hypothesis ชี้ว่ามีประโยชน์ (ขั้น 8)
    • เลือก model + metric พร้อมเหตุผล (ขั้น 9)
    • Interpretation: อ่านผล อธิบายข้อค้นพบ ข้อจำกัด (ไม่ automate)

[นำเสนอ]
   11. Web app (query จาก DB — ข้อมูลจริงเท่านั้น, refresh แล้วเห็นผลรันล่าสุด)
   12. Report 7–12 หน้า + Presentation/Live demo
       Demo: กดรัน DAG → Raw → Pipeline → Analytical Dataset → Model → Result บนเว็บ
```

Notes
- เขียนตาราง DB แบบแทนที่ทั้งตารางใน transaction เดียว เว็บที่เปิดอยู่จะไม่เห็นข้อมูลครึ่ง ๆ
- ตัวเลขอัปเดตอัตโนมัติ แต่ข้อสรุปไม่ — ถ้าผลเปลี่ยนมาก ต้องอ่านและตีความใหม่

## To be decided after data selection
- [ ] Research questions & hypotheses
- [ ] Unit of analysis (e.g. country × year) and join keys
- [ ] Table schemas & data dictionary
- [ ] Data quality rules (≥ 4)
- [x] Database: SQLite (file-based, web can read while DAG writes)
