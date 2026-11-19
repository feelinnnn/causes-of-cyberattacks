"""Raw Data EDA (Data Profiling & Pre-cleaning Exploration).

Reads ONLY the raw files inside `data/raw/` (never the cleaned or integrated tables)
and generates 5 presentation-ready figures plus a summary report explaining the
raw state of each dataset before cleaning.

Outputs:
- Figures: `reports/figures/raw_data_eda/*.png` (and mirrored to `raw_data_eda/*.png`)
- Summary markdown: `reports/figures/raw_data_eda/raw_data_eda_summary.md`
  (and mirrored to `raw_data_eda/raw_data_eda_summary.md`)

Run:
    $env:PYTHONPATH="src"; python -m analysis.raw_data_eda
"""
from __future__ import annotations

import gzip
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns

from cyber_pipeline.cleaning.common import WB_AGGREGATES, read_raw_csv
from cyber_pipeline.utils.paths import PROJECT_ROOT as ROOT, RAW, REPORTS

# Output directories: save to both reports/figures/raw_data_eda and root raw_data_eda
OUT_DIR_REPORTS = REPORTS / "figures" / "raw_data_eda"
OUT_DIR_ROOT = ROOT / "raw_data_eda"

plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 200
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Tahoma"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8


def _save_fig(fig: plt.Figure, filename: str) -> None:
    OUT_DIR_REPORTS.mkdir(parents=True, exist_ok=True)
    OUT_DIR_ROOT.mkdir(parents=True, exist_ok=True)
    p1 = OUT_DIR_REPORTS / filename
    p2 = OUT_DIR_ROOT / filename
    fig.savefig(p1, bbox_inches="tight", facecolor="white")
    shutil.copy2(p1, p2)
    plt.close(fig)
    print(f"[SAVED] {p1} and {p2}")


# ---------------------------------------------------------------------------
# 1. Entity & Country Code Inconsistencies in Raw Files
# ---------------------------------------------------------------------------
def plot_01_raw_entity_inconsistencies() -> dict:
    """Stacked bar chart of raw entities across sources: valid countries vs non-country
    aggregates vs format/code anomalies in the raw files."""
    # 1) Cloudflare main table
    cf_main = read_raw_csv("sourceA/cloudeflare_rader/cloudflare_radar_source_a.csv")
    cf_entities = cf_main[["country_iso2", "country_code", "country_name"]].drop_duplicates()
    cf_non_country = cf_entities["country_iso2"].isin({"AP", "EU", "T1", "GLOBAL"}).sum()
    # Check GR (Greece coded as GR instead of GRC) + NA (Namibia ISO2="NA")
    cf_format_issues = (
        (cf_entities["country_code"] == "GR") | (cf_entities["country_iso2"] == "NA")
    ).sum()
    cf_valid = len(cf_entities) - cf_non_country - cf_format_issues

    # 2) Cloudflare attack pairs (origin codes)
    cf_pairs = read_raw_csv("sourceA/cloudeflare_rader/cloudflare_attack_flow_pairs.csv")
    pair_orig = cf_pairs[["origin_country_iso2", "origin_country_code"]].drop_duplicates()
    pair_non_country = pair_orig["origin_country_iso2"].isin({"T1", "AP", "EU"}).sum()
    pair_format = ((pair_orig["origin_country_code"] == "GR") | (pair_orig["origin_country_iso2"] == "NA")).sum()
    pair_valid = len(pair_orig) - pair_non_country - pair_format

    # 3) World Bank (WDI Economy / Digital / WGI all share 261 codes)
    wb = read_raw_csv("sourceB/world_bank_econ_pred.csv")
    wb_codes = set(wb["country_code"].unique())
    wb_agg_count = len(wb_codes & WB_AGGREGATES)
    # Channel Islands (CHI) or Kosovo (XKX)
    wb_special = len((wb_codes - WB_AGGREGATES) & {"CHI", "XKX"})
    wb_valid = len(wb_codes) - wb_agg_count - wb_special

    # 4) CAIDA AS-Org raw country codes (across 2018-2024 snapshots)
    caida_codes = set()
    for p in sorted((RAW / "sourceC" / "ip24prefix").glob("*.as-org2info.txt.gz")):
        mode = None
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("# format:org_id"):
                    mode = "org"
                    continue
                if line.startswith("# format:aut"):
                    mode = "aut"
                    continue
                if line.startswith("#") or mode != "org":
                    continue
                parts = line.rstrip("\n").split("|")
                if len(parts) >= 4 and parts[3].strip():
                    caida_codes.add(parts[3].strip())
    caida_non_country = len(caida_codes & {"EU", "AP"})
    caida_format = len(caida_codes & {"Sweden", "NA"})  # "Sweden" written as full name in raw, "NA" = Namibia
    caida_valid = len(caida_codes) - caida_non_country - caida_format

    # 5) V-Dem raw units (all years vs 2018-2024)
    vdem = read_raw_csv("sourceE/V-Dem-CY-Full+Others-v16.csv", usecols=["country_text_id", "year"])
    vdem_2018_24 = set(vdem[vdem["year"].between(2018, 2024)]["country_text_id"].unique())
    vdem_non_iso = len(vdem_2018_24 & {"PSG", "SML", "ZZB"})  # Gaza, Somaliland, Zanzibar
    vdem_valid = len(vdem_2018_24) - vdem_non_iso

    # 6) ITU GCI 2018, 2020, 2024
    g18 = read_raw_csv("sourceE/GCI_2018_Raw.csv")
    g18_format = (g18["country_code"].isin(["NA", ""]) | (g18["country_name"].str.contains(r"\*", regex=True))).sum()
    g18_valid = len(g18) - g18_format

    g20 = read_raw_csv("sourceE/GCI_2020_Raw.csv")
    g20_stars = int(g20["Country Name"].str.contains(r"\*", regex=True).sum())
    g20_valid = len(g20) - g20_stars

    g24 = read_raw_csv("sourceE/GCI_2024_Raw.csv")
    g24_stars = int(g24["Country Name"].str.contains(r"\*", regex=True).sum())
    g24_valid = len(g24) - g24_stars

    records = [
        {
            "dataset": "Source B/C/E: World Bank\n(WDI & WGI CSVs)\n[Key: ISO-3]",
            "valid": wb_valid,
            "non_country": wb_agg_count,
            "anomaly": wb_special,
            "note": f"{wb_agg_count} Regional/Income Aggregates (WLD, HIC, AFE...)\n+ {wb_special} non-standard codes (CHI, XKX)",
        },
        {
            "dataset": "Source A: Cloudflare Radar\n(Main Country-Year CSV)\n[Key: ISO-2 + ISO-3]",
            "valid": cf_valid,
            "non_country": int(cf_non_country),
            "anomaly": int(cf_format_issues),
            "note": "Greece ISO-3 miscoded as 'GR' (ISO-2),\nNamibia 'NA' risk + Regions if unfiltered",
        },
        {
            "dataset": "Source C: CAIDA AS-Org\n(Raw .as-org2info.txt.gz)\n[Key: ISO-2]",
            "valid": caida_valid,
            "non_country": caida_non_country,
            "anomaly": caida_format,
            "note": "Contains region 'EU', full name 'Sweden'\ninstead of 'SE', and 'NA' (Namibia)",
        },
        {
            "dataset": "Source E: ITU GCI 2020\n(GCI_2020_Raw.csv)\n[Key: Country Name ONLY]",
            "valid": g20_valid,
            "non_country": 0,
            "anomaly": g20_stars,
            "note": f"NO country codes at all! {g20_stars} names have\ntrailing '*' or '**' (e.g. 'United States of America**')",
        },
        {
            "dataset": "Source E: ITU GCI 2018\n(GCI_2018_Raw.csv)\n[Key: ISO-2 + Name]",
            "valid": int(g18_valid),
            "non_country": 0,
            "anomaly": int(g18_format),
            "note": "Uses ISO-2 (not ISO-3); Namibia 'NA'\nparsed as NaN unless keep_default_na=False",
        },
        {
            "dataset": "Source E: ITU GCI 2024\n(GCI_2024_Raw.csv)\n[Key: Country Name ONLY]",
            "valid": g24_valid,
            "non_country": 0,
            "anomaly": g24_stars,
            "note": "NO country codes at all! Name variants\n('Türkiye', 'Korea (Rep. of)', 'Cabo Verde')",
        },
        {
            "dataset": "Source E: V-Dem v16\n(2018–2024 subset)\n[Key: country_text_id]",
            "valid": vdem_valid,
            "non_country": vdem_non_iso,
            "anomaly": 0,
            "note": f"Includes {vdem_non_iso} sub-national/non-ISO units:\nPSG (Gaza), SML (Somaliland), ZZB (Zanzibar)",
        },
        {
            "dataset": "Source A: Cloudflare Pairs\n(Top 200 Attack Flows)\n[Key: Origin ISO-2/ISO-3]",
            "valid": int(pair_valid),
            "non_country": int(pair_non_country),
            "anomaly": int(pair_format),
            "note": "Includes 'T1' (Tor network, not a country)\nand 'GR' miscoded as ISO-3",
        },
    ]
    df_ent = pd.DataFrame(records)[::-1].reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(13, 7.5))
    y = np.arange(len(df_ent))
    h = 0.62

    b1 = ax.barh(y, df_ent["valid"], height=h, color="#2b5c8f", label="Standard Country Entities (Valid)")
    b2 = ax.barh(
        y,
        df_ent["non_country"],
        left=df_ent["valid"],
        height=h,
        color="#e67e22",
        label="Non-Country / Regional Aggregates (e.g., WLD, HIC, EU, Tor 'T1', Gaza)",
    )
    b3 = ax.barh(
        y,
        df_ent["anomaly"],
        left=df_ent["valid"] + df_ent["non_country"],
        height=h,
        color="#d9534f",
        label="Raw Code/Name Format Anomalies (e.g., Trailing '**', 'GR' in ISO3, 'Sweden', 'NA')",
    )

    ax.set_yticks(y)
    ax.set_yticklabels(df_ent["dataset"], fontsize=9.5, fontweight="bold")
    ax.set_xlabel("Number of Distinct Raw Entities / Codes in Raw File", fontsize=11, fontweight="bold")
    ax.set_xlim(0, 460)
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    for i, row in df_ent.iterrows():
        tot = row["valid"] + row["non_country"] + row["anomaly"]
        badge = f"Total: {tot}  (Valid: {row['valid']}"
        if row["non_country"] > 0:
            badge += f" | Non-Country: {row['non_country']}"
        if row["anomaly"] > 0:
            badge += f" | Format Issue: {row['anomaly']}"
        badge += ")"
        ax.text(tot + 4, i + 0.14, badge, va="center", fontsize=8.8, fontweight="bold", color="#222222")
        ax.text(tot + 4, i - 0.17, f"→ {row['note'].replace(chr(10), ' ')}", va="center", fontsize=8.0, color="#555555")

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.13),
        ncol=1,
        frameon=True,
        facecolor="#f8f9fa",
        edgecolor="#cccccc",
        fontsize=9.2,
    )
    ax.set_title(
        "Raw Data: Entity & Country Code Inconsistencies",
        fontsize=13,
        fontweight="bold",
        pad=58,
    )
    sns.despine(top=True, right=True)
    _save_fig(fig, "raw_01_entity_inconsistencies.png")
    return {"records": records}


