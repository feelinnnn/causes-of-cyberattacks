"""Sources B, C (part) and E (part): World Bank WDI and WGI country-year tables."""
from __future__ import annotations

import pandas as pd

from .common import WB_AGGREGATES, YEAR_MIN, YEAR_MAX, CleanLog, check_range, read_raw_csv, write_cleaned

FILES = {
    # cleaned name: (raw file, {column: (min, max)} physically possible range)
    "wb_econ": ("sourceB/world_bank_econ_pred.csv",
                {"gdp_per_capita": (0, None), "secure_internet_servers_per_1m": (0, None),
                 "fdi_net_inflows": (None, None), "population": (0, None)}),
    "wb_digital": ("sourceC/world_bank_digi_found.csv",
                   {"internet_users_pct": (0, 100), "broadband_subs_per_100": (0, 100)}),
    "wb_governance": ("sourceE/world_bank_gov_wgi.csv",
                      {"gov_effectiveness": (-2.5, 2.5), "rule_of_law": (-2.5, 2.5)}),
}


# clean ไฟล์ World Bank 1 ไฟล์
# ตัดแถวที่เป็นกลุ่มประเทศ (เช่น "ทั้งโลก", "เอเชียตะวันออก") ออก เพราะจะทำให้นับซ้ำ แล้วเช็กว่าค่าเป็นไปได้
def clean_one(name: str, path: str, ranges: dict, clog: CleanLog) -> pd.DataFrame:
    src = name
    df = read_raw_csv(path)

    before = len(df)
    df = df[~df["country_code"].isin(WB_AGGREGATES)]
    clog.add(src, "drop World Bank regional/income aggregates", before, len(df),
             "aggregates would double count countries")

    before = len(df)
    df = df[df["year"].between(YEAR_MIN, YEAR_MAX)]
    clog.add(src, f"keep years {YEAR_MIN}-{YEAR_MAX}", before, len(df))

    for col, (lo, hi) in ranges.items():
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df = check_range(df, [col], -1e18 if lo is None else lo, 1e18 if hi is None else hi, src, clog)

    # Rows where every indicator is empty carry no information, but they are kept:
    # an empty row still says "this country exists in the World Bank list for this year",
    # which the join step needs to tell "no data" apart from "not a country".
    empty = df[list(ranges)].isna().all(axis=1)
    clog.add(src, "rows with all indicators missing (kept)", len(df), len(df), f"{int(empty.sum())} rows")

    out = df.rename(columns={"country_code": "iso3"})[["iso3", "country_name", "year", *ranges]]
    write_cleaned(out, name, ["iso3", "year"])
    return out


# สั่ง clean ไฟล์ World Bank ทั้ง 3 ไฟล์ (เศรษฐกิจ, อินเทอร์เน็ต, ธรรมาภิบาล)
def run(clog: CleanLog) -> None:
    for name, (path, ranges) in FILES.items():
        clean_one(name, path, ranges, clog)
