from __future__ import annotations

import csv
from pathlib import Path
from collections.abc import Iterator


def read_records(csv_path: str) -> Iterator[dict[str, str]]:
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8-sig") as file:
        yield from csv.DictReader(file)


def find_csv_files(input_directory: str) -> list[Path]:
    return sorted(Path(input_directory).glob("*.csv"))