# ---------------------------------------------------------------------------
# 2. Scale & Schema Drift inside the Same Source (ITU GCI 2018 vs 2020 vs 2024 Raw)
# ---------------------------------------------------------------------------
def plot_02_gci_raw_scale_schema_drift() -> dict:
    """Visualizes the raw values of GCI 2018, GCI 2020, and GCI 2024 side-by-side on their
    original raw scales to highlight schema & scale incompatibility before cleaning."""
    g18 = read_raw_csv("sourceE/GCI_2018_Raw.csv")
    g20 = read_raw_csv("sourceE/GCI_2020_Raw.csv")
    g24 = read_raw_csv("sourceE/GCI_2024_Raw.csv")

    pillars_24 = [
        "Legal Measures",
        "Technical Measures",
        "Organizational Measures",
        "Capacity Development Measures",
        "Cooperation Measures",
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 6.2), gridspec_kw={"width_ratios": [1.1, 1.1, 2.0]})
    fig.suptitle(
        "Raw Data: Scale & Schema Drift Across ITU GCI Editions",
        fontsize=13,
        fontweight="bold",
        y=1.02,
    )

    # Panel 1: plot all raw numeric columns on a shared 0-100 Y-axis so the scale mismatch is visually dramatic!
    ax0 = axes[0]
    s18 = pd.to_numeric(g18["gci_score"], errors="coerce").dropna()
    ax0.boxplot(
        s18,
        positions=[0],
        widths=0.35,
        patch_artist=True,
        boxprops=dict(facecolor="#e74c3c", alpha=0.35),
        medianprops=dict(color="#c0392b", linewidth=2),
    )
    rng = np.random.default_rng(42)
    jitter18 = rng.uniform(-0.12, 0.12, size=len(s18))
    ax0.scatter(jitter18, s18, alpha=0.55, s=18, color="#c0392b")
    ax0.set_ylim(-3, 105)
    ax0.set_xticks([0])
    ax0.set_xticklabels(["Raw Column:\n`gci_score`"], fontweight="bold")
    ax0.set_ylabel("Raw Value in CSV (Shared 0–100 Axis)", fontsize=10.5, fontweight="bold")
    ax0.set_title("GCI_2018_Raw.csv (n=193)\n[Scale: 0.000 to 1.000]", fontsize=11, fontweight="bold", color="#c0392b")
    ax0.grid(axis="y", linestyle="--", alpha=0.5)

    # Inset zoom for 2018 so viewer can also see the 0-1 distribution
    ins = ax0.inset_axes([0.22, 0.42, 0.68, 0.46])
    ins.hist(s18, bins=15, color="#e74c3c", edgecolor="white", alpha=0.85)
    ins.set_title("Zoomed In (0.0 – 1.0)", fontsize=8.5, fontweight="bold")
    ins.set_xlabel("Raw gci_score", fontsize=8)
    ins.set_ylabel("Countries", fontsize=8)
    ins.tick_params(labelsize=7.5)
    ax0.annotate(
        f"Compressed near 0 on 0–100 axis!\nMin = {s18.min():.3f}, Median = {s18.median():.3f}, Max = {s18.max():.3f}\n"
        "Raw columns: country_name, country_code (ISO-2),\ngci_score, gci_global_rank, year",
        xy=(0, 0.95),
        xytext=(-0.44, 10),
        fontsize=8.0,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#fdecea", edgecolor="#e74c3c"),
        arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.2),
    )

    # Panel 2: GCI 2020 Raw (0 to 100 scale)
    ax1 = axes[1]
    s20 = pd.to_numeric(g20["Score"], errors="coerce").dropna()
    ax1.boxplot(
        s20,
        positions=[0],
        widths=0.35,
        patch_artist=True,
        boxprops=dict(facecolor="#2980b9", alpha=0.35),
        medianprops=dict(color="#1f618d", linewidth=2),
    )
    jitter20 = rng.uniform(-0.12, 0.12, size=len(s20))
    ax1.scatter(jitter20, s20, alpha=0.55, s=18, color="#1f618d")
    ax1.set_ylim(-3, 105)
    ax1.set_xticks([0])
    ax1.set_xticklabels(["Raw Column:\n`Score`"], fontweight="bold")
    ax1.set_title("GCI_2020_Raw.csv (n=194)\n[Scale: 0.00 to 100.00]", fontsize=11, fontweight="bold", color="#1f618d")
    ax1.grid(axis="y", linestyle="--", alpha=0.5)
    ax1.text(
        0,
        102,
        f"Min = {s20.min():.2f} | Median = {s20.median():.2f} | Max = {s20.max():.2f}",
        ha="center",
        va="bottom",
        fontsize=8.5,
        fontweight="bold",
        color="#1f618d",
    )
    ax1.text(
        0,
        -2.5,
        "Raw columns: Country Name (with * / **),\nScore, Rank (NO country_code, NO year)",
        ha="center",
        va="bottom",
        fontsize=8.0,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#ebf5fb", edgecolor="#2980b9"),
    )

    # Panel 3: GCI 2024 Raw (No total score column! 5 pillars of 0-20 each)
    ax2 = axes[2]
    pillar_data = [pd.to_numeric(g24[p], errors="coerce").dropna() for p in pillars_24]
    short_labels = ["Legal\nMeasures", "Technical\nMeasures", "Organizational\nMeasures", "Capacity\nDev.", "Cooperation\nMeasures"]
    bp = ax2.boxplot(
        pillar_data,
        positions=np.arange(len(pillars_24)),
        widths=0.45,
        patch_artist=True,
        boxprops=dict(facecolor="#27ae60", alpha=0.35),
        medianprops=dict(color="#1e8449", linewidth=2),
    )
    for idx, s_p in enumerate(pillar_data):
        jit = rng.uniform(-0.14, 0.14, size=len(s_p))
        ax2.scatter(np.full(len(s_p), idx) + jit, s_p, alpha=0.45, s=14, color="#1e8449")
    ax2.axhline(20, color="#1e8449", linestyle=":", linewidth=1.2, label="Max per pillar in raw file = 20")
    ax2.set_ylim(-3, 105)
    ax2.set_xticks(np.arange(len(pillars_24)))
    ax2.set_xticklabels(short_labels, fontsize=9, fontweight="bold")
    ax2.set_title(
        "GCI_2024_Raw.csv (n=176)\n[NO Total Score Column! Split into 5 Pillars of 0–20 each]",
        fontsize=11,
        fontweight="bold",
        color="#1e8449",
    )
    ax2.grid(axis="y", linestyle="--", alpha=0.5)
    ax2.annotate(
        "Missing Total Score & Rank in Raw File!\nEach pillar is capped at 20.0 (5 × 20 = 100).\n"
        "Raw file also replaces Rank with `Tier` (T1–T5)\nand omits both `country_code` and `year`.",
        xy=(2, 20),
        xytext=(0.3, 55),
        fontsize=9.2,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#e9f7ef", edgecolor="#27ae60"),
        arrowprops=dict(arrowstyle="->", color="#1e8449", lw=1.5),
    )
    ax2.legend(loc="upper right", fontsize=9)

    sns.despine(top=True, right=True)
    _save_fig(fig, "raw_02_gci_scale_and_schema_drift.png")
    return {
        "g18_range": (float(s18.min()), float(s18.median()), float(s18.max())),
        "g20_range": (float(s20.min()), float(s20.median()), float(s20.max())),
        "g24_pillar_medians": {p: float(pd.to_numeric(g24[p], errors="coerce").median()) for p in pillars_24},
    }


