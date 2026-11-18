"""Airflow DAG: raw files -> cleaned (one task per source) -> integrated -> data dictionary -> DQ -> SQLite.

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
    t_load = PythonOperator(task_id="load_sqlite", python_callable=load_sqlite)

    # Later steps plug in after load_sqlite: eda_figures, hypothesis_tests, features, models.
    [t_ing_cf, t_ing_wb] >> t_ref
    t_ing_cf >> t_c_cf
    t_ing_wb >> t_c_wb
    t_ref >> [t_c_bgp, t_c_vdem, t_c_gci]
    [t_c_cf, t_c_wb, t_c_bgp, t_c_vdem, t_c_gci] >> t_join >> t_dict >> t_dq >> t_load
