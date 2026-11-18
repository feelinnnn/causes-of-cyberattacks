"""Source A: Cloudflare Radar (3 raw files -> 4 cleaned tables)."""
from __future__ import annotations

import json

import pandas as pd

from .common import CleanLog, check_range, read_raw_csv, write_cleaned
from .countries import CF_ISO3_FIX, NON_COUNTRY

SRC = "cloudflare"
DIR = "sourceA/cloudeflare_rader/"

PCT_COLS = ["target_ddos_percent", "origin_ddos_percent", "target_l7_mitigated_percent",
            "origin_l7_mitigated_percent", "http_traffic_percent",
            "ipv4_percent", "ipv6_percent", "bot_traffic_percent", "tls_1_3_percent",
            "mitigation_waf_percent", "mitigation_ddos_percent", "mitigation_bot_percent"]

# mitigation_* were fetched with location=XX. For layer 7 that filters on where the
# attack COMES FROM, so the names say so to stop them being read as "attacks received".
RENAME = {"country_code": "iso3",
          "mitigation_waf_percent": "origin_mitig_waf_percent",
          "mitigation_ddos_percent": "origin_mitig_ddos_percent",
          "mitigation_bot_percent": "origin_mitig_bot_percent"}


# แก้รหัสประเทศที่ผิดในไฟล์ดิบ (กรีซเขียนเป็น GR แต่ต้องเป็น GRC)
def _fix_codes(df: pd.DataFrame, iso2: str, iso3: str, clog: CleanLog, step: str) -> pd.DataFrame:
    n = int((df[iso2].isin(CF_ISO3_FIX)).sum())
    df[iso3] = df[iso2].map(CF_ISO3_FIX).fillna(df[iso3])
    clog.add(SRC, f"{step}: fix wrong ISO3 (GR->GRC)", len(df), len(df), f"{n} rows recoded")
    return df


# clean ไฟล์หลักของ Cloudflare (1 แถว = 1 ประเทศใน 1 ปี)
# แก้รหัสประเทศ, ตัดภูมิภาคออก, ดึงตัวเลขการโจมตี L3 ออกมาจากข้อความ JSON, ตัดคอลัมน์ที่ใช้ไม่ได้
def clean_country_year(clog: CleanLog) -> pd.DataFrame:
    df = read_raw_csv(DIR + "cloudflare_radar_source_a.csv")
    df = _fix_codes(df, "country_iso2", "country_code", clog, "country_year")

    before = len(df)
    df = df[~df["country_iso2"].isin(NON_COUNTRY)]
    clog.add(SRC, "country_year: drop regions (AP, EU)", before, len(df))

    # Layer 3 vector breakdown is a JSON string -> real numbers.
    # l3_syn_percent / l3_udp_percent are empty in raw, so rebuild them from the JSON.
    parsed = df["l3_vector_breakdown_json"].map(lambda s: json.loads(s) if isinstance(s, str) else {})
    df["l3_syn_percent"] = parsed.map(lambda d: float(d["SYN Flood"]) if "SYN Flood" in d else None)
    df["l3_udp_percent"] = parsed.map(lambda d: float(d["UDP Flood"]) if "UDP Flood" in d else None)
    has_l3 = parsed.map(bool)
    # Vector absent from a non-empty breakdown = below the top-10 shown, not "unknown".
    for c in ("l3_syn_percent", "l3_udp_percent"):
        df.loc[has_l3 & df[c].isna(), c] = 0.0
    clog.add(SRC, "country_year: rebuild l3_syn/udp from JSON", len(df), len(df),
             f"{int(has_l3.sum())} rows with L3 data")

    for c in PCT_COLS:  # older snapshots may lack the newer columns
        if c not in df.columns:
            df[c] = pd.NA
    df = check_range(df, PCT_COLS + ["l3_syn_percent", "l3_udp_percent"], 0, 100, SRC, clog)

    # A country with all three mitigation shares = 0 has no attacks recorded, not 0%.
    mit = ["mitigation_waf_percent", "mitigation_ddos_percent", "mitigation_bot_percent"]
    allzero = df[mit].sum(axis=1, min_count=1).eq(0)
    df.loc[allzero, mit] = pd.NA
    clog.add(SRC, "country_year: all-zero mitigation -> NaN", len(df), len(df), f"{int(allzero.sum())} rows")

    df["l3_top_vector"] = df["l3_vector_type"]
    keep = ["country_code", "country_iso2", "country_name", "year"] + PCT_COLS + \
           ["l3_top_vector", "l3_syn_percent", "l3_udp_percent"] + \
           [c for c in ("meta_date_start", "meta_date_end") if c in df.columns]
    # Dropped on purpose:
    # - attack_flow_pair: free-text copy of the pairs table, which is cleaned separately.
    # - l3_vector_breakdown_json: moved to the long table cloudflare_l3_vectors.
    # - timeseries_weekly_mean/peak: each country's series is scaled to its own max (=1),
    #   so these cannot be compared between countries.
    # - *_intensity, *_log_ratio, is_above_min_traffic (added by the fetch script): derived
    #   features. They are rebuilt in feature engineering from the raw shares, so the choice
    #   of formula and threshold lives in one place and is applied after the train/test split.
    out = df[keep].rename(columns=RENAME).rename(columns={"country_iso2": "iso2"})
    # Columns with no value at all (e.g. target/origin DDoS in the current raw snapshot)
    # carry no information. Drop them here; if a later snapshot fills them, they come back.
    empty = [c for c in out.columns if out[c].isna().all()]
    out = out.drop(columns=empty)
    clog.add(SRC, "country_year: drop 100% empty columns", len(out), len(out),
             ", ".join(empty) or "none")
    write_cleaned(out, "cloudflare_country_year", ["iso3", "year"])

    l3 = [{"iso3": c, "year": y, "vector": k, "percent": float(v)}
          for c, y, d in zip(out["iso3"], out["year"], parsed) for k, v in d.items()]
    l3 = pd.DataFrame(l3)
    write_cleaned(l3, "cloudflare_l3_vectors", ["iso3", "year", "vector"])
    return out