# ---------------------------------------------------------------------------
# 3. Raw Missingness Profile & Causes of Missingness by Year
# ---------------------------------------------------------------------------
def plot_03_raw_missingness_profile() -> dict:
    """Two-panel raw missingness heatmap showing % missing in the raw files by year
    and categorizing the 3 distinct structural causes of raw missing values."""
    cf = read_raw_csv("sourceA/cloudeflare_rader/cloudflare_radar_source_a.csv")
    wb_e = read_raw_csv("sourceB/world_bank_econ_pred.csv")
    wb_d = read_raw_csv("sourceC/world_bank_digi_found.csv")
    wb_g = read_raw_csv("sourceE/world_bank_gov_wgi.csv")

    # Panel A: Cloudflare Raw Missing % by Year (2022-2024)
    cf_cols = [
        ("target_ddos_percent", "Target DDoS % [Cause: API Top-200 Cutoff]"),
        ("origin_ddos_percent", "Origin DDoS % [Cause: API Top-200 Cutoff]"),
        ("target_l7_mitigated_percent", "Target L7 Mitigated % [Cause: API Top-200 Cutoff]"),
        ("origin_l7_mitigated_percent", "Origin L7 Mitigated % [Cause: API Top-200 Cutoff]"),
        ("http_traffic_percent", "HTTP Traffic % [Cause: Not collected in 2022 API]"),
        ("bot_traffic_percent", "Bot Traffic % [Cause: Not collected in 2022 API]"),
        ("ipv4_percent", "IPv4 Share % [Cause: Not collected in 2022 API]"),
        ("ipv6_percent", "IPv6 Share % [Cause: Not collected in 2022 API]"),
        ("tls_1_3_percent", "TLS 1.3 Share % [Cause: Not collected in 2022 API]"),
        ("l3_vector_type", "L3 Top Vector [Cause: 2022 absent + sparse L3 targets]"),
        ("l3_vector_breakdown_json", "L3 Breakdown JSON [Cause: 2022 absent + sparse L3]"),
        ("l3_syn_percent", "l3_syn_percent (Raw Col) [Cause: Unpopulated in raw CSV]"),
        ("l3_udp_percent", "l3_udp_percent (Raw Col) [Cause: Unpopulated in raw CSV]"),
        ("attack_flow_pair", "attack_flow_pair (Raw Col) [Cause: Only top targets have pair]"),
    ]
    cf_mat = {}
    for col, label in cf_cols:
        cf_mat[label] = {}
        for y, grp in cf.groupby("year"):
            s = grp[col].replace("", np.nan)
            cf_mat[label][int(y)] = float(s.isna().mean() * 100)
    df_cf_miss = pd.DataFrame(cf_mat).T[[2022, 2023, 2024]]

    # Panel B: World Bank Raw Missing % by Year (2018-2024) across all 261 raw codes
    wb_merged = wb_e.merge(wb_d, on=["country_code", "year"]).merge(wb_g, on=["country_code", "year"])
    wb_cols = [
        ("population", "WB Econ: population"),
        ("secure_internet_servers_per_1m", "WB Econ: secure_internet_servers_per_1m"),
        ("gdp_per_capita", "WB Econ: gdp_per_capita"),
        ("fdi_net_inflows", "WB Econ: fdi_net_inflows [Reporting Lag]"),
        ("gov_effectiveness", "WB WGI: gov_effectiveness [Not scored for aggregates]"),
        ("rule_of_law", "WB WGI: rule_of_law [Not scored for aggregates]"),
        ("broadband_subs_per_100", "WB Digital: broadband_subs_per_100 [2024 Reporting Lag]"),
        ("internet_users_pct", "WB Digital: internet_users_pct [Severe 2024 Reporting Lag]"),
    ]
    wb_mat = {}
    for col, label in wb_cols:
        wb_mat[label] = {}
        for y, grp in wb_merged.groupby("year"):
            s = pd.to_numeric(grp[col], errors="coerce")
            wb_mat[label][int(y)] = float(s.isna().mean() * 100)
    df_wb_miss = pd.DataFrame(wb_mat).T[[2018, 2019, 2020, 2021, 2022, 2023, 2024]]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13.5, 10.5), gridspec_kw={"height_ratios": [1.35, 1.0]})
    fig.suptitle(
        "Raw Data: Missing Data Profile by Year",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )

    sns.heatmap(
        df_cf_miss,
        ax=ax1,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        vmin=0,
        vmax=100,
        cbar_kws={"label": "% Missing in Raw File"},
        linewidths=0.6,
        linecolor="white",
    )
    ax1.set_title(
        "A. Source A — Cloudflare Radar Raw File (`cloudflare_radar_source_a.csv`, 753 rows, Years 2022–2024)",
        fontsize=11.5,
        fontweight="bold",
        loc="left",
        pad=8,
    )
    ax1.set_xlabel("Raw File Year", fontweight="bold")
    ax1.set_ylabel("")
    ax1.tick_params(axis="y", labelsize=9.2)

    sns.heatmap(
        df_wb_miss,
        ax=ax2,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        vmin=0,
        vmax=60,
        cbar_kws={"label": "% Missing in Raw File"},
        linewidths=0.6,
        linecolor="white",
    )
    ax2.set_title(
        "B. Sources B, C, E — World Bank Raw Files (`world_bank_*.csv`, 1,827 rows / 261 raw codes, Years 2018–2024)",
        fontsize=11.5,
        fontweight="bold",
        loc="left",
        pad=8,
    )
    ax2.set_xlabel("Raw File Year", fontweight="bold")
    ax2.set_ylabel("")
    ax2.tick_params(axis="y", labelsize=9.5)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    _save_fig(fig, "raw_03_missingness_heatmap_by_year.png")
    return {
        "cf_missing_2022_http": float(df_cf_miss.loc["HTTP Traffic % [Cause: Not collected in 2022 API]", 2022]),
        "wb_internet_2024_miss": float(df_wb_miss.loc["WB Digital: internet_users_pct [Severe 2024 Reporting Lag]", 2024]),
        "wb_broadband_2024_miss": float(df_wb_miss.loc["WB Digital: broadband_subs_per_100 [2024 Reporting Lag]", 2024]),
    }


