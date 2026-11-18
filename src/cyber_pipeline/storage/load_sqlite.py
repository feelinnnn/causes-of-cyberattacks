"""Load pipeline outputs into SQLite: data/warehouse/cyberattacks.db

What goes in the database (what the web app and analysis read):
- every table in data/cleaned/          -> table cleaned_<name>
- data/integrated/country_year.csv      -> table country_year
- reports/dq/dq_results.csv             -> table dq_results
- data/cleaned/_cleaning_log.csv        -> table cleaning_log
- one row per run                       -> table pipeline_runs (history, never replaced)

What stays as files: data/raw/ (large, read-only, licence-restricted).

Each run REPLACES the data tables inside one transaction: re-running never creates
duplicates, and if anything fails the previous version stays intact.

    PYTHONPATH=src python -m cyber_pipeline.storage.load_sqlite
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from cyber_pipeline.utils.logging_utils import get_logger
from cyber_pipeline.utils.paths import CLEANED, DATA, INTEGRATED, REPORTS

log = get_logger("load_sqlite")
DB_PATH = Path(os.environ.get("SQLITE_PATH", DATA / "warehouse" / "cyberattacks.db"))

# Primary keys get a unique index so the database itself rejects duplicates.
KEYS = {
    "cleaned_country_reference": ["iso3"],
    "cleaned_cloudflare_country_year": ["iso3", "year"],
    "cleaned_cloudflare_l3_vectors": ["iso3", "year", "vector"],
    "cleaned_cloudflare_attack_pairs": ["year", "origin_iso2", "target_iso2"],
    "cleaned_cloudflare_timeseries_weekly": ["iso2", "request_year", "week_start"],
    "cleaned_wb_econ": ["iso3", "year"], "cleaned_wb_digital": ["iso3", "year"],
    "cleaned_wb_governance": ["iso3", "year"], "cleaned_vdem_country_year": ["iso3", "year"],
    "cleaned_gci_country_edition": ["iso3", "edition"], "cleaned_bgp_country_year": ["iso3", "year"],
    "country_year": ["iso3", "year"],
}


# อ่านไฟล์ CSV (ระวังรหัส "NA" ของนามิเบีย)
def read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


# รวบรวมตารางทั้งหมดที่จะเอาไปเก็บในฐานข้อมูล
def collect() -> dict[str, pd.DataFrame]:
    tables = {f"cleaned_{p.stem}": read(p) for p in sorted(CLEANED.glob("*.csv")) if not p.stem.startswith("_")}
    tables["country_year"] = read(INTEGRATED / "country_year.csv")
    for name, path in {"dq_results": REPORTS / "dq" / "dq_results.csv",
                       "cleaning_log": CLEANED / "_cleaning_log.csv"}.items():
        if path.exists():
            tables[name] = read(path)
    return tables


# บันทึกทุกตารางลงฐานข้อมูล SQLite (เขียนทับของเดิมทั้งหมด ไม่มีข้อมูลซ้ำ)
# ถ้าพังกลางทาง ข้อมูลเดิมยังอยู่ครบ และจดประวัติไว้ว่ารันเมื่อไหร่
def main() -> None:
    tables = collect()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con = sqlite3.connect(DB_PATH)
    try:
        with con:  # one transaction: all tables replaced, or none
            for name, df in tables.items():
                df.to_sql(name, con, if_exists="replace", index=False)
                if name in KEYS:
                    con.execute(f'CREATE UNIQUE INDEX "ux_{name}" ON "{name}" ({", ".join(KEYS[name])})')
            con.execute("""CREATE TABLE IF NOT EXISTS pipeline_runs (
                               run_at TEXT, table_name TEXT, n_rows INTEGER, n_columns INTEGER)""")
            con.executemany("INSERT INTO pipeline_runs VALUES (?, ?, ?, ?)",
                            [(started, n, len(df), df.shape[1]) for n, df in tables.items()])
    finally:
        con.close()
    log.info("loaded %d tables into %s", len(tables), DB_PATH)


if __name__ == "__main__":
    main()
