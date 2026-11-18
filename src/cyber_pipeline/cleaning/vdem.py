"""Source E (part): V-Dem v16, country-year. The raw file has 4,600+ columns; keep only these."""
from __future__ import annotations

from .common import YEAR_MIN, YEAR_MAX, CleanLog, read_raw_csv, write_cleaned

SRC = "vdem"
RAW_FILE = "sourceE/V-Dem-CY-Full+Others-v16.csv"

# Agreed variables plus the extra digital-society ones listed in data_audit.md,
# so the team can still choose between them without re-reading the 400 MB file.
VARS = ["v2smgovcapsec", "v2smprivcon", "v2smprivex", "v2x_polyarchy", "v2x_libdem", "v2x_rule",
        "v2smgovfilprc", "v2smgovshut", "v2smgovsmmon", "v2smfordom", "v2smpolcap"]
# _nr = number of expert coders. Few coders = less reliable estimate (used in the DQ report).
NR = ["v2smgovcapsec_nr", "v2smprivcon_nr"]

# V-Dem units that are not ISO countries; no other source reports them.
NOT_ISO = {"PSG": "Palestine/Gaza", "SML": "Somaliland", "ZZB": "Zanzibar"}


# clean ข้อมูล V-Dem (ไฟล์ใหญ่มาก 400 MB)
# อ่านมาเฉพาะคอลัมน์ที่ใช้ เก็บเฉพาะปี 2018-2024 และตัดพื้นที่ที่ไม่ใช่ประเทศ (เช่น Gaza) ออก
def run(clog: CleanLog) -> None:
    cols = ["country_name", "country_text_id", "year", *VARS, *NR]
    df = read_raw_csv(RAW_FILE, usecols=cols)
    clog.add(SRC, f"select {len(VARS)} variables (+{len(NR)} coder counts) of 4,600+", len(df), len(df))

    before = len(df)
    df = df[df["year"].between(YEAR_MIN, YEAR_MAX)]
    clog.add(SRC, f"keep years {YEAR_MIN}-{YEAR_MAX}", before, len(df))

    before = len(df)
    df = df[~df["country_text_id"].isin(NOT_ISO)]
    clog.add(SRC, "drop non-ISO units (Gaza, Somaliland, Zanzibar)", before, len(df),
             "PSE in V-Dem = West Bank only; kept as PSE")

    # v2smprivcon is missing by design for countries with no privacy law; keep NaN.
    out = df.rename(columns={"country_text_id": "iso3"})[["iso3", "country_name", "year", *VARS, *NR]]
    write_cleaned(out, "vdem_country_year", ["iso3", "year"])
