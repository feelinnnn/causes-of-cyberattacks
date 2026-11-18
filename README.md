# Causes of Cyberattacks

โครงสร้างเริ่มต้นสำหรับ data engineering pipeline ที่รองรับการนำเข้าข้อมูลจาก
API และ CSV ด้วย Apache Airflow, Docker และ SQLite

## โครงสร้างโปรเจค

```text
.
├── dags/
│   └── cyberattacks_ingestion_dag.py
├── data/
│   ├── input/
│   │   └── sample_cyberattacks.csv
│   └── warehouse/
├── sql/
│   └── schema.sql
├── src/cyberattacks/
│   ├── api_client.py
│   ├── csv_loader.py
│   ├── database.py
│   └── pipeline.py
├── tests/
│   └── test_pipeline.py
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## เริ่มต้นใช้งาน

```bash
cp .env.example .env
docker compose up --build
```

เปิด Airflow ที่ <http://localhost:8080> แล้วใช้บัญชีที่แสดงใน log:

```bash
docker compose logs airflow
```

จากนั้นเปิดใช้งาน DAG ชื่อ `cyberattacks_ingestion`. ข้อมูลจะถูกเก็บใน
`data/warehouse/cyberattacks.db` ซึ่งเปิดดูได้ด้วย SQLite:

```bash
sqlite3 data/warehouse/cyberattacks.db
```

หากต้องการรัน ingestion โดยไม่ใช้ Airflow:

```bash
docker compose run --rm airflow python -m src.cyberattacks.pipeline
```

## การตั้งค่า

แก้ค่าใน `.env`:

- `API_URL`: endpoint ที่คืนค่า JSON เป็นรายการข้อมูล หรือ object ที่มี key `data`
- `API_TIMEOUT_SECONDS`: timeout ของการเรียก API
- `CLOUDFLARE_API_TOKEN`: token สำหรับตรวจสอบสิทธิ์ Cloudflare (เก็บเฉพาะใน `.env`)
- `CLOUDFLARE_VERIFY_URL`: endpoint สำหรับตรวจสอบ token
- `CSV_INPUT_DIR`: โฟลเดอร์ CSV ภายใน container ระบบจะอ่านทุกไฟล์ `.csv`
- `SQLITE_PATH`: path ของฐานข้อมูล SQLite ภายใน container

ถ้า `API_URL` ว่าง pipeline จะข้าม API และยังนำเข้า CSV ต่อได้

สำหรับ Cloudflare Radar ให้กำหนดค่า:

```env
API_URL=https://api.cloudflare.com/client/v4/radar/attacks/layer7/top/attacks?limit=200&dateRange=1d&format=json
CLOUDFLARE_API_TOKEN=ใส่_token_ใหม่ที่หมุนแล้ว
```

สำหรับ World Bank ต้องระบุรหัส `indicator` ด้วย เพราะ URL ที่ลงท้ายด้วย
`/indicator/` อย่างเดียวจะเกิดข้อผิดพลาด `Invalid value`:

```env
WORLD_BANK_URL=https://api.worldbank.org/v2/country/all/indicator
WORLD_BANK_INDICATOR=IT.NET.USER.ZS,NY.GDP.MKTP.CD
WORLD_BANK_DATE_RANGE=2022:2024
WORLD_BANK_COUNTRY_LIMIT=50
```

pipeline จะเรียก URL ในรูปแบบ
`.../indicator/{indicator}?date=2022:2024&format=json` แยกทีละ indicator
และบันทึกผลลงตาราง `world_bank_records`

World Bank จะโหลดรายชื่อประเทศ 50 ประเทศแรก แล้วเรียก API แยกทีละประเทศ
สำหรับแต่ละ indicator พร้อม retry แบบ exponential backoff 2, 4 และ 8 วินาที

ไฟล์ CSV จริงให้วางใน `data/input/` ระบบจะอ่านทุกไฟล์แบบทีละ batch
และเก็บข้อมูลดิบทุกคอลัมน์ไว้ในตาราง `raw_csv_records` เพื่อให้ทีมถัดไป
ทำความสะอาดข้อมูลได้โดยไม่เสียข้อมูลต้นฉบับ

ตัวอย่าง indicator:

- `IT.NET.USER.ZS`: ผู้ใช้อินเทอร์เน็ตเป็นสัดส่วนของประชากร
- `NY.GDP.MKTP.CD`: GDP มูลค่าปัจจุบัน (ดอลลาร์สหรัฐ)

World Bank ไม่มีตัวชี้วัดสัดส่วนการค้าออนไลน์แบบสากลในชุดนี้โดยตรง
จึงใช้ GDP เป็นตัวแทนปัจจัยด้านเศรษฐกิจ และสามารถเพิ่ม indicator อื่นคั่นด้วย comma ได้

> Endpoint `user/tokens/verify` ใช้ตรวจสอบว่า token ใช้งานได้เท่านั้น
> ยังไม่ใช่ endpoint ที่ส่งข้อมูล cyberattacks กลับมา หากต้องการนำเข้าข้อมูล
> Cloudflare จริง ต้องกำหนด `API_URL` เป็น endpoint ของ resource ที่ต้องการอ่าน
> และปรับรูปแบบข้อมูลให้ตรงกับ schema ในขั้นตอนถัดไป

Endpoint นี้ให้ข้อมูลแบบจัดอันดับ (ไม่ใช่ event โจมตีดิบทุก request)
โดยรองรับสูงสุด 200 รายการต่อคำขอ ระบบจึงใช้ `limit=200&dateRange=1d`
และ DAG จะทำงานทุกวันเพื่อสะสม snapshot รายวันไว้ใน SQLite การตั้ง
`dateRange=3y` ใช้กับ endpoint นี้ไม่ได้ หากต้องการข้อมูลย้อนหลัง 3 ปี
ต้องมี historical export หรือ endpoint/แผนบริการ Cloudflare ที่รองรับ
การกำหนดช่วงวันที่ย้อนหลัง แล้วจึงทำ backfill แยกต่างหาก

ห้ามใส่ token จริงใน source code, command history หรือ commit หาก token ถูกเปิดเผย
แล้วให้ revoke/rotate ใน Cloudflare ก่อนนำไปใช้ใน `.env`