# คู่มือรัน Airflow (สำหรับเพื่อนในทีม)

คู่มือนี้พาตั้งแต่ clone repo จนเห็น DAG `cyber_pipeline` รันครบทุกกล่องใน Airflow
และได้ฐานข้อมูล `data/warehouse/cyberattacks.db` ที่มีทั้งข้อมูลและผลโมเดล

---

## 1. ภาพรวม: กดครั้งเดียวได้อะไร

```
ดึงผ่าน API:   ingest_cloudflare → raw_cloudflare → clean_cloudflare
               ingest_worldbank  → raw_worldbank  → clean_worldbank
โหลดมาเอง:                        raw_vdem       → clean_vdem
                                  raw_gci        → clean_gci
                                  raw_bgp        → clean_bgp
   (build_country_reference ทำรายชื่อประเทศก่อน clean_bgp / vdem / gci)

→ join → data_dictionary → dq_check → load_clean_data_to_db
→ features → train_models_v1 → train_models_v2 → online_ml
```

| กล่อง | ทำอะไร | บันทึกที่ไหน |
|---|---|---|
| `ingest_*` | ดึงข้อมูลใหม่จาก API (ข้ามไป ถ้าไม่ได้ตั้ง `RUN_INGEST=1`) | `data/raw/` |
| `raw_*` | เช็กว่าไฟล์ดิบที่ต้องใช้มีครบ และเขียนชื่อไฟล์ ขนาด จำนวนแถวลง log | (log ของ Airflow) |
| `clean_*`, `build_country_reference` | ทำความสะอาดข้อมูลทีละแหล่ง | `data/cleaned/` |
| `join` | รวมเป็นตารางประเทศ × ปี | `data/integrated/country_year.csv` |
| `data_dictionary` | สร้างเอกสารอธิบายคอลัมน์ | `docs/data_dictionary.md` |
| `dq_check` | ตรวจคุณภาพข้อมูล ถ้ากฎร้ายแรงไม่ผ่านจะหยุดทั้ง DAG | `reports/dq/` |
| `load_clean_data_to_db` | ยกข้อมูลที่ผ่าน DQ เข้า DB | `data/warehouse/cyberattacks.db` |
| `features` | สร้างปัจจัยของกลุ่มวิเคราะห์ (432 แถว) | DB ตาราง `features` + `data/analytical/` |
| `train_models_v1` | เทรนโมเดล V1 | DB `model_*` + `data/analytical/` |
| `train_models_v2` | เทรนโมเดล V2 | DB `*_v2` + `data/analytical/v2/` |
| `online_ml` | จำลอง Online ML รายเดือน 2022–2024 | DB `online_*` + `data/analytical/online/` |

---

## 2. สิ่งที่ต้องมีก่อน

- **Git**
- **Docker Desktop** (เปิดโปรแกรมไว้ก่อนรันคำสั่ง docker ทุกครั้ง)
- พื้นที่ว่างประมาณ 5 GB (image ของ Airflow + Java + ข้อมูล)
- **ไฟล์ข้อมูลดิบ `data/raw/`**: ไม่ได้อยู่บน GitHub (ไฟล์ใหญ่ และบางแหล่งห้ามแจกต่อ) ขอโฟลเดอร์ `raw` จากหัวหน้าทีม

---

## 3. ติดตั้ง (ทำครั้งแรกครั้งเดียว)

### 3.1 Clone และดึงโค้ดล่าสุด
```
git clone https://github.com/feelinnnn/causes-of-cyberattacks.git
cd causes-of-cyberattacks
git checkout main
git pull origin main
```

### 3.2 วางไฟล์ข้อมูลดิบ
เอาโฟลเดอร์ `raw` ที่ได้มาไปวางที่ `data/raw/` ให้โครงสร้างเป็นแบบนี้ (กล่อง `raw_*` เช็กไฟล์ตามรายการนี้)

```
data/raw/
├── sourceA/cloudeflare_rader/
│   ├── cloudflare_radar_source_a.csv
│   ├── cloudflare_attack_flow_pairs.csv
│   └── cloudflare_timeseries_weekly.csv
├── sourceB/world_bank_econ_pred.csv
├── sourceC/
│   ├── world_bank_digi_found.csv
│   ├── BGP/routeviews-rv2-2022/2023/20240701-*.pfx2as.gz
│   └── ip24prefix/2022/2023/2024070*.as-org2info.txt.gz
└── sourceE/
    ├── GCI_2018_Raw.csv, GCI_2020_Raw.csv, GCI_2024_Raw.csv
    ├── V-Dem-CY-Full+Others-v16.csv
    └── world_bank_gov_wgi.csv
```
หมายเหตุ: ชื่อโฟลเดอร์ `cloudeflare_rader` สะกดแบบนี้จริง อย่าแก้

