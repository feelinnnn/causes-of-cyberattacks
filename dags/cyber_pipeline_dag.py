"""Airflow DAG: raw files (one check box per source) -> cleaned (one task per source) -> integrated -> data dictionary -> DQ -> SQLite.

Run manually from the Airflow UI (schedule=None): the sources are yearly, so a daily
schedule would only repeat the same work. Every step overwrites its own outputs, so
re-running is safe.

Optional first step: re-fetch the API sources (Cloudflare, World Bank) with the scripts in
data/data_API/. Skipped unless RUN_INGEST=1 in .env (Cloudflare also needs CLOUDFLARE_API_TOKEN).
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.exceptions import AirflowFailException, AirflowSkipException
from airflow.operators.python import PythonOperator

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/opt/airflow")


# รันสคริปต์ดึงข้อมูลใหม่ 1 ตัว
# ถ้าไม่ได้เปิด RUN_INGEST=1 ไว้ใน .env จะข้ามไป แล้วใช้ไฟล์ที่มีอยู่แล้วแทน
def _fetch(script: str, needs_token: bool) -> None:
    """Re-download one source with its fetch script. Skipped unless RUN_INGEST=1, so a
    normal run uses the raw files already in data/raw/ (some sources are manual downloads)."""
    if os.environ.get("RUN_INGEST") != "1":
        raise AirflowSkipException("RUN_INGEST is not 1: using the raw files already in data/raw/")
    if needs_token and not os.environ.get("CLOUDFLARE_API_TOKEN"):
        raise AirflowFailException("RUN_INGEST=1 but CLOUDFLARE_API_TOKEN is not set in .env")
    subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "data", "data_API", script)], check=True)


# ขั้นดึงข้อมูล Cloudflare ใหม่ (ต้องมี token)
def ingest_cloudflare() -> None:
    _fetch("Cloudflare_Radar_SourceA.py", needs_token=True)


# ขั้นดึงข้อมูล World Bank ใหม่ทั้ง 3 ไฟล์
def ingest_worldbank() -> None:
    for script in ("WBank_Econ_Pred.py", "WBank_Digi_found.py", "WBank_Gov_WGI.py"):
        _fetch(script, needs_token=False)


# ---- กล่องข้อมูลดิบ: 1 กล่องต่อ 1 แหล่งข้อมูล ----
# เช็กว่าไฟล์ดิบที่ขั้น clean ต้องใช้มีอยู่จริงใน data/raw/ แล้วเขียนชื่อไฟล์ ขนาด จำนวนแถว
# และวันที่แก้ล่าสุดลง log ถ้าขาดไฟล์ไหน กล่องจะเป็นสีแดงและหยุดก่อนขั้น clean
# (API = ดึงด้วยสคริปต์ใน data/data_API/, manual = ดาวน์โหลดเองจากเว็บต้นทาง)
RAW_FILES = {
    "cloudflare": ["sourceA/cloudeflare_rader/cloudflare_radar_source_a.csv",
                   "sourceA/cloudeflare_rader/cloudflare_attack_flow_pairs.csv",
                   "sourceA/cloudeflare_rader/cloudflare_timeseries_weekly.csv"],          # API
    "worldbank": ["sourceB/world_bank_econ_pred.csv",
                  "sourceC/world_bank_digi_found.csv",
                  "sourceE/world_bank_gov_wgi.csv"],                                       # API
    "vdem": ["sourceE/V-Dem-CY-Full+Others-v16.csv"],                                      # manual
    "gci": ["sourceE/GCI_2018_Raw.csv", "sourceE/GCI_2020_Raw.csv",
            "sourceE/GCI_2024_Raw.csv"],                                                   # manual
    "bgp": [f"sourceC/BGP/routeviews-rv2-{y}0701-*.pfx2as.gz" for y in (2022, 2023, 2024)]
         + [f"sourceC/ip24prefix/{y}070*.as-org2info.txt.gz" for y in (2022, 2023, 2024)],  # manual (CAIDA)
}


# เช็กไฟล์ดิบของแหล่งข้อมูล 1 แหล่ง
def check_raw(source: str) -> None:
    import glob
    import logging
    log = logging.getLogger("airflow.task")
    raw = os.path.join(PROJECT_ROOT, "data", "raw")
    missing = []
    for pattern in RAW_FILES[source]:
        found = sorted(glob.glob(os.path.join(raw, pattern)))
        if not found:
            missing.append(pattern)
            continue
        for f in found:
            size_mb = os.path.getsize(f) / 1e6
            modified = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
            rows = ""
            if f.endswith(".csv"):
                with open(f, "rb") as fh:
                    rows = f", {sum(1 for _ in fh) - 1:,} rows"
            log.info("OK  %s  (%.1f MB%s, modified %s)", os.path.relpath(f, raw), size_mb, rows, modified)
    if missing:
        raise AirflowFailException(f"Missing raw files for {source}: {missing}")


# task: clean 1 source
# ขั้น clean แหล่งข้อมูล 1 แหล่ง
def clean(source: str) -> None:
    from cyber_pipeline.cleaning.run_cleaning import run_source
    run_source(source)


# ขั้นรวมทุกแหล่งข้อมูลเป็นตาราง country_year
def join() -> None:
    from cyber_pipeline.cleaning.run_cleaning import combine_logs
    from cyber_pipeline.transform.join import main
    combine_logs()
    main()


# ขั้นสร้างเอกสารอธิบายคอลัมน์
def data_dictionary() -> None:
    from cyber_pipeline.quality.data_dictionary import main
    main()


# ขั้นตรวจคุณภาพข้อมูล ถ้ามีข้อร้ายแรงไม่ผ่าน จะหยุดก่อนข้อมูลเสียเข้าฐานข้อมูล
def dq_check() -> None:
    from cyber_pipeline.quality.dq_checks import main
    if main() != 0:  # an "error" rule failed: stop before bad data reaches the database
        raise AirflowFailException("Data quality FAIL: see reports/dq/dq_summary.md")


# ขั้นเก็บผลทั้งหมดลงฐานข้อมูล
def load_sqlite() -> None:
    from cyber_pipeline.storage.load_sqlite import main
    main()


# ---- ต่อจากฐานข้อมูล: ปัจจัย -> โมเดล V1, V2 -> Online ML (โค้ดของ Art) ----
# ทุกขั้นเขียนตารางลง SQLite ไฟล์เดียวกัน (if_exists="replace") และเขียน CSV ลง data/analytical/

# สร้างปัจจัยของกลุ่มวิเคราะห์ -> ตาราง features
def features() -> None:
    from cyber_pipeline.transform.features import main
    main()


# โมเดล V1 -> ตาราง model_metrics, feature_importance, model_predictions
def train_models_v1() -> None:
    from analysis.train_models import main
    main()


# โมเดล V2 -> ตาราง features_v2, model_metrics_v2, feature_importance_v2, model_predictions_v2
def train_models_v2() -> None:
    from analysis.train_models_v2 import main
    main()


# Online ML (replay รายเดือน 2022-2024) -> ตาราง online_metrics_summary, online_replay_log,
# online_drift_events, online_coef_evolution, online_predictions
def online_ml() -> None:
    from analysis.online_ml import main
    main()


with DAG(
    dag_id="cyber_pipeline",
    description="Clean, join, document, check and load the cyberattack country-year data",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=1)},
    tags=["cyberattacks"],
) as dag:
    # 1. Ingest (optional, API sources only). V-Dem, GCI and CAIDA are manual downloads.
    t_ing_cf = PythonOperator(task_id="ingest_cloudflare", python_callable=ingest_cloudflare,
                              retries=3, retry_delay=timedelta(minutes=2))
    t_ing_wb = PythonOperator(task_id="ingest_worldbank", python_callable=ingest_worldbank,
                              retries=2, retry_delay=timedelta(minutes=1))

    # 1b. One box per raw data source: checks the files the cleaning step reads are in data/raw/.
    # Runs whether ingest ran or was skipped, so manual downloads get a box too.
    def raw_task(source: str) -> PythonOperator:
        return PythonOperator(task_id=f"raw_{source}", python_callable=check_raw,
                              op_kwargs={"source": source}, trigger_rule="none_failed", retries=0)

    t_raw_cf, t_raw_wb = raw_task("cloudflare"), raw_task("worldbank")   # API sources
    t_raw_vdem, t_raw_gci, t_raw_bgp = raw_task("vdem"), raw_task("gci"), raw_task("bgp")  # manual

    # 2. Clean each source separately (runs whether ingest ran or was skipped).
    # สร้างกล่องขั้นตอน clean ของแต่ละแหล่งข้อมูล
    # ทำงานได้แม้ขั้นดึงข้อมูลจะถูกข้าม
    def clean_task(source: str, task_id: str) -> PythonOperator:
        return PythonOperator(task_id=task_id, python_callable=clean, op_kwargs={"source": source},
                              trigger_rule="none_failed")

    t_ref = clean_task("reference", "build_country_reference")
    t_c_cf = clean_task("cloudflare", "clean_cloudflare")      # Source A
    t_c_wb = clean_task("worldbank", "clean_worldbank")        # Sources B, C, E (WDI, WGI)
    t_c_bgp = clean_task("bgp", "clean_bgp")                   # Source C (CAIDA)
    t_c_vdem = clean_task("vdem", "clean_vdem")                # Source E
    t_c_gci = clean_task("gci", "clean_gci")                   # Source E

    t_join = PythonOperator(task_id="join", python_callable=join)
    t_dict = PythonOperator(task_id="data_dictionary", python_callable=data_dictionary)
    t_dq = PythonOperator(task_id="dq_check", python_callable=dq_check, retries=0)
    t_load = PythonOperator(
        task_id="load_clean_data_to_db", python_callable=load_sqlite,
        doc_md="ยกข้อมูลที่ clean และผ่าน DQ แล้วเข้า DB (cleaned_*, country_year, dq_results, "
               "cleaning_log, pipeline_runs). ขั้นวิเคราะห์หลังจากนี้บันทึกผลลง DB เอง")

    # 3. Analysis (after the database is loaded). Run one after another: every step writes to
    # the same SQLite file, so running them in parallel could give "database is locked".
    t_feat = PythonOperator(task_id="features", python_callable=features,
                              doc_md="บันทึกผลลง DB เอง: ตาราง features และ data/analytical/features.csv")
    t_v1 = PythonOperator(task_id="train_models_v1", python_callable=train_models_v1,
                              doc_md="บันทึกผลลง DB เอง: model_metrics, feature_importance, model_predictions",
                          execution_timeout=timedelta(hours=1))
    t_v2 = PythonOperator(task_id="train_models_v2", python_callable=train_models_v2,
                              doc_md="บันทึกผลลง DB เอง: features_v2, model_metrics_v2, feature_importance_v2, model_predictions_v2",
                          execution_timeout=timedelta(hours=1))
    t_online = PythonOperator(task_id="online_ml", python_callable=online_ml,
                              doc_md="บันทึกผลลง DB เอง: online_metrics_summary, online_replay_log, online_drift_events, online_coef_evolution, online_predictions",
                              execution_timeout=timedelta(hours=1))

    t_ing_cf >> t_raw_cf
    t_ing_wb >> t_raw_wb
    [t_raw_cf, t_raw_wb, t_raw_gci] >> t_ref        # the country list is built from these files
    t_raw_cf >> t_c_cf
    t_raw_wb >> t_c_wb
    t_raw_bgp >> t_c_bgp
    t_raw_vdem >> t_c_vdem
    t_raw_gci >> t_c_gci
    t_ref >> [t_c_bgp, t_c_vdem, t_c_gci]
    [t_c_cf, t_c_wb, t_c_bgp, t_c_vdem, t_c_gci] >> t_join >> t_dict >> t_dq >> t_load
    t_load >> t_feat >> t_v1 >> t_v2 >> t_online
