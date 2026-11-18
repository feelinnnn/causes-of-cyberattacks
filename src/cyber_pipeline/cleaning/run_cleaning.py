"""Run the cleaning step: data/raw/ -> data/cleaned/.

Each source can be cleaned on its own (Airflow runs them as separate tasks), or all
together from the command line:

    PYTHONPATH=src python -m cyber_pipeline.cleaning.run_cleaning

Each source writes its own log (_cleaning_log_<source>.csv); combine_logs() merges them
into _cleaning_log.csv for the DQ report and the database.
"""
from __future__ import annotations

import pandas as pd

from cyber_pipeline.utils.paths import CLEANED

from . import bgp, cloudflare, gci, vdem, worldbank
from .common import CleanLog, log, write_cleaned
from .countries import build_reference


# สั่ง clean ข้อมูลเครือข่าย (ต้องใช้ตารางประเทศกลางช่วยแปลงรหัส)
def _bgp(clog: CleanLog) -> None:
    ref = build_reference().dropna(subset=["iso2"])
    bgp.run(clog, dict(zip(ref["iso2"], ref["iso3"])))


# สร้างและบันทึกตารางประเทศกลาง
def _reference(clog: CleanLog) -> None:
    write_cleaned(build_reference(), "country_reference", ["iso3"])


SOURCES = {
    "reference": _reference,
    "cloudflare": cloudflare.run,
    "worldbank": worldbank.run,
    "vdem": vdem.run,
    "gci": gci.run,
    "bgp": _bgp,
}


# clean แหล่งข้อมูลเดียว แล้วบันทึกว่าทำอะไรไปบ้างแยกเป็นไฟล์ของแหล่งนั้น
def run_source(name: str) -> None:
    clog = CleanLog()
    SOURCES[name](clog)
    CLEANED.mkdir(parents=True, exist_ok=True)
    clog.to_frame().to_csv(CLEANED / f"_cleaning_log_{name}.csv", index=False, encoding="utf-8")
    log.info("cleaned %s: %d log entries", name, len(clog.rows))


# รวมบันทึกของทุกแหล่งข้อมูลเป็นไฟล์เดียว (_cleaning_log.csv)
def combine_logs() -> None:
    parts = [pd.read_csv(CLEANED / f"_cleaning_log_{n}.csv") for n in SOURCES
             if (CLEANED / f"_cleaning_log_{n}.csv").exists()]
    parts = [p for p in parts if not p.empty]
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    out.to_csv(CLEANED / "_cleaning_log.csv", index=False, encoding="utf-8")


# clean ทุกแหล่งข้อมูลรวดเดียว (ใช้ตอนรันเองในเครื่อง ไม่ผ่าน Airflow)
def main() -> None:
    for name in SOURCES:
        run_source(name)
    combine_logs()


if __name__ == "__main__":
    main()
