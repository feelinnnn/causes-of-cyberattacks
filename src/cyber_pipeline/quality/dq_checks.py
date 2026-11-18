"""Data quality checks on data/cleaned/ and data/integrated/.

Each rule returns rows for reports/dq/dq_results.csv:
  rule_id, dimension, table, column, check, severity, n_checked, n_failed, pct_failed, status, detail
severity "error" -> status FAIL stops the pipeline (exit code 1, Airflow marks the task failed).
severity "warn"  -> status WARN is reported; the pipeline continues.
Rules only report; they never change data.

    PYTHONPATH=src python -m cyber_pipeline.quality.dq_checks
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from cyber_pipeline.utils.logging_utils import get_logger
from cyber_pipeline.utils.paths import CLEANED, INTEGRATED, REPORTS

from . import data_dictionary

log = get_logger("dq")
DQ_DIR = REPORTS / "dq"

KEYS = {
    "country_reference": ["iso3"], "cloudflare_country_year": ["iso3", "year"],
    "cloudflare_l3_vectors": ["iso3", "year", "vector"],
    "cloudflare_attack_pairs": ["year", "origin_iso2", "target_iso2"],
    "cloudflare_timeseries_weekly": ["iso2", "request_year", "week_start"],
    "wb_econ": ["iso3", "year"], "wb_digital": ["iso3", "year"], "wb_governance": ["iso3", "year"],
    "vdem_country_year": ["iso3", "year"], "gci_country_edition": ["iso3", "edition"],
    "bgp_country_year": ["iso3", "year"],
}
# (table, columns, low, high): physically possible ranges
RANGES = [
    ("cloudflare_country_year", ["target_ddos_percent", "origin_ddos_percent", "target_l7_mitigated_percent",
                                 "origin_l7_mitigated_percent", "http_traffic_percent", "ipv4_percent", "ipv6_percent", "bot_traffic_percent",
                                 "tls_1_3_percent", "origin_mitig_waf_percent", "origin_mitig_ddos_percent",
                                 "origin_mitig_bot_percent", "l3_syn_percent", "l3_udp_percent"], 0, 100),
    ("cloudflare_l3_vectors", ["percent"], 0, 100),
    ("cloudflare_attack_pairs", ["attack_share_percent"], 0, 100),
    ("cloudflare_timeseries_weekly", ["trend_scaled"], 0, 1),
    ("wb_econ", ["gdp_per_capita", "population", "secure_internet_servers_per_1m"], 0, np.inf),
    ("wb_digital", ["internet_users_pct", "broadband_subs_per_100"], 0, 100),
    ("wb_governance", ["gov_effectiveness", "rule_of_law"], -2.5, 2.5),
    ("vdem_country_year", ["v2x_polyarchy", "v2x_libdem", "v2x_rule"], 0, 1),
    ("gci_country_edition", ["gci_score_100"], 0, 100),
    ("bgp_country_year", ["routed_asn_count", "routed_prefix_count", "ipv4_slash24_count"], 0, np.inf),
]
MISSING_WARN = 0.30   # completeness: warn if more than 30% missing
COVERAGE_WARN = 0.80  # join coverage: warn if fewer than 80% of in-World-Bank rows matched
OUTLIER_Z = 5.0       # robust z-score (median / MAD)
FEW_CODERS = 3        # V-Dem estimates from <= 3 experts are less reliable
CROSS_RHO = 0.70      # expected Spearman rho between two independent measures of internet size

_rows: list[dict] = []


# จดผลการตรวจ 1 ข้อ ว่าผ่าน (PASS) เตือน (WARN) หรือไม่ผ่าน (FAIL)
def record(rule_id, dimension, table, column, check, severity, n_checked, n_failed, detail="",
           failed_is_bad=True):
    pct = n_failed / n_checked if n_checked else 0.0
    status = "PASS" if (n_failed == 0 or not failed_is_bad) else ("FAIL" if severity == "error" else "WARN")
    _rows.append({"rule_id": rule_id, "dimension": dimension, "table": table, "column": column,
                  "check": check, "severity": severity, "n_checked": int(n_checked),
                  "n_failed": int(n_failed), "pct_failed": round(pct * 100, 2),
                  "status": status, "detail": detail})


# อ่านไฟล์ CSV (ระวังรหัส "NA" ของนามิเบียเหมือนตอน clean)
def read(path) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


# ---------- rules on cleaned tables ----------

# กฎ 1: ห้ามมีแถวซ้ำ เช่น ไทยปี 2023 ต้องมีแค่แถวเดียว
def r01_unique_key(t: dict) -> None:
    for name, key in KEYS.items():
        df = t[name]
        dup = df.duplicated(key, keep=False)
        record("R01", "uniqueness", name, ",".join(key), "key is unique", "error", len(df), dup.sum())


# กฎ 2: รหัสประเทศทุกตัวต้องมีอยู่จริงในตารางประเทศกลาง
def r02_referential(t: dict) -> None:
    ref = set(t["country_reference"]["iso3"])
    checks = [("cloudflare_country_year", "iso3", None), ("cloudflare_l3_vectors", "iso3", None),
              ("wb_econ", "iso3", None), ("wb_digital", "iso3", None), ("wb_governance", "iso3", None),
              ("vdem_country_year", "iso3", None), ("gci_country_edition", "iso3", None),
              ("bgp_country_year", "iso3", None), ("cloudflare_attack_pairs", "target_iso3", None),
              ("cloudflare_attack_pairs", "origin_iso3", "origin_is_country"),
              ("cloudflare_timeseries_weekly", "iso3", "scope")]
    for name, col, scope in checks:
        df = t[name]
        if scope == "origin_is_country":
            df = df[df[scope]]
        elif scope == "scope":
            df = df[df[scope] == "country"]
        bad = ~df[col].isin(ref)
        record("R02", "referential integrity", name, col, "code exists in country_reference", "error",
               len(df), bad.sum(), ", ".join(sorted(set(df.loc[bad, col].astype(str))))[:200])


# กฎ 3: ค่าต้องเป็นไปได้ เช่น เปอร์เซ็นต์ไม่ติดลบและไม่เกิน 100
def r03_ranges(t: dict) -> None:
    for name, cols, lo, hi in RANGES:
        for c in cols:
            s = t[name][c].dropna()
            bad = ~s.between(lo, hi)
            record("R03", "validity", name, c, f"value in [{lo}, {hi}]", "error", len(s), bad.sum())


# กฎ 4: ค่าที่ควรรวมกันได้ตามจริงต้องรวมได้ เช่น IPv4 + IPv6 = 100%
def r04_internal_consistency(t: dict) -> None:
    cf = t["cloudflare_country_year"]
    ip = cf[["ipv4_percent", "ipv6_percent"]].dropna()
    bad = (ip.sum(axis=1) - 100).abs() > 0.5
    record("R04", "consistency", "cloudflare_country_year", "ipv4_percent+ipv6_percent",
           "sum = 100 (+/-0.5)", "warn", len(ip), bad.sum())
    mit = cf[["origin_mitig_waf_percent", "origin_mitig_ddos_percent", "origin_mitig_bot_percent"]].dropna()
    s = mit.sum(axis=1)
    record("R04", "consistency", "cloudflare_country_year", "origin_mitig_*", "sum <= 100.5", "warn",
           len(mit), (s > 100.5).sum(), f"median sum = {s.median():.1f} (rest = other mitigation products)")
    for c in ["target_ddos_percent", "origin_ddos_percent", "target_l7_mitigated_percent",
              "origin_l7_mitigated_percent"]:
        tot = cf.groupby("year")[c].sum(min_count=1).dropna()
        bad = (tot - 100).abs() > 1
        record("R04", "consistency", "cloudflare_country_year", c, "world shares sum to 100 (+/-1) per year",
               "warn", len(tot), bad.sum(), "sums: " + ", ".join(f"{y}={v:.1f}" for y, v in tot.items()))
    g = t["gci_country_edition"]
    g24 = g[g["edition"] == 2024]
    pil = g24[[c for c in g.columns if c.startswith("pillar_")]].sum(axis=1)
    record("R04", "consistency", "gci_country_edition", "gci_score_100", "2024 score = sum of pillars",
           "warn", len(g24), ((pil - g24["gci_score_100"]).abs() > 0.01).sum())


# กฎ 9: ค่า V-Dem ที่มีผู้เชี่ยวชาญให้คะแนนแค่ 1-3 คน ถือว่าน่าเชื่อถือน้อย
# ไม่แก้ข้อมูล แค่บันทึกเป็น WARN ในรายงาน (dq_results.csv) ว่ามีกี่ค่า
def r09_reliability(t: dict) -> None:
    v = t["vdem_country_year"]
    for c in ["v2smgovcapsec_nr", "v2smprivcon_nr"]:
        s = v[c].dropna()
        few = s <= FEW_CODERS
        record("R09", "reliability", "vdem_country_year", c, f"coders > {FEW_CODERS}", "warn", len(s), few.sum(),
               "few-coder country-years: " + ", ".join(sorted(set(v.loc[s[few].index, "iso3"])))[:200])


# ---------- rules on the integrated table ----------

# กฎ 5: คอลัมน์ไหนมีช่องว่างเกิน 30% ในปีไหน
def r05_completeness(cy: pd.DataFrame) -> None:
    """Missing share per column per year, on rows that are real World Bank countries."""
    base = cy[cy["in_worldbank"]]
    skip = {"iso3", "iso2", "country_name", "year", "in_worldbank"}
    for c in [c for c in cy.columns if c not in skip and not c.startswith("has_")]:
        for y, g in base.groupby("year"):
            miss = g[c].isna()
            if miss.mean() > MISSING_WARN:
                record("R05", "completeness", "country_year", c, f"missing <= {MISSING_WARN:.0%} (year {y})",
                       "warn", len(g), miss.sum())
    record("R05", "completeness", "country_year", "(all other columns)",
           f"missing <= {MISSING_WARN:.0%} per year", "warn", len(base), 0, "columns not listed passed")


# กฎ 6: แต่ละแหล่งข้อมูลจับคู่กับประเทศได้กี่ % (ควรได้ 80% ขึ้นไป)
def r06_join_coverage(cy: pd.DataFrame) -> None:
    base = cy[cy["in_worldbank"]]
    for c in [c for c in cy.columns if c.startswith("has_") and c != "has_population"]:
        miss = ~base[c]
        record("R06", "join coverage", "country_year", c, f"matched >= {COVERAGE_WARN:.0%} of World Bank rows",
               "warn", len(base), miss.sum(),
               f"matched {base[c].mean():.1%}", failed_is_bad=base[c].mean() < COVERAGE_WARN)


# กฎ 7: ตรวจข้ามแหล่ง ประเทศที่มีคนใช้เน็ตเยอะ (World Bank) ควรมี traffic เยอะ (Cloudflare)
# ถ้าสองแหล่งไปในทางเดียวกัน แปลว่าข้อมูลน่าเชื่อถือ
def r07_cross_source(cy: pd.DataFrame) -> None:
    """Cloudflare traffic share and World Bank internet users come from unrelated measurement
    systems; if both are right, countries with more internet users should send more traffic."""
    d = cy.assign(users=cy["internet_users_pct"] / 100 * cy["population"])
    for y, g in d.groupby("year"):
        g = g[["http_traffic_percent", "users"]].dropna()
        if len(g) < 10:
            record("R07", "cross-source consistency", "country_year", "http_traffic_percent ~ internet users",
                   f"Spearman rho >= {CROSS_RHO} (year {y})", "warn", len(g), 0,
                   "not enough overlapping rows to test", failed_is_bad=False)
            continue
        rho = g["http_traffic_percent"].rank().corr(g["users"].rank())  # Spearman = Pearson on ranks
        record("R07", "cross-source consistency", "country_year", "http_traffic_percent ~ internet users",
               f"Spearman rho >= {CROSS_RHO} (year {y})", "warn", len(g), int(rho < CROSS_RHO),
               f"rho = {rho:.3f}")


# กฎ 8: หาค่าที่สูงหรือต่ำผิดปกติ ไม่ลบและไม่แก้ข้อมูล (เพราะอาจเป็นค่าจริง)
# แค่บันทึกเป็น WARN ในรายงาน (dq_results.csv) พร้อมตัวอย่างประเทศ-ปีที่ผิดปกติ
def r08_outliers(cy: pd.DataFrame) -> None:
    """Robust z = 0.6745 * (x - median) / MAD. Flag only; extreme values can be real."""
    skip = {"year", "n_sources_available", "gci_edition_used", "gci_age_years"}
    num = [c for c in cy.select_dtypes("number").columns if c not in skip]
    for c in num:
        s = cy[c].dropna()
        # Size variables (population, ASNs, traffic share) are heavily right-skewed: on a raw scale
        # every large country looks extreme. Test those on a log scale instead.
        log_scale = s.min() >= 0 and s.skew() > 2 and (s == 0).mean() < 0.05  # not for zero-inflated
        if log_scale and (s > 0).any():
            s = np.log(s + s[s > 0].min() / 2)  # small offset keeps zeros finite
        mad = (s - s.median()).abs().median()
        if len(s) < 10 or mad == 0:
            continue
        z = 0.6745 * (s - s.median()) / mad
        out = z.abs() > OUTLIER_Z
        if out.any():
            top = cy.loc[z[out].abs().sort_values(ascending=False).index]
            record("R08", "plausibility", "country_year", c,
                   f"robust |z| <= {OUTLIER_Z}" + (" (log scale)" if log_scale else ""), "warn", len(s), out.sum(),
                   "e.g. " + ", ".join(f"{a}-{b}" for a, b in zip(top["iso3"].head(5), top["year"].head(5))))


# กฎ 10: ปีล่าสุดมีข้อมูลครบกี่ % ของประเทศ
def r10_timeliness(cy: pd.DataFrame) -> None:
    """Share of World Bank countries with a value in the latest year, per source column."""
    latest = cy["year"].max()
    base = cy[cy["in_worldbank"] & (cy["year"] == latest)]
    cols = ["target_ddos_percent", "origin_ddos_percent", "origin_mitig_ddos_percent", "http_traffic_percent", "gdp_per_capita", "internet_users_pct",
            "broadband_subs_per_100", "gov_effectiveness", "v2smgovcapsec", "routed_asn_count", "gci_score_100"]
    for c in cols:
        miss = base[c].isna()
        record("R10", "timeliness", "country_year", c, f"has value in {latest} for >= {COVERAGE_WARN:.0%} of countries",
               "warn", len(base), miss.sum(), f"available {1 - miss.mean():.1%}",
               failed_is_bad=(1 - miss.mean()) < COVERAGE_WARN)


# กฎ 11: ทุกคอลัมน์ต้องมีคำอธิบายใน data dictionary
def r11_dictionary() -> None:
    for c in data_dictionary.coverage(data_dictionary.load()):
        record("R11", "documentation", c["table"], "(all)", "every column documented in data_dictionary.yaml",
               "warn", 1, int(bool(c["undocumented"] or c["missing_in_data"])),
               f"undocumented={c['undocumented']} not_in_data={c['missing_in_data']}")


# เขียนรายงานสรุปผลการตรวจ (dq_summary.md)
def render_summary(res: pd.DataFrame) -> str:
    counts = res["status"].value_counts().to_dict()
    L = ["# Data quality report", "",
         f"Rules run: {len(res)}  ·  PASS {counts.get('PASS', 0)}  ·  WARN {counts.get('WARN', 0)}  ·  "
         f"FAIL {counts.get('FAIL', 0)}", "",
         "FAIL = error rule broken (pipeline stops). WARN = reported, pipeline continues. "
         "Full detail: `reports/dq/dq_results.csv`. Cleaning actions: `data/cleaned/_cleaning_log.csv`.", "",
         "## Summary by rule", "", "| Rule | Dimension | Checks | PASS | WARN | FAIL |", "|---|---|---|---|---|---|"]
    for (rid, dim), g in res.groupby(["rule_id", "dimension"]):
        v = g["status"].value_counts()
        L.append(f"| {rid} | {dim} | {len(g)} | {v.get('PASS', 0)} | {v.get('WARN', 0)} | {v.get('FAIL', 0)} |")
    bad = res[res["status"] != "PASS"]
    L += ["", "## Findings (WARN / FAIL)", "",
          "| Rule | Table | Column | Check | Failed | % | Detail |", "|---|---|---|---|---|---|---|"]
    for r in bad.itertuples():
        L.append(f"| {r.rule_id} {r.status} | {r.table} | `{r.column}` | {r.check} | {r.n_failed}/{r.n_checked} | "
                 f"{r.pct_failed} | {str(r.detail).replace('|', '/')} |")
    return "\n".join(L) + "\n"


# รันกฎทั้งหมด บันทึกผล ถ้ามีข้อที่ไม่ผ่านแบบร้ายแรงจะส่งสัญญาณให้ Airflow หยุด
def main() -> int:
    _rows.clear()
    tables = {n: read(CLEANED / f"{n}.csv") for n in KEYS}
    cy = read(INTEGRATED / "country_year.csv")
    for rule in (r01_unique_key, r02_referential, r03_ranges, r04_internal_consistency, r09_reliability):
        rule(tables)
    for rule in (r05_completeness, r06_join_coverage, r07_cross_source, r08_outliers, r10_timeliness):
        rule(cy)
    r11_dictionary()

    res = pd.DataFrame(_rows)
    DQ_DIR.mkdir(parents=True, exist_ok=True)
    res.to_csv(DQ_DIR / "dq_results.csv", index=False, encoding="utf-8")
    (DQ_DIR / "dq_summary.md").write_text(render_summary(res), encoding="utf-8")
    n_fail = (res["status"] == "FAIL").sum()
    log.info("DQ: %d checks, %d WARN, %d FAIL", len(res), (res["status"] == "WARN").sum(), n_fail)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