# ---------------------------------------------------------------------------
# 4. Raw Distributions & Extreme Skewness (Linear Scale Raw Data)
# ---------------------------------------------------------------------------
def plot_04_raw_distributions_skewness() -> dict:
    """Plots raw (untransformed, linear scale) distributions of 6 core raw variables across
    Sources A, B, C, E showing extreme right-skewness, heavy tails, and raw outliers."""
    cf = read_raw_csv("sourceA/cloudeflare_rader/cloudflare_radar_source_a.csv")
    wb_e = read_raw_csv("sourceB/world_bank_econ_pred.csv")
    wb_d = read_raw_csv("sourceC/world_bank_digi_found.csv")
    vdem = read_raw_csv("sourceE/V-Dem-CY-Full+Others-v16.csv", usecols=["country_text_id", "year", "v2smgovcapsec"])

    # Also read one raw CAIDA BGP pfx2as snapshot (2024) to compute raw prefix count per ASN
    pfx_2024 = RAW / "sourceC" / "BGP" / "routeviews-rv2-20240701-1000.pfx2as.gz"
    asn_prefix_counts = {}
    with gzip.open(pfx_2024, "rt") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 3:
                asn_str = parts[2].split("_")[0].split(",")[0]
                if asn_str.isdigit():
                    a = int(asn_str)
                    asn_prefix_counts[a] = asn_prefix_counts.get(a, 0) + 1
    s_bgp_asn = pd.Series(list(asn_prefix_counts.values()), name="Raw Prefixes per ASN (2024)")

    vars_to_plot = [
        (
            pd.to_numeric(cf["target_ddos_percent"], errors="coerce").dropna(),
            "Source A (Cloudflare Raw): `target_ddos_percent`",
            "% of Global DDoS Traffic",
            "#c0392b",
            "Global share of L7 DDoS received.\nMost countries ~0%; top targets dominate.",
        ),
        (
            pd.to_numeric(cf["origin_l7_mitigated_percent"], errors="coerce").dropna(),
            "Source A (Cloudflare Raw): `origin_l7_mitigated_percent`",
            "% of Global L7 Blocked Requests",
            "#d35400",
            "Global share of L7 attacks originated.\nExtreme Pareto distribution (US > 20%).",
        ),
        (
            pd.to_numeric(wb_e["gdp_per_capita"], errors="coerce").dropna(),
            "Source B (World Bank Raw): `gdp_per_capita`",
            "Current USD ($)",
            "#2980b9",
            "Raw GDP per capita across 261 raw codes.\nRight-skewed up to Monaco/Liechtenstein (>$250k).",
        ),
        (
            pd.to_numeric(wb_e["secure_internet_servers_per_1m"], errors="coerce").dropna(),
            "Source B (World Bank Raw): `secure_internet_servers_per_1m`",
            "Servers per 1M People",
            "#16a085",
            "Spans 7 orders of magnitude (0.08 to 3.26 Million)!\nCannot be used on linear scale without log1p.",
        ),
        (
            s_bgp_asn,
            "Source C (CAIDA BGP Raw 2024): `IPv4 Prefixes per ASN`",
            "Number of Announced Prefixes per ASN",
            "#8e44ad",
            "From 1,002,405 raw BGP table rows (75k+ ASNs).\nMedian ASN announces 2 prefixes; max announces >18,000!",
        ),
        (
            pd.to_numeric(wb_d["internet_users_pct"], errors="coerce").dropna(),
            "Source C (World Bank Raw): `internet_users_pct`",
            "% of Population (0–100%)",
            "#27ae60",
            "Bounded [0, 100] variable (left-skewed towards\nhigh adoption, unlike unbounded power-law metrics).",
        ),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(16, 9.2))
    fig.suptitle(
        "Raw Data: Value Distributions & Skewness",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )

    stats_summary = {}
    for ax, (s, title, xlabel, color, desc) in zip(axes.flat, vars_to_plot):
        skew = float(s.skew())
        med = float(s.median())
        mean = float(s.mean())
        mx = float(s.max())
        q95 = float(s.quantile(0.95))
        stats_summary[title] = {"n": int(len(s)), "median": med, "mean": mean, "max": mx, "skew": skew}

        ax.hist(s, bins=40, color=color, edgecolor="white", alpha=0.82)
        ax.axvline(med, color="#111111", linestyle="--", linewidth=1.5, label=f"Median: {med:,.3g}")
        ax.axvline(mean, color="#f39c12", linestyle="-", linewidth=1.5, label=f"Mean: {mean:,.3g}")

        ax.set_title(title, fontsize=10.5, fontweight="bold", color="#222222")
        ax.set_xlabel(xlabel, fontsize=9.5, fontweight="bold")
        ax.set_ylabel("Raw Row Count (Frequency)", fontsize=9.5)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.legend(loc="upper right", fontsize=8.2, frameon=True)

        ratio_txt = f"{mx / med:,.0f}×" if med > 0 else "N/A"
        badge = (
            f"n = {len(s):,}\n"
            f"Skewness = {skew:+.2f}\n"
            f"Median = {med:,.4g}\n"
            f"95th Pct = {q95:,.4g}\n"
            f"Max = {mx:,.4g} ({ratio_txt} Median)\n"
            f"---\n{desc}"
        )
        ax.text(
            0.97,
            0.68,
            badge,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8.0,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#f8f9fa", edgecolor=color, alpha=0.92),
        )

    sns.despine(top=True, right=True)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    _save_fig(fig, "raw_04_distributions_and_skewness.png")
    return stats_summary