### 3.3 ไฟล์ `.env` (ไม่บังคับ)
ถ้าไม่สร้าง ก็รันได้ตามปกติ (ใช้ไฟล์ใน `data/raw/` ที่มีอยู่) สร้างเฉพาะเมื่ออยากให้ Airflow ดึงข้อมูลใหม่จาก API

สร้างไฟล์ `.env` ที่โฟลเดอร์บนสุดของโปรเจกต์:
```
RUN_INGEST=1
CLOUDFLARE_API_TOKEN=ใส่ token ของตัวเอง
```
- `.env` อยู่ใน `.gitignore` แล้ว **ห้าม commit** และห้ามส่ง token ให้ใคร
- ดึงใหม่จะเขียนทับไฟล์ใน `data/raw/` ผลโมเดลอาจไม่ตรงกับในสไลด์ ควร backup `data/raw` ก่อน

### 3.4 Build และเปิด Airflow
```
docker compose build
docker compose up -d
```
ครั้งแรกใช้เวลาหลายนาที (ติดตั้ง Java, PySpark, scikit-learn, scipy)

---

## 4. Login

เปิด http://localhost:8080

- **Username:** `admin`
- **Password:** รอประมาณ 1 นาทีหลัง `up -d` แล้วรัน
  ```
  docker exec cyberattacks-airflow cat /opt/airflow/standalone_admin_password.txt
  ```

ถ้าขึ้น `No such file or directory` (เกิดได้หลัง build ใหม่ เพราะ user มีอยู่แล้วใน `.airflow/`) ให้ตั้งรหัสเอง:
```
docker exec cyberattacks-airflow airflow users reset-password --username admin --password รหัสที่อยากได้
```

---

## 5. รัน DAG

1. กดชื่อ DAG **`cyber_pipeline`**
2. กดปุ่ม ▶ (มุมขวาบน) → **Trigger DAG**
3. กดแท็บ **Graph** เพื่อดูความคืบหน้า

| สีกล่อง | ความหมาย |
|---|---|
| เขียวเข้ม | สำเร็จ |
| เขียวอ่อน | กำลังรัน |
| ชมพู | ข้าม (`ingest_*` จะข้ามถ้าไม่ได้ตั้ง `RUN_INGEST=1` เป็นเรื่องปกติ) |
| แดง | พัง → คลิกกล่อง → **Logs** |

**เวลาที่ใช้ทั้ง DAG ประมาณ 30–40 นาที** ส่วนที่นานคือ `train_models_v1` (~6 นาที) และ `train_models_v2` (~20 นาที)
เพราะ Airflow ตั้งเป็น SequentialExecutor ทำได้ทีละกล่อง และโมเดลใช้ GridSearch + permutation importance

ระหว่างรัน:
- รีเฟรช / ปิดหน้าเว็บได้ งานรันใน Docker ไม่หยุด
- **อย่า** `docker compose down` หรือปิด Docker Desktop
- **อย่า** กด Clear / Mark Failed ที่กล่อง

ดูรายละเอียดแต่ละกล่อง: คลิกกล่อง → **Task Instance Details** (มีคำอธิบายว่าบันทึกตารางอะไร)
ดูว่าใช้ไฟล์ดิบไฟล์ไหน: คลิกกล่อง `raw_*` → **Logs** จะเห็นบรรทัด `OK  sourceE/GCI_2024_Raw.csv (… rows, modified …)`

---

## 6. ผลลัพธ์อยู่ไหน

Docker ผูกโฟลเดอร์ `data/`, `reports/`, `docs/`, `logs/` ไว้กับเครื่องเรา ผลจึงอยู่ในเครื่องทันที

| ผล | ที่อยู่ |
|---|---|
| ข้อมูล clean | `data/cleaned/` |
| ตารางประเทศ × ปี | `data/integrated/country_year.csv` (753 แถว × 59 คอลัมน์) |
| รายงาน DQ | `reports/dq/dq_summary.md` |
| ผลโมเดล V1 | `data/analytical/model_metrics.csv` ฯลฯ |
| ผลโมเดล V2 | `data/analytical/v2/` |
| ผล Online ML | `data/analytical/online/` |
| **ฐานข้อมูล** | `data/warehouse/cyberattacks.db` |

