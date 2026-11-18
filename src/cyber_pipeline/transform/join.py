"""data/cleaned/ -> data/integrated/country_year.csv

Design:
- Spine = every country/territory in country_reference (except ones with no data at all)
  x analysis years. Every source is LEFT-joined onto it, so a country never disappears
  silently; missing data shows up as NaN and is counted by the DQ step.
- Only country x year tables are joined. Finer tables (L3 vectors, attack pairs, weekly
  series) would multiply rows, so they stay separate for EDA and the web app.
- GCI is published per edition, not per year: each year gets the latest edition
  published in or before that year (as-of join), so no future value is used.
- No rows are filtered for analysis here. Filtering (population, traffic threshold,
  complete cases) happens in the analytical step, using the flags added below.

    PYTHONPATH=src python -m cyber_pipeline.transform.join
"""
from __future__ import annotations

import pandas as pd

from cyber_pipeline.utils.logging_utils import get_logger
from cyber_pipeline.utils.paths import CLEANED, INTEGRATED

log = get_logger("join")

NO_DATA = {"ANT"}  # Netherlands Antilles: dissolved 2010, no value in any source
KEY = ["iso3", "year"]

# cleaned table -> columns to bring in (all are country x year)
SOURCES = {
    "cloudflare_country_year": ["target_ddos_percent", "origin_ddos_percent", "target_l7_mitigated_percent",
                                "origin_l7_mitigated_percent", "http_traffic_percent", "ipv4_percent", "ipv6_percent",
                                "bot_traffic_percent", "tls_1_3_percent", "origin_mitig_waf_percent",
                                "origin_mitig_ddos_percent", "origin_mitig_bot_percent",
                                "l3_top_vector", "l3_syn_percent", "l3_udp_percent"],
    "wb_econ": ["gdp_per_capita", "population", "secure_internet_servers_per_1m", "fdi_net_inflows"],
    "wb_digital": ["internet_users_pct", "broadband_subs_per_100"],
    "wb_governance": ["gov_effectiveness", "rule_of_law"],
    "vdem_country_year": ["v2smgovcapsec", "v2smprivcon", "v2smprivex", "v2x_polyarchy", "v2x_libdem",
                          "v2x_rule", "v2smgovfilprc", "v2smgovshut", "v2smgovsmmon", "v2smfordom",
                          "v2smpolcap", "v2smgovcapsec_nr", "v2smprivcon_nr"],
    "bgp_country_year": ["routed_asn_count", "routed_prefix_count", "ipv4_slash24_count"],
}
SHORT = {"cloudflare_country_year": "cloudflare", "wb_econ": "wb_econ", "wb_digital": "wb_digital",
         "wb_governance": "wb_governance", "vdem_country_year": "vdem", "bgp_country_year": "bgp"}


# อ่านตารางที่ clean แล้วจาก data/cleaned/
def read(name: str) -> pd.DataFrame:
    return pd.read_csv(CLEANED / f"{name}.csv", keep_default_na=False, na_values=[""])


# สร้างตารางเปล่าที่มีทุกประเทศ ทุกปี ไว้เป็นโครงก่อน
# แล้วค่อยเอาข้อมูลแต่ละแหล่งมาเติมทีละแหล่ง ประเทศที่ไม่มีข้อมูลจะไม่หายไป แค่เป็นช่องว่าง
def build_spine(ref: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    ref = ref[~ref["iso3"].isin(NO_DATA)]
    spine = ref[["iso3", "iso2", "name", "in_worldbank"]].rename(columns={"name": "country_name"})
    return spine.merge(pd.DataFrame({"year": years}), how="cross")


# เอาข้อมูลอีกตารางมาเติมเข้าตารางหลัก โดยจับคู่ด้วยประเทศและปี
# ถ้าจำนวนแถวเปลี่ยน (ซ้ำหรือหาย) จะหยุดทันที
def left_join(df: pd.DataFrame, other: pd.DataFrame, on: list[str], name: str) -> pd.DataFrame:
    """Left join that refuses to add or lose rows."""
    n = len(df)
    out = df.merge(other, on=on, how="left", validate="one_to_one")
    if len(out) != n:
        raise ValueError(f"join with {name} changed row count {n} -> {len(out)}")
    return out


# GCI ไม่ได้ออกทุกปี เลยให้แต่ละปีใช้ฉบับล่าสุดที่ออกแล้ว ณ ปีนั้น
# เช่น ปี 2023 ใช้ฉบับ 2020 (ห้ามใช้ฉบับ 2024 เพราะยังไม่ออก)
def gci_asof(gci: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """For each iso3 x year: latest GCI edition with edition <= year."""
    rows = []
    for y in years:
        g = gci[gci["edition"] <= y].sort_values("edition").groupby("iso3").tail(1)
        rows.append(g.assign(year=y))
    out = pd.concat(rows, ignore_index=True)
    out["gci_age_years"] = out["year"] - out["edition"]
    return out.rename(columns={"edition": "gci_edition_used"})[
        ["iso3", "year", "gci_score_100", "gci_tier", "gci_edition_used", "gci_age_years"]]


# รวมทุกแหล่งข้อมูลเป็นตารางเดียว country_year.csv
# และเพิ่มคอลัมน์ช่วยคัดประเทศ เช่น มีข้อมูลประชากรไหม traffic มากพอไหม
def main() -> pd.DataFrame:
    # Analysis years follow the attack data: whatever years Cloudflare has, the spine has.
    years = sorted(read("cloudflare_country_year")["year"].unique().tolist())
    df = build_spine(read("country_reference"), years)
    log.info("spine: %d countries x years %s = %d rows", df.iso3.nunique(), years, len(df))

    for name, cols in SOURCES.items():
        src = read(name)
        cols = [c for c in cols if c in src.columns]  # e.g. columns dropped as 100% empty
        src = src[KEY + cols]
        flag = f"has_{SHORT[name]}"
        src[flag] = True
        df = left_join(df, src, KEY, name)
        df[flag] = df[flag].eq(True)
        log.info("joined %-24s matched %d/%d rows", name, df[flag].sum(), len(df))

    g = gci_asof(read("gci_country_edition"), years)
    g["has_gci"] = True
    df = left_join(df, g, KEY, "gci")
    df["has_gci"] = df["has_gci"].eq(True)
    log.info("joined %-24s matched %d/%d rows", "gci (as-of)", df["has_gci"].sum(), len(df))

    # Flags for the analytical step (no filtering here).
    df["has_population"] = df["population"].notna()
    # Traffic share can be missing for some years (2022 in the current snapshot), so use the
    # country's mean over all available years.
    df["http_traffic_mean"] = df.groupby("iso3")["http_traffic_percent"].transform("mean")
    df["traffic_above_0_01pct"] = df["http_traffic_mean"] >= 0.01
    df["n_sources_available"] = df[[c for c in df.columns if c.startswith("has_")
                                    and c != "has_population"]].sum(axis=1)

    INTEGRATED.mkdir(parents=True, exist_ok=True)
    out = INTEGRATED / "country_year.csv"
    df.sort_values(KEY).to_csv(out, index=False, encoding="utf-8")
    log.info("wrote %s: %d rows x %d columns", out.name, *df.shape)
    return df


if __name__ == "__main__":
    main()