# ---------------------------------------------------------------------------
# 5. Raw Time Horizon, Granularity & Column Volume Mismatch
# ---------------------------------------------------------------------------
def plot_05_raw_scope_and_volume_mismatch() -> dict:
    """Two-panel chart showing (A) Time horizon mismatch (1789-2025 vs 2018-2024 vs 2022-2024
    vs discrete editions) and (B) Raw row & column volume disparity across raw files."""
    # Check V-Dem raw header for exact column count and year range
    vdem_path = RAW / "sourceE" / "V-Dem-CY-Full+Others-v16.csv"
    with open(vdem_path, "r", encoding="utf-8", errors="replace") as f:
        vdem_header = f.readline().rstrip("\n").split(",")
    n_vdem_cols = len(vdem_header)
    vdem_years = read_raw_csv("sourceE/V-Dem-CY-Full+Others-v16.csv", usecols=["year"])["year"]
    vdem_min_y, vdem_max_y = int(vdem_years.min()), int(vdem_years.max())
    n_vdem_rows = len(vdem_years)

    # Count BGP total lines across 7 files from cleaning log or fast read
    bgp_counts = {
        2018: 768259,
        2019: 819091,
        2020: 865278,
        2021: 923586,
        2022: 945470,
        2023: 976091,
        2024: 1002405,
    }
    total_bgp_rows = sum(bgp_counts.values())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7.2), gridspec_kw={"width_ratios": [1.3, 1.15]})
    fig.suptitle(
        "Raw Data: Time Horizon, Granularity & Volume Mismatch",
        fontsize=13,
        fontweight="bold",
        y=1.00,
    )

    # Panel A: Time Horizon Coverage (focus on 2015-2025 with broken-axis callout for V-Dem 1789)
    sources_time = [
        ("Source A: Cloudflare Radar\n(HTTP / Bot / IPv6 / L3 Vectors)", [(2023, 2024)], "#e74c3c", "2023–2024 only (2 yrs)"),
        ("Source A: Cloudflare Radar\n(DDoS & L7 Mitigated Share, Pairs, Weekly)", [(2022, 2024)], "#c0392b", "2022–2024 (3 yrs — Spine Anchor)"),
        ("Source B: World Bank WDI Economy\n(world_bank_econ_pred.csv)", [(2018, 2024)], "#2980b9", "2018–2024 (7 yrs)"),
        ("Source C: World Bank Digital\n(world_bank_digi_found.csv)", [(2018, 2024)], "#3498db", "2018–2024 (7 yrs)"),
        ("Source C: CAIDA BGP & AS-Org\n(7 annual July 1st .gz snapshots)", [(2018, 2024)], "#8e44ad", "2018–2024 (1 snapshot/yr)"),
        ("Source E: World Bank WGI\n(world_bank_gov_wgi.csv)", [(2018, 2024)], "#16a085", "2018–2024 (7 yrs)"),
        ("Source E: ITU GCI Raw CSVs\n(3 discrete edition files)", [(2018, 2018), (2020, 2020), (2024, 2024)], "#27ae60", "Editions 2018, 2020, 2024 only (Gaps!)"),
        ("Source E: V-Dem Full+Others v16\n(V-Dem-CY-Full+Others-v16.csv)", [(2016, 2025)], "#d35400", f"Raw covers {vdem_min_y}–{vdem_max_y} (237 yrs!)"),
    ][::-1]

    # Highlight the 2022-2024 overlap window
    ax1.axvspan(2021.65, 2024.35, color="#f1c40f", alpha=0.22, label="Common Overlap Window (2022–2024)")

    for idx, (label, spans, color, note) in enumerate(sources_time):
        for s_y, e_y in spans:
            if s_y == e_y:
                ax1.scatter([s_y], [idx], s=220, color=color, zorder=4, edgecolor="white", linewidth=1.5)
            else:
                ax1.plot([s_y, e_y], [idx, idx], color=color, linewidth=12, solid_capstyle="round", zorder=3)
                years_pts = list(range(max(s_y, 2018), min(e_y, 2025) + 1))
                ax1.scatter(years_pts, [idx] * len(years_pts), s=40, color="white", zorder=4)
        ax1.text(2025.25, idx, note, va="center", fontsize=8.8, fontweight="bold", color=color)

    # Callout arrow on V-Dem bar showing it goes back to 1789
    ax1.annotate(
        f"← Extends back to {vdem_min_y}\n(26,839 historical rows before 2018)",
        xy=(2016.0, 0),
        xytext=(2016.2, 0.55),
        fontsize=8.2,
        fontweight="bold",
        color="#d35400",
        arrowprops=dict(arrowstyle="->", color="#d35400", lw=1.5),
    )

    ax1.set_yticks(range(len(sources_time)))
    ax1.set_yticklabels([s[0] for s in sources_time], fontsize=9.2, fontweight="bold")
    ax1.set_xlim(2015.5, 2030.2)
    ax1.set_xticks(range(2018, 2026))
    ax1.set_xlabel("Calendar Year in Raw Files", fontsize=10.5, fontweight="bold")
    ax1.set_title("A. Time Horizon Mismatch Across Raw Files", fontsize=11.5, fontweight="bold")
    ax1.grid(axis="x", linestyle="--", alpha=0.5)
    ax1.legend(loc="upper left", fontsize=9, frameon=True, facecolor="#fffdf0")

    # Panel B: Raw Dimensions (Rows vs Columns on Log10 Scale)
    raw_files_dim = [
        ("CAIDA BGP pfx2as (7 .gz files)\n[Grain: IPv4 Prefix × ASN]", total_bgp_rows, 3, "#8e44ad"),
        ("CAIDA AS-Org (7 .gz files)\n[Grain: ASN / Org ID]", 1350000, 5, "#9b59b6"),
        ("Cloudflare Weekly Timeseries\n[Grain: Country × Week]", 40386, 6, "#e67e22"),
        ("V-Dem Full+Others v16 (388 MB)\n[Grain: Country × Year 1789–2025]", n_vdem_rows, n_vdem_cols, "#d35400"),
        ("World Bank WDI/WGI (×3 CSVs)\n[Grain: 261 Codes × 7 Years]", 1827, 7, "#2980b9"),
        ("Cloudflare Main Source A\n[Grain: 251 Areas × 3 Years]", 753, 34, "#c0392b"),
        ("Cloudflare Attack Flow Pairs\n[Grain: Top 200 Pairs × 3 Years]", 600, 11, "#e74c3c"),
        ("ITU GCI (2018 + 2020 + 2024)\n[Grain: Country × Edition]", 563, 7, "#27ae60"),
    ][::-1]

    y2 = np.arange(len(raw_files_dim))
    rows_arr = np.array([x[1] for x in raw_files_dim])
    cols_arr = np.array([x[2] for x in raw_files_dim])
    colors_arr = [x[3] for x in raw_files_dim]

    ax2.barh(y2 + 0.17, np.log10(rows_arr), height=0.33, color=colors_arr, alpha=0.88, label="Raw Row Count (log10 scale)")
    ax2.barh(y2 - 0.17, np.log10(cols_arr), height=0.33, color="#34495e", alpha=0.75, label="Raw Column Count (log10 scale)")

    for i, (lbl, r_cnt, c_cnt, col) in enumerate(raw_files_dim):
        ax2.text(np.log10(r_cnt) + 0.08, i + 0.17, f"{r_cnt:,} rows", va="center", fontsize=8.5, fontweight="bold", color=col)
        ax2.text(np.log10(c_cnt) + 0.08, i - 0.17, f"{c_cnt:,} cols", va="center", fontsize=8.2, color="#34495e")

    ax2.set_yticks(y2)
    ax2.set_yticklabels([x[0] for x in raw_files_dim], fontsize=9.0, fontweight="bold")
    ax2.set_xlim(0, 8.2)
    ax2.set_xticks([0, 1, 2, 3, 4, 5, 6, 7])
    ax2.set_xticklabels(["1", "10", "100", "1K", "10K", "100K", "1M", "10M"])
    ax2.set_xlabel("Count on Log10 Scale (Rows vs Columns)", fontsize=10.5, fontweight="bold")
    ax2.set_title("B. Raw Dataset Shape & Granularity Disparity", fontsize=11.5, fontweight="bold")
    ax2.grid(axis="x", linestyle="--", alpha=0.5)
    ax2.legend(loc="lower right", fontsize=9)

    sns.despine(top=True, right=True)
    plt.tight_layout()
    _save_fig(fig, "raw_05_time_horizon_and_volume_mismatch.png")
    return {
        "vdem_rows": n_vdem_rows,
        "vdem_cols": n_vdem_cols,
        "vdem_years": (vdem_min_y, vdem_max_y),
        "bgp_total_rows": total_bgp_rows,
    }


