"""Country reference table and country-name matching.

Join key for the whole project is ISO3 (`iso3`) + `year`.
The reference is built from codes already in the raw files (Cloudflare gives
ISO2+ISO3+name, World Bank gives ISO3+name), so no external lookup is needed.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

from .common import WB_AGGREGATES, read_raw_csv

CF_MAIN = "sourceA/cloudeflare_rader/cloudflare_radar_source_a.csv"
WB_ECON = "sourceB/world_bank_econ_pred.csv"
GCI_2018 = "sourceE/GCI_2018_Raw.csv"

# Known code errors in the raw Cloudflare files (ISO2 -> correct ISO3).
CF_ISO3_FIX = {"GR": "GRC"}
# Codes that are not countries: Cloudflare regions and the Tor network.
NON_COUNTRY = {"AP", "EU", "T1", "GLOBAL"}

# Names used by ITU (GCI) or V-Dem that do not match any name in the reference.
MANUAL_NAMES = {
    "korea rep of": "KOR", "republic of korea": "KOR", "korea dprk": "PRK",
    "democratic peoples republic of korea": "PRK", "lao pdr": "LAO",
    "lao peoples democratic republic": "LAO", "viet nam": "VNM", "turkiye": "TUR",
    "turkey": "TUR", "vatican": "VAT", "holy see": "VAT", "russian federation": "RUS",
    "iran islamic republic of": "IRN", "bolivia plurinational state of": "BOL",
    "venezuela": "VEN", "venezuela bolivarian republic of": "VEN",
    "congo rep of the": "COG", "congo republic of the": "COG", "congo": "COG",
    "democratic republic of the congo": "COD", "cote divoire": "CIV",
    "tanzania": "TZA", "united republic of tanzania": "TZA", "moldova": "MDA",
    "republic of moldova": "MDA", "nepal republic of": "NPL", "syria": "SYR",
    "syrian arab republic": "SYR", "micronesia": "FSM",
    "micronesia federated states of": "FSM", "north macedonia": "MKD",
    "eswatini": "SWZ", "cabo verde": "CPV", "czechia": "CZE", "czech republic": "CZE",
    "united states of america": "USA", "united kingdom": "GBR", "gambia": "GMB",
    "bahamas": "BHS", "egypt": "EGY", "yemen": "YEM", "kyrgyzstan": "KGZ",
    "slovakia": "SVK", "brunei darussalam": "BRN", "palestine": "PSE",
    "state of palestine": "PSE", "sao tome and principe": "STP",
    "saint kitts and nevis": "KNA", "saint lucia": "LCA",
    "saint vincent and the grenadines": "VCT", "timor leste": "TLS",
    "dominican rep": "DOM", "lao p d r": "LAO", "dem rep of the congo": "COD",
    "central african rep": "CAF", "dem peoples rep of korea": "PRK", "dem people s rep of korea": "PRK",
    "burma myanmar": "MMR", "myanmar": "MMR", "taiwan": "TWN", "hong kong": "HKG",
}


# ทำให้ชื่อประเทศเขียนเหมือนกัน เช่น "Côte d'Ivoire" กับ "Cote dIvoire" จะกลายเป็นคำเดียวกัน
# (เปลี่ยนเป็นตัวเล็ก ตัดสัญลักษณ์และวรรณยุกต์ออก)
def normalize_name(name: str) -> str:
    """Lowercase, drop accents, asterisks and punctuation so name variants compare equal."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = s.replace("*", "").replace("&", " and ").lower()
    s = re.sub(r"[^a-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# สร้างตารางรายชื่อประเทศกลาง บอกว่าแต่ละประเทศมีรหัส 2 ตัว รหัส 3 ตัว และชื่ออะไร
# ทุกแหล่งข้อมูลจะใช้ตารางนี้แปลงรหัสให้ตรงกัน
def build_reference() -> pd.DataFrame:
    """One row per country/territory: iso3, iso2, name, in_worldbank."""
    cf = read_raw_csv(CF_MAIN)[["country_iso2", "country_code", "country_name"]].drop_duplicates()
    cf = cf[~cf["country_iso2"].isin(NON_COUNTRY)]
    cf["iso3"] = cf["country_iso2"].map(CF_ISO3_FIX).fillna(cf["country_code"])
    ref = cf.rename(columns={"country_iso2": "iso2", "country_name": "name"})[["iso3", "iso2", "name"]]

    wb = read_raw_csv(WB_ECON)[["country_code", "country_name"]].drop_duplicates()
    wb = wb[~wb["country_code"].isin(WB_AGGREGATES)]
    ref = ref.merge(wb.rename(columns={"country_code": "iso3", "country_name": "name_wb"}),
                    on="iso3", how="outer")
    ref["in_worldbank"] = ref["name_wb"].notna()
    ref["name"] = ref["name"].fillna(ref["name_wb"])
    return ref[["iso3", "iso2", "name", "name_wb", "in_worldbank"]].sort_values("iso3").reset_index(drop=True)


# สร้างตัวช่วยแปลง "ชื่อประเทศ" เป็น "รหัส 3 ตัว"
# ใช้กับไฟล์ที่มีแต่ชื่อ ไม่มีรหัส (เช่น GCI)
def name_lookup(ref: pd.DataFrame) -> dict[str, str]:
    """normalized name -> iso3, from every name we already trust plus manual fixes."""
    lut: dict[str, str] = {}
    for col in ("name", "name_wb"):
        for n, c in zip(ref[col], ref["iso3"]):
            if isinstance(n, str):
                lut[normalize_name(n)] = c
    # GCI 2018 carries ITU's own names next to ISO2 codes: reuse them for 2020/2024.
    iso2_to_3 = dict(zip(ref["iso2"], ref["iso3"]))
    g = read_raw_csv(GCI_2018)
    for n, c2 in zip(g["country_name"], g["country_code"]):
        if c2 in iso2_to_3:
            lut[normalize_name(n)] = iso2_to_3[c2]
    lut.update(MANUAL_NAMES)
    return lut