# clean ไฟล์ "ใครโจมตีใคร" (คู่ประเทศต้นทางกับเป้าหมาย)
# ไม่ลบแถวไหนทิ้ง แต่เพิ่มคอลัมน์ True/False ไว้ให้เลือกกรองทีหลัง:
#   origin_is_country = False ถ้าต้นทางเป็นเครือข่าย Tor (ไม่ใช่ประเทศจริง)
#   is_domestic = True ถ้าต้นทางกับเป้าหมายเป็นประเทศเดียวกัน (โจมตีกันเองในประเทศ)
def clean_pairs(clog: CleanLog) -> pd.DataFrame:
    df = read_raw_csv(DIR + "cloudflare_attack_flow_pairs.csv")
    for side in ("origin", "target"):
        df = _fix_codes(df, f"{side}_country_iso2", f"{side}_country_code", clog, f"pairs {side}")
    df["origin_is_country"] = ~df["origin_country_iso2"].isin(NON_COUNTRY)  # T1 = Tor network
    df["is_domestic"] = df["origin_country_iso2"] == df["target_country_iso2"]
    df = check_range(df, ["attack_share_percent"], 0, 100, SRC, clog)
    out = df.rename(columns={"origin_country_code": "origin_iso3", "target_country_code": "target_iso3",
                             "origin_country_iso2": "origin_iso2", "target_country_iso2": "target_iso2"})
    out = out[["year", "rank", "origin_iso3", "origin_iso2", "origin_country_name",
               "target_iso3", "target_iso2", "target_country_name", "attack_share_percent",
               "origin_is_country", "is_domestic"]]
    clog.add(SRC, "pairs: keep Tor (T1) & domestic pairs, flagged", len(out), len(out),
             f"{int((~out.origin_is_country).sum())} Tor, {int(out.is_domestic.sum())} domestic")
    write_cleaned(out, "cloudflare_attack_pairs", ["year", "origin_iso2", "target_iso2"])
    return out


# clean ไฟล์รายสัปดาห์
# สัปดาห์เดียวกันอาจอยู่ในข้อมูล 2 ปี เลยเก็บปีที่ขอข้อมูลไว้ในคอลัมน์ request_year
# และเพิ่มคอลัมน์ is_partial_week = True สำหรับสัปดาห์ที่คร่อมปี (ไม่ลบ แต่ไว้กรองออกได้ถ้าไม่อยากนับซ้ำ)
def clean_timeseries(clog: CleanLog) -> pd.DataFrame:
    df = read_raw_csv(DIR + "cloudflare_timeseries_weekly.csv")
    df = _fix_codes(df, "country_iso2", "country_code", clog, "timeseries")
    df["week_start"] = pd.to_datetime(df["week_timestamp"], utc=True).dt.date
    # Each request covered one calendar year and was scaled to max=1 within that request.
    # The same week can appear in two requests with different values, so the request
    # year is part of the key, and the edge weeks that spill into another year are flagged.
    df = df.rename(columns={"year": "request_year", "country_code": "iso3",
                            "country_iso2": "iso2", "timeseries_weekly_trend": "trend_scaled"})
    ws = pd.to_datetime(df["week_start"])
    df["is_partial_week"] = (ws.dt.year != df["request_year"]) | \
                            ((ws + pd.Timedelta(days=6)).dt.year != df["request_year"])
    df["scope"] = df["iso2"].map(lambda c: "global" if c == "GLOBAL" else "region" if c in ("AP", "EU") else "country")
    df = check_range(df, ["trend_scaled"], 0, 1, SRC, clog)
    out = df[["iso3", "iso2", "country_name", "scope", "request_year", "week_start",
              "trend_scaled", "is_partial_week"]]
    clog.add(SRC, "timeseries: flag partial weeks at year edges", len(out), len(out),
             f"{int(out.is_partial_week.sum())} rows flagged")
    write_cleaned(out, "cloudflare_timeseries_weekly", ["iso2", "request_year", "week_start"])
    return out


# สั่ง clean ไฟล์ Cloudflare ทั้ง 3 ไฟล์
def run(clog: CleanLog) -> None:
    clean_country_year(clog)
    clean_pairs(clog)
    clean_timeseries(clog)