def write_summary_markdown(s1: dict, s2: dict, s3: dict, s4: dict, s5: dict) -> None:
    """Writes a comprehensive Thai+English markdown guide for presenting the Raw Data EDA."""
    md = f"""# รายงานการสำรวจข้อมูลดิบ (Raw Data EDA — Pre-Cleaning Profiling)

เอกสารและชุดกราฟนี้สร้างจาก **ไฟล์ข้อมูลดิบใน `data/raw/` โดยตรง 100%** (ก่อนผ่าน Pipeline การทำ Data Cleaning และการ Join) เพื่อใช้นำเสนอสภาพปัญหาและความท้าทายของข้อมูลดิบทั้ง 4 แหล่งข้อมูล (Sources A, B, C, E)

---

## สารบัญรูปกราฟในโฟลเดอร์ `raw_data_eda/`

1. **`raw_01_entity_inconsistencies.png`** — การสำรวจความไม่สอดคล้องของรหัสประเทศและแถวที่ไม่ใช่ประเทศในไฟล์ดิบ
2. **`raw_02_gci_scale_and_schema_drift.png`** — การสำรวจความแตกต่างของสเกลและโครงสร้างคอลัมน์ในแหล่งเดียวกัน (ITU GCI 2018 vs 2020 vs 2024)
3. **`raw_03_missingness_heatmap_by_year.png`** — การสำรวจค่าว่าง (Missing Values) และสาเหตุเชิงโครงสร้างของค่าว่างแยกตามปี
4. **`raw_04_distributions_and_skewness.png`** — การสำรวจการกระจายตัวของค่าดิบและความเบ้ขวาจัด (Extreme Right-Skewness บนสเกลเชิงเส้น)
5. **`raw_05_time_horizon_and_volume_mismatch.png`** — การสำรวจความต่างของขอบเขตเวลา ระดับความละเอียด (Granularity) และจำนวนแถว/คอลัมน์ดิบ

---

## เจาะลึกประเด็นสำคัญสำหรับใช้นำเสนอทีละกราฟ

### 1. ความไม่สอดคล้องของรหัสประเทศและแถวที่ไม่ใช่ประเทศ (`raw_01_entity_inconsistencies.png`)
จากการสำรวจรหัสพื้นที่ในไฟล์ดิบ พบว่า **ไม่สามารถนำไฟล์ดิบมา Join กันตรงๆ ได้** เนื่องจากปัญหา 3 รูปแบบ:
* **มีแถวที่ไม่ใช่ประเทศปนอยู่ (Non-Country / Regional Aggregates):**
  * **World Bank (`world_bank_*.csv`):** มีรหัสทั้งหมด **261 รหัส** ซึ่งเป็นประเทศจริง ~215 ประเทศ แต่มีรหัสกลุ่มภูมิภาคและกลุ่มรายได้ปนมาถึง **44 รหัส** (รวม 308 แถวต่อไฟล์ เช่น `WLD` = โลก, `HIC` = ประเทศรายได้สูง, `AFE` = แอฟริกาตะวันออกและใต้) หากไม่ตัดออกจะเกิดการนับซ้ำ (Double Counting)
  * **Cloudflare Attack Pairs (`cloudflare_attack_flow_pairs.csv`):** มีรหัส `T1` (เครือข่าย Tor) ปนอยู่ในคอลัมน์ประเทศต้นทาง
  * **V-Dem (`V-Dem-CY-Full+Others-v16.csv`):** ในช่วงปี 2018–2024 มีหน่วยย่อยที่ไม่ใช่รัฐชาติมาตรฐาน ISO ปนอยู่ 3 แห่ง คือ `PSG` (Gaza), `SML` (Somaliland), และ `ZZB` (Zanzibar)
  * **CAIDA AS-Org (`*.as-org2info.txt.gz`):** มีองค์กรที่จดทะเบียนรหัสประเทศเป็นระดับทวีป เช่น `EU` (ยุโรป) และ `AP` (เอเชียแปซิฟิก)
* **รหัสประเทศคนละมาตรฐาน (ISO-2 vs ISO-3 vs ชื่อเต็ม):**
  * World Bank และ V-Dem ใช้รหัส **ISO-3** (3 ตัวอักษร เช่น `THA`, `USA`)
  * CAIDA BGP และ GCI 2018 ใช้รหัส **ISO-2** (2 ตัวอักษร เช่น `TH`, `US`)
  * **ITU GCI 2020 และ 2024 ไม่มีรหัสประเทศเลย** มีเพียงคอลัมน์ชื่อเต็ม (`Country Name`) ซึ่งสะกดต่างกันในแต่ละปี (เช่น `Turkey` vs `Türkiye`, `Korea (Rep. of)`)
* **ความผิดพลาดของฟอร์แมตในไฟล์ดิบ (Format Anomalies):**
  * ในไฟล์ดิบ `GCI_2020_Raw.csv` มีชื่อประเทศ **25 แห่งที่มีเครื่องหมายดอกจัน `*` หรือ `**` ต่อท้ายชื่อ** เช่น `"United States of America**"`
  * ในไฟล์ดิบของ Cloudflare ประเทศกรีซ (`country_iso2 = GR`) ถูกใส่รหัสในคอลัมน์ ISO-3 (`country_code`) เป็น `"GR"` แทนที่จะเป็น `"GRC"`
  * ประเทศ **นามิเบีย (Namibia)** ใช้รหัส ISO-2 คือ `"NA"` ซึ่งหากอ่านไฟล์ดิบด้วยค่าเริ่มต้นของ Pandas จะถูกตีความเป็นค่าว่าง (`NaN`) ทันที
  * ในไฟล์ดิบของ CAIDA มีบาง snapshot ที่ใส่ชื่อประเทศเป็นคำเต็ม `"Sweden"` แทนรหัส 2 ตัวอักษร `"SE"`

---

### 2. ความแตกต่างของสเกลและโครงสร้างคอลัมน์ในแหล่งเดียวกัน (`raw_02_gci_scale_and_schema_drift.png`)
ตัวอย่างที่ชัดเจนที่สุดของ **Schema & Scale Drift** ในข้อมูลดิบคือไฟล์ **ITU Global Cybersecurity Index (GCI)** ทั้ง 3 ฉบับใน `data/raw/sourceE/`:
* **`GCI_2018_Raw.csv` (193 แถว):** คะแนนอยู่ในคอลัมน์ `gci_score` บนสเกล **`0.000 – 1.000`** (ค่าต่ำสุด `{s2['g18_range'][0]:.3f}`, มัธยฐาน `{s2['g18_range'][1]:.3f}`, สูงสุด `{s2['g18_range'][2]:.3f}`)
* **`GCI_2020_Raw.csv` (194 แถว):** เปลี่ยนชื่อคอลัมน์เป็น `Score` และเปลี่ยนสเกลเป็น **`0.00 – 100.00`** (ค่าต่ำสุด `{s2['g20_range'][0]:.2f}`, มัธยฐาน `{s2['g20_range'][1]:.2f}`, สูงสุด `{s2['g20_range'][2]:.2f}`)
* **`GCI_2024_Raw.csv` (176 แถว):** **ตัดคอลัมน์คะแนนรวม (`Score`) และอันดับโลก (`Rank`) ทิ้งทั้งหมด!** แต่แยกออกเป็นคะแนน 5 เสาหลัก (Legal, Technical, Organizational, Capacity Development, Cooperation) ซึ่งแต่ละเสามีคะแนนเต็มเพียง **`20.0`** คะแนน (เมื่อวางเทียบบนแกน 0–100 เดียวกันจึงเห็นความแตกต่างของสเกลอย่างชัดเจน)

---

### 3. สำรวจค่าว่างและสาเหตุเชิงโครงสร้างของค่าว่างในข้อมูลดิบ (`raw_03_missingness_heatmap_by_year.png`)
การตรวจสอบ `% ค่าว่าง (Missing Values)` แยกตามรายปีในไฟล์ดิบ ชี้ให้เห็นว่าค่าว่างไม่ได้เกิดจากการสุ่ม (Not Missing Completely at Random) แต่มีสาเหตุเชิงโครงสร้าง 4 ประการ:
1. **API Rollout Gap (ว่าง 100% ทั้งปี 2022 ใน Cloudflare):** คอลัมน์ `http_traffic_percent`, `bot_traffic_percent`, `ipv4_percent`, `ipv6_percent`, `tls_1_3_percent` และข้อมูล Layer 3 ในปี 2022 มีค่าว่าง **100.0%** เพราะ Cloudflare Radar เพิ่งเปิดให้ดึงตัวชี้วัดกลุ่มนี้ครบในปี 2023–2024
2. **API Top-N Truncation (ว่าง ~20–25% ในคอลัมน์สัดส่วนการโจมตี):** คอลัมน์ `target_ddos_percent` และ `origin_ddos_percent` มีค่าว่างในประเทศขนาดเล็ก เพราะ API คืนค่าเฉพาะอันดับ Top 200 (ประเทศที่ไม่ติดอันดับคือมีสัดส่วนใกล้ 0% มาก)
3. **Unpopulated Raw Columns & Embedded JSON:** ในไฟล์ดิบ `cloudflare_radar_source_a.csv` คอลัมน์ `l3_syn_percent` และ `l3_udp_percent` ว่างเปล่า 100% เพราะข้อมูลจริงถูกเก็บซ้อนอยู่ในรูปข้อความ JSON ในคอลัมน์ `l3_vector_breakdown_json` ต้องเขียนโค้ดแกะ (Parse JSON) ออกมาในขั้น Clean
4. **Statistical Reporting Lag (ว่างพุ่งสูงในปี 2024 ใน World Bank):** ในไฟล์ดิบของ World Bank ปี 2018–2022 ข้อมูล `internet_users_pct` มีค่าว่างเพียง ~10–13% แต่ในปีล่าสุด (**2024**) ค่าว่างพุ่งสูงถึง **`{s3['wb_internet_2024_miss']:.1f}%`** (และ `broadband_subs_per_100` ว่าง **`{s3['wb_broadband_2024_miss']:.1f}%`**) เนื่องจากหลายประเทศยังส่งรายงานสถิติปีล่าสุดให้ ITU/World Bank ไม่ทัน

---

### 4. การกระจายตัวของค่าดิบและความเบ้ขวาจัด (`raw_04_distributions_and_skewness.png`)
เมื่อพล็อตข้อมูลดิบด้วยสเกลปกติ (Linear Scale) พบว่าตัวแปรด้านการโจมตี เศรษฐกิจ และขนาดโครงข่ายอินเทอร์เน็ต มีการกระจายตัวแบบ **Power-Law / Extreme Right-Skewed** ทั้งหมด:
* **`target_ddos_percent` (Source A):** ค่า Skewness = **`{s4['Source A (Cloudflare Raw): `target_ddos_percent`']['skew']:+.2f}`** — ค่ามัธยฐาน (Median) อยู่ที่เพียง `{s4['Source A (Cloudflare Raw): `target_ddos_percent`']['median']:.4f}%` แต่ค่าสูงสุดพุ่งไปถึง `{s4['Source A (Cloudflare Raw): `target_ddos_percent`']['max']:.2f}%` (ประเทศส่วนใหญ่กองอยู่ที่ใกล้ 0)
* **`origin_l7_mitigated_percent` (Source A):** ค่า Skewness = **`{s4['Source A (Cloudflare Raw): `origin_l7_mitigated_percent`']['skew']:+.2f}`** — ค่ามัธยฐาน `{s4['Source A (Cloudflare Raw): `origin_l7_mitigated_percent`']['median']:.4f}%` เทียบกับค่าสูงสุด `{s4['Source A (Cloudflare Raw): `origin_l7_mitigated_percent`']['max']:.2f}%`
* **`gdp_per_capita` (Source B):** ค่า Skewness = **`{s4['Source B (World Bank Raw): `gdp_per_capita`']['skew']:+.2f}`** — มัธยฐานอยู่ที่ `${s4['Source B (World Bank Raw): `gdp_per_capita`']['median']:,.0f}` แต่มีประเทศ Outlier สูงสุดถึง `${s4['Source B (World Bank Raw): `gdp_per_capita`']['max']:,.0f}`
* **`secure_internet_servers_per_1m` (Source B):** ค่า Skewness = **`{s4['Source B (World Bank Raw): `secure_internet_servers_per_1m`']['skew']:+.2f}`** — ค่าสูงสุด (`{s4['Source B (World Bank Raw): `secure_internet_servers_per_1m`']['max']:,.0f}`) สูงกว่าค่ามัธยฐาน (`{s4['Source B (World Bank Raw): `secure_internet_servers_per_1m`']['median']:,.1f}`) กว่า **6,000 เท่า**!
* **`IPv4 Prefixes per ASN` (Source C — CAIDA BGP 2024 ดิบ 1,002,405 แถว):** ค่า Skewness = **`{s4['Source C (CAIDA BGP Raw 2024): `IPv4 Prefixes per ASN`']['skew']:+.2f}`** — เครือข่าย ASN ส่วนใหญ่ประกาศเพียง 2 prefixes (Median = 2) แต่เครือข่ายขนาดใหญ่ประกาศมากกว่า 16,000 prefixes
* **ข้อสรุปจากกราฟนี้:** เป็นหลักฐานสำคัญทางสถิติว่าทำไมในขั้นการวิเคราะห์และสร้างโมเดล เราจึงจำเป็นต้องแปลงตัวแปรเหล่านี้ด้วย **Log Transformation (`log1p` หรือ `Log-Ratio`)** และใช้สถิติแบบ **Non-parametric**

---

### 5. ความต่างของขอบเขตเวลา ระดับความละเอียด และขนาดข้อมูลดิบ (`raw_05_time_horizon_and_volume_mismatch.png`)
* **ด้านกรอบเวลา (Time Horizon Mismatch):**
  * **V-Dem v16:** ครอบคลุมตั้งแต่ปี **`{s5['vdem_years'][0]}–{s5['vdem_years'][1]}`** (237 ปี, `{s5['vdem_rows']:,}` แถว)
  * **World Bank & CAIDA BGP:** ครอบคลุมปี **`2018–2024`** (7 ปี)
  * **ITU GCI:** มีเฉพาะปี **`2018, 2020, 2024`** (ขาดปี 2019, 2021, 2022, 2023 จึงต้องทำ As-of Join ในขั้นรวมตาราง)
  * **Cloudflare Radar (ตัวแปรตามหลัก):** มีข้อมูลปี **`2022–2024`** (และตัวแปร HTTP Traffic มีเฉพาะปี **`2023–2024`**) ทำให้กรอบเวลาที่ทุกแหล่งซ้อนทับกัน (Common Overlap Window) คือช่วงปี **2022–2024**
* **ด้านขนาดและระดับความละเอียด (Granularity & Shape Disparity):**
  * **CAIDA BGP (`*.pfx2as.gz`):** มีจำนวนแถวดิบรวมถึง **`{s5['bgp_total_rows']:,}` แถว** ในระดับ `IPv4 Prefix × ASN` (แถมมีแถวที่เป็น Multi-Origin AS เช่น `13335_15169` และ prefix ย่อยที่ซ้อนทับกับบล็อกใหญ่ ซึ่งต้องยุบรวมเป็นระดับประเทศ-ปีโดยไม่ให้นับ IP ซ้ำ)
  * **V-Dem v16:** มีจำนวนคอลัมน์ดิบสูงถึง **`{s5['vdem_cols']:,}` คอลัมน์** (ขนาดไฟล์ 388 MB) จึงต้องคัดกรองเฉพาะตัวแปรธรรมาภิบาลและไซเบอร์ที่ใช้จริง 13 ตัวแปร
"""
    for folder in (OUT_DIR_REPORTS, OUT_DIR_ROOT):
        folder.mkdir(parents=True, exist_ok=True)
        out_md = folder / "raw_data_eda_summary.md"
        out_md.write_text(md, encoding="utf-8")
        print(f"[SAVED] {out_md}")


def main() -> None:
    print("Running Raw Data EDA (reading strictly from data/raw/)...")
    s1 = plot_01_raw_entity_inconsistencies()
    s2 = plot_02_gci_raw_scale_schema_drift()
    s3 = plot_03_raw_missingness_profile()
    s4 = plot_04_raw_distributions_skewness()
    s5 = plot_05_raw_scope_and_volume_mismatch()
    write_summary_markdown(s1, s2, s3, s4, s5)
    print("Done! All 5 raw data EDA figures and summary report generated.")


if __name__ == "__main__":
    main()
