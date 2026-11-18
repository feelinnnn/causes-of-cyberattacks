from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def initialize_database(database_path: str, schema_path: str) -> None:
    """Create the SQLite database and its tables if they do not exist."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = Path(schema_path).read_text(encoding="utf-8")
    with sqlite3.connect(path) as connection:
        connection.executescript(schema)


def insert_api_records(
    database_path: str,
    source_url: str,
    records: list[dict[str, Any]],
    ingested_at: str,
) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO api_cyberattacks (source_url, payload, ingested_at)
            VALUES (?, ?, ?)
            """,
            [(source_url, json.dumps(record), ingested_at) for record in records],
        )


def insert_csv_records(
    database_path: str,
    records: list[dict[str, str]],
    ingested_at: str,
) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO csv_cyberattacks
                (attack_type, description, source, occurred_at, ingested_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    record.get("attack_type"),
                    record.get("description"),
                    record.get("source"),
                    record.get("occurred_at"),
                    ingested_at,
                )
                for record in records
            ],
        )


def insert_raw_csv_records(
    database_path: str,
    source_file: str,
    records: list[dict[str, str]],
    start_row_number: int,
    ingested_at: str,
) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO raw_csv_records
                (source_file, row_number, payload, ingested_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                (source_file, start_row_number + offset, json.dumps(record), ingested_at)
                for offset, record in enumerate(records)
            ],
        )


def insert_world_bank_records(
    database_path: str,
    indicator: str,
    records: list[dict[str, Any]],
    ingested_at: str,
) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO world_bank_records
                (indicator, country_id, country_name, year, value, payload, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    indicator,
                    record.get("countryiso3code"),
                    (record.get("country") or {}).get("value"),
                    record.get("date"),
                    str(record.get("value")) if record.get("value") is not None else None,
                    json.dumps(record),
                    ingested_at,
                )
                for record in records
            ],
        )
