from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from .api_client import fetch_records, verify_cloudflare_token
from .csv_loader import find_csv_files, read_records
from .database import (
    initialize_database,
    insert_api_records,
    insert_csv_records,
    insert_raw_csv_records,
    insert_world_bank_records,
)
from .world_bank_client import fetch_indicator

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _settings() -> tuple[str, str, str]:
    database_path = os.getenv(
        "SQLITE_PATH",
        os.path.join(PROJECT_ROOT, "data", "warehouse", "cyberattacks.db"),
    )
    schema_path = os.getenv(
        "SCHEMA_PATH", os.path.join(PROJECT_ROOT, "sql", "schema.sql")
    )
    csv_input_dir = os.getenv(
        "CSV_INPUT_DIR", os.path.join(PROJECT_ROOT, "data", "input")
    )
    return database_path, schema_path, csv_input_dir


def run_cloudflare(database_path: str, ingested_at: str) -> None:
    cloudflare_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    api_url = os.getenv("API_URL", "").strip()
    if not api_url:
        LOGGER.info("API_URL is empty; skipping Cloudflare ingestion")
        return
    if not cloudflare_token:
        raise RuntimeError("CLOUDFLARE_API_TOKEN is required when API_URL is configured")

    verification = verify_cloudflare_token(
        cloudflare_token,
        int(os.getenv("API_TIMEOUT_SECONDS", "30")),
        os.getenv(
            "CLOUDFLARE_VERIFY_URL",
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
        ),
    )
    LOGGER.info("Cloudflare token verified: %d result(s)", len(verification.get("result") or {}))
    records = fetch_records(api_url, int(os.getenv("API_TIMEOUT_SECONDS", "30")), cloudflare_token)
    insert_api_records(database_path, api_url, records, ingested_at)
    LOGGER.info("Inserted %d Cloudflare records", len(records))


def run_world_bank(database_path: str, ingested_at: str) -> None:
    world_bank_url = os.getenv(
        "WORLD_BANK_URL", "https://api.worldbank.org/v2/country/all/indicator"
    ).strip()
    world_bank_indicators = [
        indicator.strip()
        for indicator in os.getenv("WORLD_BANK_INDICATOR", "").split(",")
        if indicator.strip()
    ]
    for indicator in world_bank_indicators:
        records = fetch_indicator(
            world_bank_url,
            indicator,
            os.getenv("WORLD_BANK_DATE_RANGE", "2022:2024"),
            int(os.getenv("WORLD_BANK_TIMEOUT_SECONDS", "10")),
            int(os.getenv("WORLD_BANK_COUNTRY_LIMIT", "50")),
        )
        insert_world_bank_records(database_path, indicator, records, ingested_at)
        LOGGER.info("Inserted %d World Bank records for %s", len(records), indicator)
        time.sleep(5)
    if not world_bank_indicators:
        LOGGER.info("WORLD_BANK_INDICATOR is empty; skipping World Bank ingestion")


def run_csv(database_path: str, csv_input_dir: str, ingested_at: str) -> None:
    csv_files = find_csv_files(csv_input_dir)
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {csv_input_dir}")

    for csv_file in csv_files:
        row_number = 1
        batch: list[dict[str, str]] = []
        total_rows = 0
        for record in read_records(str(csv_file)):
            batch.append(record)
            if len(batch) == 1000:
                insert_raw_csv_records(
                    database_path,
                    csv_file.name,
                    batch,
                    row_number,
                    ingested_at,
                )
                row_number += len(batch)
                total_rows += len(batch)
                batch = []
        if batch:
            insert_raw_csv_records(
                database_path, csv_file.name, batch, row_number, ingested_at
            )
            total_rows += len(batch)
        LOGGER.info("Inserted %d raw CSV records from %s", total_rows, csv_file.name)


def run() -> None:
    database_path, schema_path, csv_input_dir = _settings()
    ingested_at = datetime.now(timezone.utc).isoformat()
    initialize_database(database_path, schema_path)
    run_cloudflare(database_path, ingested_at)
    run_world_bank(database_path, ingested_at)
    run_csv(database_path, csv_input_dir, ingested_at)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