---

## 7. เปิดดูฐานข้อมูล

ไฟล์ `data/warehouse/cyberattacks.db` เป็น SQLite ไฟล์เดียว

**วิธีที่ง่ายสุด: DB Browser for SQLite** (ดาวน์โหลดที่ sqlitebrowser.org)
1. Open Database → เลือก `cyberattacks.db`
2. แท็บ **Browse Data** → เลือกตาราง
3. แท็บ **Execute SQL** ถ้าจะ query เช่น `SELECT * FROM model_metrics_v2 LIMIT 20;`

ทางอื่น: VS Code ติดตั้ง extension **SQLite Viewer** แล้วคลิกไฟล์ `.db`

**ตารางที่ควรเห็นหลังรันครบ**

| กลุ่ม | ตาราง | มาจากกล่อง |
|---|---|---|
| ข้อมูล clean | `cleaned_*` (11 ตาราง) | load_clean_data_to_db |
| ตารางรวม | `country_year` | load_clean_data_to_db |
| คุณภาพ/ประวัติ | `dq_results`, `cleaning_log`, `pipeline_runs` | load_clean_data_to_db |
| ปัจจัย | `features`, `features_v2` | features, train_models_v2 |
| ผลโมเดล V1 | `model_metrics`, `feature_importance`, `model_predictions` | train_models_v1 |
| ผลโมเดล V2 | `model_metrics_v2`, `feature_importance_v2`, `model_predictions_v2` | train_models_v2 |
| Online ML | `online_metrics_summary`, `online_replay_log`, `online_drift_events`, `online_coef_evolution`, `online_predictions` | online_ml |

ทุกตารางเขียนแบบ replace: รันกี่รอบก็ไม่มีข้อมูลซ้ำ

---

## 8. แก้ปัญหาที่เจอบ่อย

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| `scipy` / `scikit-learn is not recognized` ใน cmd | ไม่ใช่คำสั่ง เป็นชื่อแพ็กเกจใน `requirements-airflow.txt` ให้ `docker compose build` ใหม่ |
| `ModuleNotFoundError: sklearn` ในกล่องโมเดล | image เก่า → `docker compose build` แล้ว `docker compose up -d` |
| ไม่มีรหัส login | ดูหัวข้อ 4 (reset-password) |
| แก้ DAG แล้วกล่องใน Graph ไม่เปลี่ยน | Airflow อ่านไฟล์ DAG ใหม่หลังรอบที่กำลังรันจบ รอให้จบแล้วรีเฟรช |
| กล่อง `raw_*` แดง: `Missing raw files` | ไฟล์ใน `data/raw/` ไม่ครบ / ชื่อผิด ดูหัวข้อ 3.2 |
| `dq_check` แดง | ข้อมูลไม่ผ่านกฎร้ายแรง ดู `reports/dq/dq_summary.md` |
| `database is locked` | มีโปรแกรมเปิด DB ค้างไว้ (เช่น DB Browser) ปิดก่อนแล้วรันกล่องนั้นใหม่ |
| port 8080 ถูกใช้ | ปิดโปรแกรมที่ใช้ port 8080 หรือแก้ `ports` ใน `docker-compose.yml` |
| `ingest_*` สีชมพู | ปกติ: ไม่ได้ตั้ง `RUN_INGEST=1` จึงใช้ไฟล์ดิบที่มีอยู่ |

ปิด Airflow เมื่อเลิกใช้:
```
docker compose down
```
(ข้อมูล, DB และ user login ยังอยู่ เปิดใหม่ด้วย `docker compose up -d`)

---

## 9. ไฟล์ที่เกี่ยวข้อง

| ไฟล์ | เนื้อหา |
|---|---|
| `dags/cyber_pipeline_dag.py` | ลำดับกล่องทั้งหมดใน Airflow |
| `docker-compose.yml`, `Dockerfile`, `requirements-airflow.txt` | ตั้งค่า container |
| `src/cyber_pipeline/` | clean, join, DQ, load DB |
| `src/analysis/train_models.py` | โมเดล V1 |
| `src/analysis/train_models_v2.py` | โมเดล V2 |
| `src/analysis/online_ml.py` | Online ML |
| `docs/feature_engineering_plan.md`, `docs/online_ml_plan.md` | แผนของงานโมเดล |
