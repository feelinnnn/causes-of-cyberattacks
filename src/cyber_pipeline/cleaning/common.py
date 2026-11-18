"""Shared helpers for the cleaning step.

Rules that apply to every source:
- Read raw files read-only; never write back into data/raw/.
- Read "NA" as text, not as missing: "NA" is Namibia's ISO2 code.
- Keep missing values as NaN. Imputation is a modelling decision and is done
  later (after the train/test split) so it cannot leak future information.
- Every dropped or changed row is recorded in CleanLog so the DQ report can
  show exactly what cleaning did.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from cyber_pipeline.utils.logging_utils import get_logger
from cyber_pipeline.utils.paths import CLEANED, RAW

log = get_logger("cleaning")

YEAR_MIN, YEAR_MAX = 2018, 2024

# World Bank region / income / lending groups present in the raw files.
# They are sums or averages of countries, so keeping them would double count.
WB_AGGREGATES = {
    "AFE", "AFW", "ARB", "CEB", "CSS", "EAP", "EAR", "EAS", "ECA", "ECS", "EMU",
    "EUU", "FCS", "FCV", "HIC", "HPC", "IBD", "IBT", "IDA", "IDB", "IDX", "INX",
    "LAC", "LCN", "LDC", "LIC", "LMC", "LMY", "LTE", "MEA", "MIC", "MNA", "NAC",
    "OED", "OSS", "PRE", "PSS", "PST", "SAS", "SSA", "SSF", "SST", "TEA", "TEC",
    "TLA", "TMN", "TSA", "TSS", "UMC", "WLD",
}


# อ่านไฟล์ข้อมูลดิบเข้ามาเป็นตาราง
# ระวังเรื่องเดียว: นามิเบียใช้รหัส "NA" ถ้าอ่านแบบปกติ pandas จะนึกว่าเป็นช่องว่าง เลยสั่งให้อ่านเป็นตัวหนังสือ
def read_raw_csv(rel_path: str, **kw) -> pd.DataFrame:
    """Read a raw CSV. utf-8-sig strips the BOM; keep_default_na=False keeps 'NA' (Namibia)."""
    return pd.read_csv(RAW / rel_path, encoding="utf-8-sig",
                       keep_default_na=False, na_values=[""], **kw)


@dataclass
class CleanLog:
    rows: list[dict] = field(default_factory=list)

    # จดบันทึกว่าขั้นตอนนี้ทำอะไรไป มีกี่แถวก่อนและหลัง (เอาไว้ใส่ในรายงาน)
    def add(self, source: str, step: str, before: int, after: int, note: str = "") -> None:
        self.rows.append({"source": source, "step": step, "rows_before": before,
                          "rows_after": after, "rows_changed": before - after, "note": note})
        log.info("%s | %s | %d -> %d %s", source, step, before, after, note)

    # เอาบันทึกทั้งหมดมาทำเป็นตาราง
    def to_frame(self) -> pd.DataFrame:
        cols = ["source", "step", "rows_before", "rows_after", "rows_changed", "note"]
        return pd.DataFrame(self.rows, columns=cols)


# เช็กว่าค่าเป็นไปได้จริงไหม เช่น เปอร์เซ็นต์ต้องอยู่ระหว่าง 0 ถึง 100
# ถ้าค่าไหนผิดให้เปลี่ยนเป็นช่องว่าง แล้วจดไว้ว่าเปลี่ยนไปกี่ค่า
def check_range(df: pd.DataFrame, cols: list[str], lo: float, hi: float,
                source: str, clog: CleanLog) -> pd.DataFrame:
    """Values outside [lo, hi] are impossible for the measure, so set them to NaN."""
    for c in cols:
        bad = df[c].notna() & ~df[c].between(lo, hi)
        if bad.any():
            df.loc[bad, c] = pd.NA
        clog.add(source, f"range check {c} in [{lo},{hi}]", len(df), len(df),
                 f"{int(bad.sum())} values set to NaN")
    return df


# บันทึกตารางที่ clean แล้วลงโฟลเดอร์ data/cleaned/
# ก่อนบันทึกจะเช็กว่าไม่มีแถวซ้ำ ถ้ามีจะหยุดทันที
def write_cleaned(df: pd.DataFrame, name: str, key: list[str]) -> Path:
    """Write one cleaned table. Fails loudly if the key is not unique."""
    dup = df.duplicated(key).sum()
    if dup:
        raise ValueError(f"{name}: {dup} duplicate rows on key {key}")
    CLEANED.mkdir(parents=True, exist_ok=True)
    out = CLEANED / f"{name}.csv"
    df.sort_values(key).to_csv(out, index=False, encoding="utf-8")
    log.info("wrote %s (%d rows, key=%s)", out.name, len(df), key)
    return out
