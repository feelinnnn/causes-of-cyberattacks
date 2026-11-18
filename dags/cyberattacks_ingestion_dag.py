from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import timedelta

from src.cyberattacks.pipeline import (
    _settings,
    initialize_database,
    run_cloudflare,
    run_csv,
    run_world_bank,
)
from datetime import datetime, timezone


def initialize():
    database_path, schema_path, _ = _settings()
    initialize_database(database_path, schema_path)


def cloudflare():
    database_path, _, _ = _settings()
    run_cloudflare(database_path, datetime.now(timezone.utc).isoformat())


def world_bank():
    database_path, _, _ = _settings()
    run_world_bank(database_path, datetime.now(timezone.utc).isoformat())


def csv_files():
    database_path, _, csv_input_dir = _settings()
    run_csv(database_path, csv_input_dir, datetime.now(timezone.utc).isoformat())


with DAG(
    dag_id="cyberattacks_ingestion",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["cyberattacks", "ingestion"],
) as dag:
    initialize_database_task = PythonOperator(task_id="initialize_database", python_callable=initialize)
    ingest_cloudflare = PythonOperator(
        task_id="ingest_cloudflare",
        python_callable=cloudflare,
        retries=3,
        retry_delay=timedelta(minutes=2),
    )
    ingest_csv = PythonOperator(
        task_id="ingest_csv_files",
        python_callable=csv_files,
    )
    ingest_world_bank = PythonOperator(
        task_id="ingest_world_bank",
        python_callable=world_bank,
        retries=2,
        retry_delay=timedelta(minutes=1),
    )
    initialize_database_task >> [ingest_cloudflare, ingest_csv, ingest_world_bank]
