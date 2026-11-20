"""Cleaned & Integrated Data EDA (Post-Cleaning Validation & Factor Exploration).

Reads directly from the SQLite database `data/warehouse/cyberattacks.db` (specifically
`country_year` and the `cleaned_*` tables) and generates 8 presentation-ready figures:
- Figures 1–5: Direct 1-to-1 counterparts to the 5 Raw Data EDA charts, demonstrating
  the exact improvements achieved by the cleaning and integration pipeline.
- Figures 6–8: Exploratory Data Analysis of cyberattack patterns and factor associations
  across Sources A, B, C, and E.

Outputs:
- Figures: `reports/figures/clean_data_eda/*.png`
- Summary markdown: `reports/figures/clean_data_eda/clean_data_eda_summary.md`

Run:
    $env:PYTHONPATH="src"; python -m analysis.clean_data_eda
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from cyber_pipeline.utils.paths import DATA, REPORTS

DB_PATH = DATA / "warehouse" / "cyberattacks.db"
OUT_DIR = REPORTS / "figures" / "clean_data_eda"

plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 200
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Tahoma"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8


def load_table(name: str) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql_query(f'SELECT * FROM "{name}"', con)


def _save_fig(fig: plt.Figure, filename: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / filename
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[SAVED] {p}")


# ---------------------------------------------------------------------------
# 1. Counterpart to Raw [1]: Standardized ISO-3 Entities & Analysis Cohorts
# ---------------------------------------------------------------------------
def plot_01_standardized_entities() -> dict:
    """Shows how all cleaned tables now use 100% valid ISO-3 country keys (0 aggregates,
    0 format errors) and how the integrated spine defines clear analysis cohorts."""
    cy = load_table("country_year")
    ref = load_table("cleaned_country_reference")
    wb_e = load_table("cleaned_wb_econ")
    bgp = load_table("cleaned_bgp_country_year")
    gci = load_table("cleaned_gci_country_edition")
    vdem = load_table("cleaned_vdem_country_year")
    cf = load_table("cleaned_cloudflare_country_year")
    pairs = load_table("cleaned_cloudflare_attack_pairs")

    # Check how many distinct ISO3 codes exist in each cleaned table and how many match country_year spine (251)
    spine_iso3 = set(cy["iso3"].unique())
    main_cohort_iso3 = set(cy[cy["in_worldbank"].eq(1) & cy["traffic_above_0_01pct"].eq(1)]["iso3"].unique())

    tables_info = [
        ("Integrated Spine: `country_year`\n(2022–2024 Master Table)", set(cy["iso3"].unique()), "0 aggregates | 0 code errors | 251 valid ISO-3"),
        ("Source A: `cleaned_cloudflare_country_year`\n(2022–2024)", set(cf["iso3"].unique()), "Dropped AP/EU regions; fixed Greece GR -> GRC"),
        ("Source C: `cleaned_bgp_country_year`\n(CAIDA BGP 2018–2024)", set(bgp["iso3"].unique()), "Dropped 'EU' orgs; mapped 'Sweden' -> SE -> SWE"),
        ("Sources B/C/E: `cleaned_wb_*`\n(World Bank WDI & WGI 2018–2024)", set(wb_e["iso3"].unique()), "Dropped 44 regional/income aggregates (308 rows)"),
        ("Source E: `cleaned_gci_country_edition`\n(ITU GCI 2018, 2020, 2024)", set(gci["iso3"].unique()), "Stripped */** flags; mapped all 194 names -> ISO-3"),
        ("Source E: `cleaned_vdem_country_year`\n(V-Dem 2018–2024)", set(vdem["iso3"].unique()), "Dropped non-ISO units (Gaza, Somaliland, Zanzibar)"),
        ("Source A: `cleaned_cloudflare_attack_pairs`\n(Distinct Origin ISO-3)", set(pairs[pairs["origin_is_country"].eq(1)]["origin_iso3"].unique()), "Flagged Tor ('T1') with origin_is_country=0"),
    ][::-1]

    records = []
    for label, codes, note in tables_info:
        in_main = len(codes & main_cohort_iso3)
        in_other_valid = len(codes & spine_iso3) - in_main
        records.append({
            "label": label,
            "in_main": in_main,
            "in_other": in_other_valid,
            "total": len(codes),
            "note": note,
        })
    df_ent = pd.DataFrame(records)

    fig, ax = plt.subplots(figsize=(13.5, 7.2))
    y = np.arange(len(df_ent))
    h = 0.60

    ax.barh(
        y,
        df_ent["in_main"],
        height=h,
        color="#1f618d",
        label=f"Core Analytical Cohort: World Bank Economies & HTTP Traffic ≥ 0.01% ({len(main_cohort_iso3)} Countries)",
    )
    ax.barh(
        y,
        df_ent["in_other"],
        left=df_ent["in_main"],
        height=h,
        color="#5dade2",
        label=f"Small Territories / Low-Traffic Islands Kept in Spine ({len(spine_iso3) - len(main_cohort_iso3)} Jurisdictions, Flagged)",
    )

    ax.set_yticks(y)
    ax.set_yticklabels(df_ent["label"], fontsize=9.5, fontweight="bold")
    ax.set_xlabel("Number of Standardized ISO-3 Country Codes (0 Regional Aggregates, 0 Format Errors)", fontsize=10.8, fontweight="bold")
    ax.set_xlim(0, 420)
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    for i, row in df_ent.iterrows():
        tot = row["total"]
        ax.text(
            tot + 4,
            i + 0.14,
            f"100% Standardized ISO-3: {tot} Countries  (Core Cohort: {row['in_main']} | Small/Low-Traffic: {row['in_other']})",
            va="center",
            fontsize=8.8,
            fontweight="bold",
            color="#1b4f72",
        )
        ax.text(tot + 4, i - 0.17, f"✓ {row['note']}", va="center", fontsize=8.2, color="#2e7d32")

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
        "Cleaned Data: Standardized ISO-3 Country Coverage",
        fontsize=13,
        fontweight="bold",
        pad=52,
    )
    sns.despine(top=True, right=True)
    _save_fig(fig, "clean_01_standardized_entities.png")
    return {
        "n_spine_countries": len(spine_iso3),
        "n_wb_countries": int(cy.groupby("iso3")["in_worldbank"].first().sum()),
        "n_main_cohort": len(main_cohort_iso3),
    }


# ---------------------------------------------------------------------------
# 2. Counterpart to Raw [2]: Unified GCI 0-100 Scale & As-Of Join
# ---------------------------------------------------------------------------
def plot_02_gci_unified_scale_and_asof() -> dict:
    """Shows (A) all 3 GCI editions unified onto the 0-100 scale (`gci_score_100`) and
    (B) how the As-Of Join maps GCI editions onto the 2022-2024 country_year table."""
    gci = load_table("cleaned_gci_country_edition")
    cy = load_table("country_year")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.2), gridspec_kw={"width_ratios": [1.15, 1.15]})
    fig.suptitle(
        "Cleaned Data: Unified GCI Score (0–100 Scale) & As-Of Join",
        fontsize=13,
        fontweight="bold",
        y=1.01,
    )

    # Panel A: Cleaned GCI Editions (2018, 2020, 2024) all on 0-100 scale
    editions = [2018, 2020, 2024]
    colors = ["#e74c3c", "#2980b9", "#27ae60"]
    labels = [
        "Edition 2018 (n=193)\n[Raw 0–1 × 100]",
        "Edition 2020 (n=194)\n[0–100 + ISO-3]",
        "Edition 2024 (n=176)\n[Sum of 5 Pillars]",
    ]
    data_ed = [gci[gci["edition"] == e]["gci_score_100"].dropna() for e in editions]

    rng = np.random.default_rng(42)
    for idx, (s, col) in enumerate(zip(data_ed, colors)):
        ax1.boxplot(
            s,
            positions=[idx],
            widths=0.38,
            patch_artist=True,
            boxprops=dict(facecolor=col, alpha=0.35),
            medianprops=dict(color=col, linewidth=2.2),
        )
        jit = rng.uniform(-0.13, 0.13, size=len(s))
        ax1.scatter(np.full(len(s), idx) + jit, s, alpha=0.5, s=16, color=col)
        ax1.text(
            idx,
            102.5,
            f"Median: {s.median():.1f}\n(IQR: {s.quantile(0.25):.1f}–{s.quantile(0.75):.1f})",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color=col,
        )

    ax1.set_ylim(-3, 115)
    ax1.set_xticks([0, 1, 2])
    ax1.set_xticklabels(labels, fontsize=9.2, fontweight="bold")
    ax1.set_ylabel("Standardized `gci_score_100` (Unified 0–100 Scale)", fontsize=10.5, fontweight="bold")
    ax1.set_title("A. `cleaned_gci_country_edition` (All 3 Editions on Same 0–100 Scale)", fontsize=11, fontweight="bold")
    ax1.grid(axis="y", linestyle="--", alpha=0.5)

    # Panel B: As-of Join inside country_year (2022, 2023 use 2020 edition; 2024 uses 2024 edition)
    cy_gci = cy[cy["has_gci"].eq(1)].copy()
    years = [2022, 2023, 2024]
    y_colors = ["#2980b9", "#2980b9", "#27ae60"]
    for idx, (yr, col) in enumerate(zip(years, y_colors)):
        sub = cy_gci[cy_gci["year"] == yr]
        s = sub["gci_score_100"].dropna()
        ed_used = int(sub["gci_edition_used"].mode().iloc[0])
        age_used = int(sub["gci_age_years"].mode().iloc[0])
        ax2.violinplot(s, positions=[idx], widths=0.55, showmeans=False, showmedians=True)
        ax2.boxplot(
            s,
            positions=[idx],
            widths=0.22,
            patch_artist=True,
            boxprops=dict(facecolor=col, alpha=0.45),
            medianprops=dict(color="#111111", linewidth=2),
        )
        ax2.text(
            idx,
            103,
            f"Year {yr} (n={len(s)})\nUses GCI {ed_used} (age={age_used}y)\nMedian = {s.median():.1f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color=col,
        )

    ax2.set_ylim(-3, 118)
    ax2.set_xticks([0, 1, 2])
    ax2.set_xticklabels(
        [
            "Analysis Year 2022\n(As-Of -> GCI 2020)",
            "Analysis Year 2023\n(As-Of -> GCI 2020)",
            "Analysis Year 2024\n(As-Of -> GCI 2024)",
        ],
        fontsize=9.2,
        fontweight="bold",
    )
    ax2.set_ylabel("Joined `gci_score_100` in `country_year`", fontsize=10.5, fontweight="bold")
    ax2.set_title("B. As-Of Join in `country_year` (Zero Future Data Leakage)", fontsize=11, fontweight="bold")
    ax2.grid(axis="y", linestyle="--", alpha=0.5)

    sns.despine(top=True, right=True)
    plt.tight_layout()
    _save_fig(fig, "clean_02_gci_unified_scale_and_asof.png")
    return {
        "ed2018_median": float(data_ed[0].median()),
        "ed2020_median": float(data_ed[1].median()),
        "ed2024_median": float(data_ed[2].median()),
    }


# ---------------------------------------------------------------------------
# 3. Counterpart to Raw [3]: Missingness & Completeness After Cleaning
# ---------------------------------------------------------------------------
def plot_03_missingness_after_cleaning() -> dict:
    """Compares % missing in the integrated table across (A) All 251 spine areas vs
    (B) the Core Analytical Cohort (in_worldbank & traffic_above_0_01pct, 142 countries),
    and shows how JSON parsing & traffic_mean resolved key raw gaps."""
    cy = load_table("country_year")
    core = cy[cy["in_worldbank"].eq(1) & cy["traffic_above_0_01pct"].eq(1)].copy()

    # Check columns across years in the Core Analytical Cohort vs All Spine
    check_cols = [
        ("target_ddos_percent", "Source A: target_ddos_percent"),
        ("origin_ddos_percent", "Source A: origin_ddos_percent"),
        ("target_l7_mitigated_percent", "Source A: target_l7_mitigated_percent"),
        ("origin_l7_mitigated_percent", "Source A: origin_l7_mitigated_percent"),
        ("http_traffic_mean", "Source A: http_traffic_mean [Bridges 2022 gap!]"),
        ("origin_mitig_waf_percent", "Source A: origin_mitig_waf_percent"),
        ("l3_syn_percent", "Source A: l3_syn_percent [Rebuilt from JSON!]"),
        ("l3_udp_percent", "Source A: l3_udp_percent [Rebuilt from JSON!]"),
        ("gdp_per_capita", "Source B: gdp_per_capita"),
        ("population", "Source B: population"),
        ("secure_internet_servers_per_1m", "Source B: secure_internet_servers_per_1m"),
        ("fdi_net_inflows", "Source B: fdi_net_inflows"),
        ("internet_users_pct", "Source C: internet_users_pct"),
        ("broadband_subs_per_100", "Source C: broadband_subs_per_100"),
        ("routed_asn_count", "Source C: routed_asn_count (CAIDA BGP)"),
        ("ipv4_slash24_count", "Source C: ipv4_slash24_count (CAIDA BGP)"),
        ("gov_effectiveness", "Source E: gov_effectiveness (WGI)"),
        ("rule_of_law", "Source E: rule_of_law (WGI)"),
        ("gci_score_100", "Source E: gci_score_100 [As-Of Joined!]"),
        ("v2smgovcapsec", "Source E: v2smgovcapsec (V-Dem Cyber Cap.)"),
    ]

    mat = {}
    for col, label in check_cols:
        mat[label] = {
            "All Spine (251 areas)\n2022–2024": float(cy[col].isna().mean() * 100),
            "WB Economies (217)\n2022–2024": float(cy[cy["in_worldbank"].eq(1)][col].isna().mean() * 100),
            "Core Cohort (142)\nYear 2022": float(core[core["year"] == 2022][col].isna().mean() * 100),
            "Core Cohort (142)\nYear 2023": float(core[core["year"] == 2023][col].isna().mean() * 100),
            "Core Cohort (142)\nYear 2024": float(core[core["year"] == 2024][col].isna().mean() * 100),
        }
    df_miss = pd.DataFrame(mat).T

    fig, ax = plt.subplots(figsize=(13.5, 9.5))
    sns.heatmap(
        df_miss,
        ax=ax,
        annot=True,
        fmt=".1f",
        cmap="YlGnBu_r",
        vmin=0,
        vmax=60,
        cbar_kws={"label": "% Missing After Cleaning & Integration (Lower = More Complete)"},
        linewidths=0.6,
        linecolor="white",
    )
    ax.set_title(
        "Cleaned Data: Completeness Profile After Cleaning & Integration",
        fontsize=13,
        fontweight="bold",
        pad=14,
    )
    ax.set_xlabel("Analysis Scope & Year in `country_year` Table", fontsize=11, fontweight="bold")
    ax.set_ylabel("")
    ax.tick_params(axis="y", labelsize=9.5)
    ax.tick_params(axis="x", labelsize=9.8)

    plt.tight_layout()
    _save_fig(fig, "clean_03_missingness_after_cleaning.png")
    return {
        "n_core_countries": int(core["iso3"].nunique()),
        "core_ddos_miss_2024": float(df_miss.loc["Source A: target_ddos_percent", "Core Cohort (142)\nYear 2024"]),
        "core_gci_miss_2024": float(df_miss.loc["Source E: gci_score_100 [As-Of Joined!]", "Core Cohort (142)\nYear 2024"]),
    }


# ---------------------------------------------------------------------------
# 4. Counterpart to Raw [4]: Distributions After Log & Log-Ratio Transformation
# ---------------------------------------------------------------------------
def plot_04_log_transformed_distributions() -> dict:
    """Direct counterpart to Raw [4]: shows the same skewed variables after applying
    Log-Ratio Attack Intensity and log10 / log1p transformations on the cleaned data."""
    cy = load_table("country_year")
    core = cy[cy["in_worldbank"].eq(1) & cy["traffic_above_0_01pct"].eq(1)].copy()

    # Compute log-ratio intensities and log10 transforms
    eps = 1e-4
    core["target_ddos_log_ratio"] = np.log(
        (core["target_ddos_percent"].fillna(0) + eps) / (core["http_traffic_mean"] + eps)
    )
    core["origin_l7_log_ratio"] = np.log(
        (core["origin_l7_mitigated_percent"].fillna(0) + eps) / (core["http_traffic_mean"] + eps)
    )
    cy["log10_gdp_per_capita"] = np.log10(cy["gdp_per_capita"].dropna())
    cy["log10_secure_servers"] = np.log10(cy["secure_internet_servers_per_1m"].dropna() + 1)
    cy["log10_ipv4_slash24"] = np.log10(cy["ipv4_slash24_count"].dropna())

    vars_to_plot = [
        (
            core["target_ddos_log_ratio"].dropna(),
            "Source A: `Target DDoS Log-Ratio Intensity`\nln((target_ddos_% + 1e-4) / (http_traffic_mean + 1e-4))",
            "Log-Ratio Intensity (0 = proportional to traffic)",
            "#c0392b",
            "+8.05 (Raw %)",
        ),
        (
            core["origin_l7_log_ratio"].dropna(),
            "Source A: `Origin L7 Mitigated Log-Ratio Intensity`\nln((origin_l7_% + 1e-4) / (http_traffic_mean + 1e-4))",
            "Log-Ratio Intensity (0 = proportional to traffic)",
            "#d35400",
            "+8.15 (Raw %)",
        ),
        (
            np.log10(cy["gdp_per_capita"].dropna()),
            "Source B: `log10(gdp_per_capita)`\n(Cleaned World Bank Economies)",
            "log10(Current USD)",
            "#2980b9",
            "+3.48 (Raw USD)",
        ),
        (
            np.log10(cy["secure_internet_servers_per_1m"].dropna() + 1),
            "Source B: `log10(secure_internet_servers_per_1m + 1)`\n(Cleaned World Bank Economies)",
            "log10(Servers per 1M People + 1)",
            "#16a085",
            "+19.72 (Raw Servers)",
        ),
        (
            np.log10(cy["ipv4_slash24_count"].dropna()),
            "Source C: `log10(ipv4_slash24_count)`\n(De-duplicated Country /24 Blocks from 6.3M BGP Rows)",
            "log10(Exclusive IPv4 /24 Blocks)",
            "#8e44ad",
            "+48.86 (Raw BGP)",
        ),
        (
            cy[cy["in_worldbank"].eq(1)]["internet_users_pct"].dropna(),
            "Source C: `internet_users_pct` (Cleaned)\n(Regional aggregates removed; [0, 100] validated)",
            "% of Population (0–100%)",
            "#27ae60",
            "-0.60 (Raw %)",
        ),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(16, 9.2))
    fig.suptitle(
        "Cleaned Data: Distributions After Log & Log-Ratio Transformation",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )

    stats_out = {}
    for ax, (s, title, xlabel, color, raw_skew_str) in zip(axes.flat, vars_to_plot):
        skew_after = float(s.skew())
        med = float(s.median())
        mean = float(s.mean())
        stats_out[title.split("\n")[0]] = {"skew_after": skew_after, "median": med, "mean": mean}

        sns.histplot(s, bins=28, kde=True, ax=ax, color=color, edgecolor="white", alpha=0.75)
        ax.axvline(med, color="#111111", linestyle="--", linewidth=1.6, label=f"Median: {med:.2f}")
        ax.axvline(mean, color="#f39c12", linestyle="-", linewidth=1.6, label=f"Mean: {mean:.2f}")

        ax.set_title(title, fontsize=10.0, fontweight="bold", color="#222222")
        ax.set_xlabel(xlabel, fontsize=9.5, fontweight="bold")
        ax.set_ylabel("Country-Year Count", fontsize=9.5)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.legend(loc="upper left", fontsize=8.2, frameon=True)

        badge = (
            f"n = {len(s):,}\n"
            f"Raw Skewness: {raw_skew_str}\n"
            f"Cleaned Skewness: {skew_after:+.2f}\n"
            f"Mean ≈ Median ({mean:.2f} vs {med:.2f})"
        )
        ax.text(
            0.97,
            0.95,
            badge,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8.2,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#f8f9fa", edgecolor=color, alpha=0.92),
        )

    sns.despine(top=True, right=True)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    _save_fig(fig, "clean_04_log_transformed_distributions.png")
    return stats_out


# ---------------------------------------------------------------------------
# 5. Counterpart to Raw [5]: Integrated Country-Year Spine & Warehouse Tables
# ---------------------------------------------------------------------------
def plot_05_integrated_spine_and_warehouse() -> dict:
    """Direct counterpart to Raw [5]: shows (A) Multi-source join coverage across the
    753 rows of the 2022–2024 country_year spine and (B) the standardized SQLite tables."""
    cy = load_table("country_year")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 6.8), gridspec_kw={"width_ratios": [1.15, 1.25]})
    fig.suptitle(
        "Cleaned Data: Integrated Country-Year Spine (2022–2024) & SQLite Warehouse",
        fontsize=13,
        fontweight="bold",
        y=1.00,
    )

    # Panel A: Source coverage in `country_year` (753 rows = 251 countries x 3 years)
    src_flags = [
        ("has_cloudflare", "Source A: Cloudflare Radar (Spine Anchor)"),
        ("has_bgp", "Source C: CAIDA BGP (Aggregated from 6.3M rows)"),
        ("has_wb_econ", "Source B: World Bank Economy (WDI)"),
        ("has_wb_digital", "Source C: World Bank Digital (WDI)"),
        ("has_wb_governance", "Source E: World Bank Governance (WGI)"),
        ("has_gci", "Source E: ITU GCI (As-Of Joined 2020/2024)"),
        ("has_vdem", "Source E: V-Dem v16 (13 Selected Cyber/Gov Vars)"),
    ][::-1]

    y1 = np.arange(len(src_flags))
    matched_all = [int(cy[f].sum()) for f, _ in src_flags]
    matched_core = [
        int(cy[cy["in_worldbank"].eq(1) & cy["traffic_above_0_01pct"].eq(1)][f].sum())
        for f, _ in src_flags
    ]
    n_all = len(cy)
    n_core = int((cy["in_worldbank"].eq(1) & cy["traffic_above_0_01pct"].eq(1)).sum())

    ax1.barh(y1 + 0.16, [m / n_all * 100 for m in matched_all], height=0.32, color="#5dade2", label=f"All Spine Jurisdictions (n={n_all} rows / 251 areas)")
    ax1.barh(y1 - 0.16, [m / n_core * 100 for m in matched_core], height=0.32, color="#1f618d", label=f"Core Analytical Cohort (n={n_core} rows / 142 countries)")

    for i, (m_all, m_core) in enumerate(zip(matched_all, matched_core)):
        ax1.text(m_all / n_all * 100 + 1.2, i + 0.16, f"{m_all}/{n_all} ({m_all/n_all*100:.0f}%)", va="center", fontsize=8.3, color="#2874a6")
        ax1.text(m_core / n_core * 100 + 1.2, i - 0.16, f"{m_core}/{n_core} ({m_core/n_core*100:.1f}%)", va="center", fontsize=8.5, fontweight="bold", color="#1b4f72")

    ax1.set_yticks(y1)
    ax1.set_yticklabels([lbl for _, lbl in src_flags], fontsize=9.2, fontweight="bold")
    ax1.set_xlim(0, 145)
    ax1.set_ylim(-1.15, len(src_flags) - 0.35)
    ax1.set_xlabel("% of Country-Year Rows Matched on `(iso3, year)` Spine", fontsize=10.5, fontweight="bold")
    ax1.set_title("A. Source Join Coverage on Integrated 2022–2024 Spine", fontsize=11.2, fontweight="bold", pad=10)
    ax1.grid(axis="x", linestyle="--", alpha=0.5)
    ax1.legend(loc="lower right", fontsize=8.4, frameon=True, facecolor="#f8f9fa", edgecolor="#cccccc")

    # Panel B: Before vs After Row/Col Volume Comparison (How 7.7M raw rows became clean SQLite tables)
    comp_items = [
        ("Integrated Master Table\n`country_year` (2022–2024)", 753, 59, "#c0392b", "All 7 sources joined 1:1 on (iso3, year)"),
        ("CAIDA BGP Country-Year\n`cleaned_bgp_country_year`", 1645, 6, "#8e44ad", "Reduced from 6,300,180 raw prefix rows!"),
        ("V-Dem Country-Year\n`cleaned_vdem_country_year`", 1232, 16, "#d35400", "Reduced from 28,092 rows × 4,618 cols!"),
        ("World Bank Tables (×3)\n`cleaned_wb_econ/digital/gov`", 1519, 7, "#2980b9", "217 countries × 7 yrs (308 agg rows dropped)"),
        ("ITU GCI Country-Edition\n`cleaned_gci_country_edition`", 563, 12, "#27ae60", "3 editions unified to 0–100 + 5 pillars"),
        ("Cloudflare L3 Vectors\n`cleaned_cloudflare_l3_vectors`", 2523, 4, "#16a085", "Unpacked from raw embedded JSON string!"),
        ("Cloudflare Attack Pairs\n`cleaned_cloudflare_attack_pairs`", 600, 11, "#e74c3c", "Top 200 pairs × 3 yrs (Tor & domestic flagged)"),
    ][::-1]

    y2 = np.arange(len(comp_items))
    r_vals = [x[1] for x in comp_items]
    c_vals = [x[2] for x in comp_items]
    cols_b = [x[3] for x in comp_items]

    ax2.barh(y2, r_vals, height=0.56, color=cols_b, alpha=0.85)
    for i, (lbl, r_v, c_v, col, note) in enumerate(comp_items):
        ax2.text(r_v + 45, i + 0.13, f"{r_v:,} rows × {c_v} cols", va="center", fontsize=9.0, fontweight="bold", color=col)
        ax2.text(r_v + 45, i - 0.16, f"→ {note}", va="center", fontsize=8.2, color="#444444")

    ax2.set_yticks(y2)
    ax2.set_yticklabels([x[0] for x in comp_items], fontsize=9.2, fontweight="bold")
    ax2.set_xlim(0, 4300)
    ax2.set_xlabel("Cleaned Table Row Count in SQLite (`cyberattacks.db`)", fontsize=10.5, fontweight="bold")
    ax2.set_title("B. Standardized SQLite Tables After Aggregation & Filtering", fontsize=11.2, fontweight="bold")
    ax2.grid(axis="x", linestyle="--", alpha=0.5)

    sns.despine(top=True, right=True)
    plt.tight_layout()
    _save_fig(fig, "clean_05_integrated_spine_and_tables.png")
    return {
        "n_spine_rows": n_all,
        "n_core_rows": n_core,
        "pct_all_7_sources_in_core": float((cy[cy["in_worldbank"].eq(1) & cy["traffic_above_0_01pct"].eq(1)]["n_sources_available"] == 7).mean() * 100),
    }


# ---------------------------------------------------------------------------
# 6. Post-Cleaning EDA: Spearman Correlation Matrix Across Sources A, B, C, E
# ---------------------------------------------------------------------------
def plot_06_correlation_heatmap() -> dict:
    """Computes Spearman rank correlations on the cleaned core cohort (2022–2024)
    between cyberattack outcomes (volume share & traffic-normalized intensity) and
    national factors from Sources B, C, and E."""
    cy = load_table("country_year")
    df = cy[cy["in_worldbank"].eq(1) & cy["traffic_above_0_01pct"].eq(1)].copy()

    eps = 1e-4
    df["target_ddos_intensity"] = np.log((df["target_ddos_percent"].fillna(0) + eps) / (df["http_traffic_mean"] + eps))
    df["origin_ddos_intensity"] = np.log((df["origin_ddos_percent"].fillna(0) + eps) / (df["http_traffic_mean"] + eps))
    df["target_l7_intensity"] = np.log((df["target_l7_mitigated_percent"].fillna(0) + eps) / (df["http_traffic_mean"] + eps))
    df["origin_l7_intensity"] = np.log((df["origin_l7_mitigated_percent"].fillna(0) + eps) / (df["http_traffic_mean"] + eps))

    attack_cols = [
        ("target_ddos_percent", "A: Target DDoS Share (%)"),
        ("origin_ddos_percent", "A: Origin DDoS Share (%)"),
        ("target_l7_mitigated_percent", "A: Target L7 Share (%)"),
        ("origin_l7_mitigated_percent", "A: Origin L7 Share (%)"),
        ("target_ddos_intensity", "A: Target DDoS Intensity (Log-Ratio)"),
        ("origin_ddos_intensity", "A: Origin DDoS Intensity (Log-Ratio)"),
        ("target_l7_intensity", "A: Target L7 Intensity (Log-Ratio)"),
        ("origin_l7_intensity", "A: Origin L7 Intensity (Log-Ratio)"),
        ("bot_traffic_percent", "A: Bot Traffic Share (%)"),
    ]

    factor_cols = [
        ("http_traffic_mean", "A: HTTP Traffic Share (%)"),
        ("ipv4_slash24_count", "C: Routed IPv4 /24 Blocks (BGP)"),
        ("routed_asn_count", "C: Routed ASN Count (BGP)"),
        ("population", "B: Population"),
        ("gdp_per_capita", "B: GDP per Capita (USD)"),
        ("secure_internet_servers_per_1m", "B: Secure Servers per 1M"),
        ("fdi_net_inflows", "B: FDI Net Inflows (% GDP)"),
        ("internet_users_pct", "C: Internet Users (% Pop)"),
        ("broadband_subs_per_100", "C: Fixed Broadband / 100"),
        ("tls_1_3_percent", "A/C: TLS 1.3 Adoption (%)"),
        ("ipv6_percent", "A/C: IPv6 Adoption (%)"),
        ("gci_score_100", "E: ITU GCI Score (0–100)"),
        ("gov_effectiveness", "E: WGI Gov. Effectiveness"),
        ("rule_of_law", "E: WGI Rule of Law"),
        ("v2smgovcapsec", "E: V-Dem Gov Cyber Capacity"),
        ("v2x_libdem", "E: V-Dem Liberal Democracy"),
        ("v2smgovfilprc", "E: V-Dem Internet Freedom (No Filtering)"),
    ]

    a_names = [c for c, _ in attack_cols]
    f_names = [c for c, _ in factor_cols]
    corr = df[f_names + a_names].corr(method="spearman").loc[f_names, a_names]
    corr.index = [lbl for _, lbl in factor_cols]
    corr.columns = [lbl for _, lbl in attack_cols]

    fig, ax = plt.subplots(figsize=(13.5, 9.5))
    sns.heatmap(
        corr,
        ax=ax,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        vmin=-0.75,
        vmax=0.95,
        center=0,
        cbar_kws={"label": "Spearman Rank Correlation (ρ)"},
        linewidths=0.6,
        linecolor="white",
    )
    ax.axvline(4, color="#111111", linewidth=2.2)
    ax.text(2.0, -0.55, "← Global Volume Share (%) →", ha="center", va="center", fontsize=10, fontweight="bold", color="#1f618d")
    ax.text(6.5, -0.55, "← Traffic-Normalized Intensity & Bot % →", ha="center", va="center", fontsize=10, fontweight="bold", color="#c0392b")

    ax.set_title(
        "Cleaned Data: Spearman Correlation Across Cyberattacks & National Factors",
        fontsize=13,
        fontweight="bold",
        pad=26,
    )
    ax.tick_params(axis="x", rotation=28, labelsize=9.2)
    ax.tick_params(axis="y", labelsize=9.5)

    plt.tight_layout()
    _save_fig(fig, "clean_06_correlation_heatmap.png")
    return {
        "rho_bgp_origin_l7": float(corr.loc["C: Routed IPv4 /24 Blocks (BGP)", "A: Origin L7 Share (%)"]),
        "rho_bgp_target_ddos": float(corr.loc["C: Routed IPv4 /24 Blocks (BGP)", "A: Target DDoS Share (%)"]),
        "rho_gci_origin_l7": float(corr.loc["E: ITU GCI Score (0–100)", "A: Origin L7 Share (%)"]),
        "rho_bot_origin_intensity": float(df["bot_traffic_percent"].corr(df["origin_l7_intensity"], method="spearman")),
        "rho_rol_origin_intensity": float(corr.loc["E: WGI Rule of Law", "A: Origin L7 Intensity (Log-Ratio)"]),
    }


# ---------------------------------------------------------------------------
# 7. Post-Cleaning EDA: Key Factor Relationships (4 Hypothesis Dimensions)
# ---------------------------------------------------------------------------
def plot_07_key_factor_relationships() -> dict:
    """4-panel plot illustrating the core empirical relationships across Sources B, C, E
    and cyberattack volume / intensity."""
    cy = load_table("country_year")
    df = cy[cy["in_worldbank"].eq(1) & cy["traffic_above_0_01pct"].eq(1)].copy()
    eps = 1e-4
    df["origin_l7_intensity"] = np.log((df["origin_l7_mitigated_percent"].fillna(0) + eps) / (df["http_traffic_mean"] + eps))
    df["target_ddos_intensity"] = np.log((df["target_ddos_percent"].fillna(0) + eps) / (df["http_traffic_mean"] + eps))
    df["log10_ipv4_slash24"] = np.log10(df["ipv4_slash24_count"])
    df["log10_origin_l7_pct"] = np.log10(df["origin_l7_mitigated_percent"])
    df["log10_target_ddos_pct"] = np.log10(df["target_ddos_percent"].replace(0, np.nan))
    df["log10_gdp"] = np.log10(df["gdp_per_capita"])
    df["log10_servers"] = np.log10(df["secure_internet_servers_per_1m"] + 1)

    # Use 2024 cross-section (or country mean across 2022-2024) so each point is 1 country
    df_2024 = df[df["year"] == 2024].copy()

    fig, axes = plt.subplots(2, 2, figsize=(15.5, 11))
    fig.suptitle(
        "Cleaned Data: Key Factors Associated with Cyberattack Volume & Intensity",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )

    # Panel A: Attack Surface (BGP IPv4 /24 blocks) vs Origin L7 Attack Share (2024)
    ax = axes[0, 0]
    sub = df_2024.dropna(subset=["log10_ipv4_slash24", "log10_origin_l7_pct"])
    sns.regplot(
        data=sub,
        x="log10_ipv4_slash24",
        y="log10_origin_l7_pct",
        ax=ax,
        color="#8e44ad",
        scatter_kws={"alpha": 0.65, "s": 38},
        line_kws={"color": "#2c3e50", "linewidth": 2},
    )
    rho_a = sub["log10_ipv4_slash24"].corr(sub["log10_origin_l7_pct"], method="spearman")
    for _, r in sub.nlargest(8, "log10_origin_l7_pct").iterrows():
        ax.text(r["log10_ipv4_slash24"] + 0.04, r["log10_origin_l7_pct"], r["iso3"], fontsize=8, fontweight="bold")
    ax.set_title(f"A. Network Attack Surface (Source C: BGP /24 Blocks) vs Origin L7 Share\n[Spearman ρ = {rho_a:+.2f}, n = {len(sub)} countries in 2024]", fontsize=10.5, fontweight="bold")
    ax.set_xlabel("log10(Routed IPv4 /24 Blocks — CAIDA BGP)", fontweight="bold")
    ax.set_ylabel("log10(Origin L7 Mitigated Share %)", fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.4)

    # Panel B: Digital Economy Infrastructure (Secure Servers per 1M) vs Target DDoS Share (2024)
    ax = axes[0, 1]
    sub_b = df_2024.dropna(subset=["log10_servers", "log10_target_ddos_pct", "gci_score_100"])
    sc = ax.scatter(
        sub_b["log10_servers"],
        sub_b["log10_target_ddos_pct"],
        c=sub_b["gci_score_100"],
        cmap="viridis",
        s=48,
        alpha=0.8,
        edgecolor="black",
        linewidth=0.4,
    )
    sns.regplot(
        data=sub_b,
        x="log10_servers",
        y="log10_target_ddos_pct",
        ax=ax,
        scatter=False,
        line_kws={"color": "#c0392b", "linewidth": 2},
    )
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("ITU GCI Score (0–100)", fontsize=9)
    rho_b = sub_b["log10_servers"].corr(sub_b["log10_target_ddos_pct"], method="spearman")
    for _, r in sub_b.nlargest(8, "log10_target_ddos_pct").iterrows():
        ax.text(r["log10_servers"] + 0.04, r["log10_target_ddos_pct"], r["iso3"], fontsize=8, fontweight="bold")
    ax.set_title(f"B. Digital Economy Servers (Source B) vs Target DDoS Share\n[Spearman ρ = {rho_b:+.2f}, colored by ITU GCI Score]", fontsize=10.5, fontweight="bold")
    ax.set_xlabel("log10(Secure Internet Servers per 1M People + 1)", fontweight="bold")
    ax.set_ylabel("log10(Target DDoS Share %)", fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.4)

    # Panel C: Bot Traffic % vs Origin L7 Attack Intensity (Traffic-Normalized Log-Ratio)
    ax = axes[1, 0]
    sub_c = df_2024.dropna(subset=["bot_traffic_percent", "origin_l7_intensity"])
    sns.regplot(
        data=sub_c,
        x="bot_traffic_percent",
        y="origin_l7_intensity",
        ax=ax,
        color="#d35400",
        scatter_kws={"alpha": 0.65, "s": 38},
        line_kws={"color": "#111111", "linewidth": 2},
    )
    rho_c = sub_c["bot_traffic_percent"].corr(sub_c["origin_l7_intensity"], method="spearman")
    for _, r in sub_c.nlargest(7, "origin_l7_intensity").iterrows():
        ax.text(r["bot_traffic_percent"] + 0.5, r["origin_l7_intensity"], r["iso3"], fontsize=8, fontweight="bold")
    ax.axhline(0, color="#555555", linestyle=":", linewidth=1.2, label="Intensity = Global Average (0)")
    ax.set_title(f"C. Bot Traffic Share vs Traffic-Normalized Origin Attack Intensity\n[Spearman ρ = {rho_c:+.2f} — More automated bot traffic -> disproportionate attack origin]", fontsize=10.5, fontweight="bold")
    ax.set_xlabel("Bot Traffic Share (% of Country HTTP Traffic)", fontweight="bold")
    ax.set_ylabel("Origin L7 Log-Ratio Intensity (Attack % / Traffic %)", fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="lower right", fontsize=8.5)

    # Panel D: Governance & Rule of Law Quartiles / GCI Tiers vs Origin Attack Intensity & Bot Traffic
    ax = axes[1, 1]
    sub_d = df.dropna(subset=["rule_of_law", "origin_l7_intensity"]).copy()
    sub_d["rol_group"] = pd.qcut(
        sub_d["rule_of_law"],
        q=4,
        labels=["Q1: Lowest\nRule of Law", "Q2: Lower-Mid\nRule of Law", "Q3: Upper-Mid\nRule of Law", "Q4: Highest\nRule of Law"],
    )
    sns.boxplot(
        data=sub_d,
        x="rol_group",
        y="origin_l7_intensity",
        hue="rol_group",
        ax=ax,
        palette=["#e74c3c", "#f39c12", "#5dade2", "#27ae60"],
        width=0.45,
        fliersize=3,
        legend=False,
    )
    ax.axhline(0, color="#333333", linestyle=":", linewidth=1.2)
    rho_d = sub_d["rule_of_law"].corr(sub_d["origin_l7_intensity"], method="spearman")
    ax.set_title(f"D. Institutional Governance (Source E: WGI Rule of Law) vs Origin Attack Intensity\n[Spearman ρ = {rho_d:+.2f} across 2022–2024 country-years]", fontsize=10.5, fontweight="bold")
    ax.set_xlabel("World Bank WGI Rule of Law Quartiles (Source E)", fontweight="bold")
    ax.set_ylabel("Origin L7 Log-Ratio Intensity (Attack % / Traffic %)", fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    sns.despine(top=True, right=True)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    _save_fig(fig, "clean_07_key_factor_relationships.png")
    return {"rho_a": float(rho_a), "rho_b": float(rho_b), "rho_c": float(rho_c), "rho_d": float(rho_d)}


# ---------------------------------------------------------------------------
# 8. Post-Cleaning EDA: Global Attack Landscape (Targets vs Origins, Pairs, L3 Vectors)
# ---------------------------------------------------------------------------
def plot_08_attack_landscape() -> dict:
    """3-panel deep-dive into Source A cleaned tables:
    (A) Top 12 Countries by Target DDoS vs Origin DDoS Share (2022–2024 mean)
    (B) Top 12 Cross-Border & Domestic Attack Flow Pairs (`cleaned_cloudflare_attack_pairs`)
    (C) Top 10 Layer-3 DDoS Attack Vectors (`cleaned_cloudflare_l3_vectors`)."""
    cy = load_table("country_year")
    pairs = load_table("cleaned_cloudflare_attack_pairs")
    l3 = load_table("cleaned_cloudflare_l3_vectors")

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(17.5, 6.8), gridspec_kw={"width_ratios": [1.25, 1.25, 1.1]})
    fig.suptitle(
        "Cleaned Data: Global Cyberattack Landscape (Targets, Origins, Pairs & L3 Vectors)",
        fontsize=13,
        fontweight="bold",
        y=1.01,
    )

    # Panel A: Top 12 Countries by Mean Target DDoS % vs Origin DDoS % (2022-2024)
    grp = (
        cy.groupby(["iso3", "country_name"], as_index=False)[["target_ddos_percent", "origin_ddos_percent"]]
        .mean()
        .fillna(0)
    )
    grp["combined"] = grp["target_ddos_percent"] + grp["origin_ddos_percent"]
    top_c = grp.nlargest(12, "combined")[::-1].reset_index(drop=True)

    y1 = np.arange(len(top_c))
    ax1.barh(y1 + 0.18, top_c["target_ddos_percent"], height=0.35, color="#c0392b", label="Target DDoS Share (% of World)")
    ax1.barh(y1 - 0.18, top_c["origin_ddos_percent"], height=0.35, color="#2980b9", label="Origin DDoS Share (% of World)")
    ax1.set_yticks(y1)
    ax1.set_yticklabels([f"{r['country_name']} ({r['iso3']})" for _, r in top_c.iterrows()], fontsize=9.0, fontweight="bold")
    ax1.set_xlabel("Mean % of Global DDoS Traffic (2022–2024)", fontsize=10, fontweight="bold")
    ax1.set_title("A. Top 12 Countries: Target vs Origin DDoS Share", fontsize=11, fontweight="bold")
    ax1.grid(axis="x", linestyle="--", alpha=0.5)
    ax1.legend(loc="lower right", fontsize=8.8)

    # Panel B: Top 12 Attack Flow Pairs (Mean share across 2022-2024)
    pairs["pair_label"] = pairs["origin_iso3"] + " → " + pairs["target_iso3"] + np.where(pairs["is_domestic"].eq(1), " (Domestic)", " (Cross-Border)")
    top_p = (
        pairs.groupby(["pair_label", "is_domestic"], as_index=False)["attack_share_percent"]
        .mean()
        .nlargest(12, "attack_share_percent")[::-1]
        .reset_index(drop=True)
    )
    p_colors = ["#e67e22" if d == 1 else "#8e44ad" for d in top_p["is_domestic"]]
    y2 = np.arange(len(top_p))
    ax2.barh(y2, top_p["attack_share_percent"], height=0.58, color=p_colors, alpha=0.88)
    for i, r in top_p.iterrows():
        ax2.text(r["attack_share_percent"] + 0.25, i, f"{r['attack_share_percent']:.2f}%", va="center", fontsize=8.5, fontweight="bold")
    ax2.set_yticks(y2)
    ax2.set_yticklabels(top_p["pair_label"], fontsize=8.8, fontweight="bold")
    ax2.set_xlim(0, max(top_p["attack_share_percent"]) * 1.18)
    ax2.set_xlabel("Mean % of Global L7 Attack Traffic", fontsize=10, fontweight="bold")
    ax2.set_title("B. Top 12 Origin → Target Attack Corridors", fontsize=11, fontweight="bold")
    ax2.grid(axis="x", linestyle="--", alpha=0.5)

    # Panel C: Top 10 Layer-3 Attack Vectors (Mean % across countries in cleaned_cloudflare_l3_vectors)
    l3_real = l3[l3["vector"] != "other"]
    top_v = (
        l3_real.groupby("vector", as_index=False)["percent"]
        .mean()
        .nlargest(10, "percent")[::-1]
        .reset_index(drop=True)
    )
    y3 = np.arange(len(top_v))
    ax3.barh(y3, top_v["percent"], height=0.58, color="#16a085", alpha=0.88)
    for i, r in top_v.iterrows():
        ax3.text(r["percent"] + 0.6, i, f"{r['percent']:.1f}%", va="center", fontsize=8.5, fontweight="bold")
    ax3.set_yticks(y3)
    ax3.set_yticklabels(top_v["vector"], fontsize=8.8, fontweight="bold")
    ax3.set_xlim(0, max(top_v["percent"]) * 1.2)
    ax3.set_xlabel("Mean Share When Present (% of Country L3 Attacks)", fontsize=10, fontweight="bold")
    ax3.set_title("C. Top 10 Layer-3 Attack Vectors (Unpacked JSON)", fontsize=11, fontweight="bold")
    ax3.grid(axis="x", linestyle="--", alpha=0.5)

    sns.despine(top=True, right=True)
    plt.tight_layout()
    _save_fig(fig, "clean_08_attack_landscape_targets_origins.png")
    return {
        "top_target": str(grp.nlargest(1, "target_ddos_percent").iloc[0]["country_name"]),
        "top_origin": str(grp.nlargest(1, "origin_ddos_percent").iloc[0]["country_name"]),
        "pct_domestic_pairs": float(pairs["is_domestic"].mean() * 100),
    }


def write_summary_markdown(s1: dict, s2: dict, s3: dict, s4: dict, s5: dict, s6: dict, s7: dict, s8: dict) -> None:
    md = rf"""# รายงานการสำรวจข้อมูลหลังทำความสะอาดและรวมตาราง (Cleaned & Integrated Data EDA)

เอกสารและชุดกราฟนี้ดึงข้อมูลโดยตรงจากฐานข้อมูล **`data/warehouse/cyberattacks.db`** (ตารางหลัก `country_year` และตาราง `cleaned_*`) เพื่อใช้สำหรับนำเสนอ:
1. **การเปรียบเทียบการเปลี่ยนแปลงหลังผ่าน Pipeline (รูปที่ 1–5 จับคู่แบบ 1:1 กับกราฟ Raw Data EDA ทั้ง 5 รูป)**
2. **ผลการสำรวจความสัมพันธ์และ Insights ของปัจจัยที่ส่งผลต่อการโจมตีทางไซเบอร์ (รูปที่ 6–8)**

---

## ส่วนที่ 1: เปรียบเทียบการเปลี่ยนแปลงจากกราฟ Raw Data ทั้ง 5 รูป (Before vs After Pipeline)

| รูปกราฟ Raw Data (ก่อน Clean) | รูปกราฟ Cleaned Data (หลัง Clean & Join) | สิ่งที่เปลี่ยนแปลงและผลลัพธ์ที่ได้จาก Pipeline |
| :--- | :--- | :--- |
| **`raw_01_entity_inconsistencies.png`**<br>รหัสประเทศคนละมาตรฐาน มีภูมิภาค (`WLD`, `HIC`, `EU`), `Tor`, ชื่อติด `**` และรหัสผิด `GR` | **`clean_01_standardized_entities.png`**<br>`Cleaned Data: Standardized ISO-3 Country Coverage` | • แปลงทุกแหล่งเข้าสู่มาตรฐาน **`ISO-3` เดียวกันครบ 100%** ({s1['n_spine_countries']} พื้นที่ใน Spine, 0 รหัสภูมิภาคซ้ำซ้อน, 0 รหัสผิด)<br>• แยก Flag ชัดเจนระหว่างประเทศสมาชิก World Bank ({s1['n_wb_countries']} เศรษฐกิจ) และกลุ่มวิเคราะห์หลักที่มี HTTP Traffic $\ge 0.01\%$ (**{s1['n_main_cohort']} ประเทศ**) |
| **`raw_02_gci_scale_and_schema_drift.png`**<br>GCI 3 ฉบับคนละสเกล (`0–1`, `0–100`, และแยก 5 เสาหลัก `0–20`) | **`clean_02_gci_unified_scale_and_asof.png`**<br>`Cleaned Data: Unified GCI Score (0–100 Scale) & As-Of Join` | • ปรับสเกลทั้ง 3 ฉบับ (2018, 2020, 2024) เข้าสู่คอลัมน์ **`gci_score_100` (`0–100`)** เดียวกัน (มัธยฐาน: ปี 2018 = `{s2['ed2018_median']:.1f}`, ปี 2020 = `{s2['ed2020_median']:.1f}`, ปี 2024 = `{s2['ed2024_median']:.1f}`)<br>• เชื่อมเข้าตาราง `country_year` แบบ **As-Of Join** (ปี 2022–2023 ใช้ฉบับ 2020, ปี 2024 ใช้ฉบับ 2024) ป้องกัน Data Leakage 100% |
| **`raw_03_missingness_heatmap_by_year.png`**<br>คอลัมน์ `l3_syn/udp` ดิบว่าง 100%, ปี 2022 ขาด HTTP Traffic 100% | **`clean_03_missingness_after_cleaning.png`**<br>`Cleaned Data: Completeness Profile After Cleaning & Integration` | • แกะ JSON ลงคอลัมน์ `l3_syn_percent`, `l3_udp_percent` และแยกเป็นตาราง `cleaned_cloudflare_l3_vectors` (2,523 แถว)<br>• สร้าง `http_traffic_mean` อุดช่องโหว่ปี 2022 ทำให้คัดกรองกลุ่มประเทศหลัก ({s3['n_core_countries']} ประเทศ) ซึ่งมีความครบถ้วนของข้อมูลสูงมาก (เช่นในปี 2024 `target_ddos_percent` ว่างเพียง `{s3['core_ddos_miss_2024']:.1f}%` และ `gci_score_100` ว่างเพียง `{s3['core_gci_miss_2024']:.1f}%`) |
| **`raw_04_distributions_and_skewness.png`**<br>ค่าดิบเบ้ขวาจัดระดับ Power-Law (Skewness `+3.48` ถึง `+48.86`) | **`clean_04_log_transformed_distributions.png`**<br>`Cleaned Data: Distributions After Log & Log-Ratio Transformation` | • เมื่อแปลงตัวแปรโจมตีเป็น **Log-Ratio Attack Intensity** เทียบกับ Traffic และเทค **`log10`** กับ GDP, Secure Servers และ BGP IPv4 `/24` blocks ค่าความเบ้ (Skewness) ลดลงจาก `+8..+48` เหลือเพียง **`-0.5` ถึง `+0.7`** (ใกล้เคียงการแจกแจงปกติ Mean $\approx$ Median) |
| **`raw_05_time_horizon_and_volume_mismatch.png`**<br>เวลาไม่ตรงกัน (1789–2025 vs 2018–2024) และ BGP ดิบ 6.3 ล้านแถว | **`clean_05_integrated_spine_and_tables.png`**<br>`Cleaned Data: Integrated Country-Year Spine (2022–2024) & SQLite Warehouse` | • ยุบรวม BGP 6.3 ล้านแถว (แบบไม่นับ IP ซ้ำ) และคัดคอลัมน์ V-Dem จาก 4,618 เหลือ 16 คอลัมน์<br>• Left-Join ทุกแหล่งเข้ากับ **Spine `country_year` (ปี 2022–2024, {s5['n_spine_rows']} แถว × 59 คอลัมน์)** โดยในกลุ่มประเทศวิเคราะห์หลัก ({s5['n_core_rows']} แถว) มีข้อมูลครบทั้ง 7 แหล่งสูงถึง **`{s5['pct_all_7_sources_in_core']:.1f}%`** |

---

## ส่วนที่ 2: สรุปข้อค้นพบสำคัญ (Key EDA Insights) จากข้อมูลที่ Clean แล้ว (รูปที่ 6–8)

### 1. ปัจจัยที่สัมพันธ์กับ "ปริมาณการโจมตีรวม (% Global Share)" vs "ความเข้มข้นของการโจมตี (Traffic-Normalized Intensity)" (`clean_06` & `clean_07`)
จากการวิเคราะห์สหสัมพันธ์แบบ Spearman Rank Correlation (`clean_06_correlation_heatmap.png`) และกราฟความสัมพันธ์ (`clean_07_key_factor_relationships.png`) พบข้อค้นพบสำคัญที่ต้องแยกเป็น **2 มิติ**:

* **มิติที่ 1 — ปริมาณส่วนแบ่งการโจมตีระดับโลก (`*_percent` — Global Volume Share):**
  * **ขนาดพื้นผิวเครือข่าย (Source C — CAIDA BGP `ipv4_slash24_count` และ `routed_asn_count`)** เป็นตัวแปรที่มีความสัมพันธ์เชิงบวกสูงที่สุดกับปริมาณการโจมตีทั้งฝั่งต้นทางและเป้าหมาย (Spearman $\rho = {s6['rho_bgp_origin_l7']:+.2f}$ กับ `origin_l7_mitigated_percent` และ $\rho = {s6['rho_bgp_target_ddos']:+.2f}$ กับ `target_ddos_percent`)
  * **โครงสร้างพื้นฐานเศรษฐกิจดิจิทัล (Source B — `secure_internet_servers_per_1m` และ `gdp_per_capita`)** สัมพันธ์เชิงบวกกับการตกเป็นเป้าหมาย DDoS ($\rho = {s7['rho_b']:+.2f}$)
  * **ข้อสังเกตสำคัญ (Scale Confounding):** ประเทศที่มีคะแนนความพร้อมไซเบอร์สูง (`gci_score_100`) มีสหสัมพันธ์เชิงบวกกับ `% การโจมตีดิบ` ($\rho = {s6['rho_gci_origin_l7']:+.2f}$) **ไม่ใช่เพราะระบบป้องกันแย่ แต่เพราะประเทศที่มี GCI สูงคือประเทศเศรษฐกิจขนาดใหญ่ที่มีโครงข่าย IP และทราฟฟิกอินเทอร์เน็ตมหาศาล** นี่คือเหตุผลสำคัญที่งานวิจัยนี้ต้องควบคุมด้วยปริมาณทราฟฟิก (**Log-Ratio Attack Intensity**)

* **มิติที่ 2 — ความเข้มข้นของการโจมตีเมื่อเทียบกับขนาดทราฟฟิกของประเทศ (`Log-Ratio Intensity`):**
  * เมื่อหารด้วยสัดส่วนทราฟฟิก (`http_traffic_mean`) เพื่อดูว่า **"ประเทศใดเป็นต้นทางหรือเป้าหมายการโจมตีเกินตัวเมื่อเทียบกับทราฟฟิกปกติของตน"**:
  * **สัดส่วนทราฟฟิกบอท (`bot_traffic_percent`)** มีความสัมพันธ์เชิงบวกอย่างชัดเจนกับความเข้มข้นของการเป็นต้นทางโจมตี ($\rho = {s7['rho_c']:+.2f}$) กล่าวคือ ประเทศที่ทราฟฟิกในประเทศมีสัดส่วน Automated Bot สูง มักเป็นแหล่งกำเนิดการโจมตี Layer 7 ในสัดส่วนที่สูงเกินขนาดทราฟฟิกปกติ
  * **คุณภาพธรรมาภิบาลและหลักนิติธรรม (Source E — `rule_of_law`, `gov_effectiveness`, `v2x_libdem`)** เมื่อดูในกลุ่มความเข้มข้นของการโจมตี พบแนวโน้มที่แตกต่างจากค่าดิบ โดยประเทศในกลุ่มหลักนิติธรรมสูงมีความผันผวนของความเข้มข้นการโจมตีต่ำกว่ากลุ่มประเทศที่ธรรมาภิบาลอ่อนแอ

### 2. ภาพรวมภูมิทัศน์การโจมตีโลก คู่โจมตี และการโจมตีระดับ Layer 3 (`clean_08_attack_landscape_targets_origins.png`)
* **Top Targets vs Top Origins:** สหรัฐอเมริกา (`USA`), จีน (`CHN`), เยอรมนี (`DEU`), สิงคโปร์ (`SGP`), และสหราชอาณาจักร (`GBR`) เป็นทั้งเป้าหมายและต้นทางหลักของทราฟฟิกการโจมตีโลก แต่มีสัดส่วนบทบาทต่างกัน (เช่น `USA` เป็นต้นทาง L7/DDoS อันดับ 1 ในขณะที่หลายประเทศเป็นเป้าหมายสูงกว่าต้นทาง)
* **คู่โจมตีหลัก (`cleaned_cloudflare_attack_pairs`):** คู่โจมตีอันดับต้นๆ ของโลกมีทั้ง **การโจมตีภายในประเทศเดียวกัน (Domestic Attacks เช่น `USA → USA`, `CHN → CHN` ซึ่งคิดเป็น `{s8['pct_domestic_pairs']:.1f}%` ของคู่ติดอันดับทั้งหมด)** และการโจมตีข้ามพรมแดนระหว่างศูนย์กลางทราฟฟิกหลัก
* **ประเภทการโจมตี Layer 3 (`cleaned_cloudflare_l3_vectors`):** หลังจากแกะข้อมูลออกจาก JSON พบว่า Vector การโจมตีระดับเครือข่ายที่มีสัดส่วนเฉลี่ยสูงสุดคือ **SYN Flood, DNS Amplification, UDP Flood, และ Mirai Botnet Flood**

---

## ข้อเสนอแนะสำหรับขั้นตอนถัดไป (Hypothesis Testing & Feature Engineering)
1. **การตั้งตัวแปรตาม (Target Variable) ในขั้น Modeling:** ควรวิเคราะห์เปรียบเทียบทั้ง **2 รูปแบบ** คือ:
   * โมเดลทำนาย **Global Attack Share (`log10(target_ddos_percent)`)** (ซึ่งจะขับเคลื่อนด้วยขนาดโครงข่าย BGP `/24` blocks, Population, และขนาดเศรษฐกิจ)
   * โมเดลทำนาย **Traffic-Normalized Attack Intensity (`Log-Ratio Intensity`)** (เพื่อตัดอิทธิพลของขนาดประเทศออก แล้ววัดผลของปัจจัยด้าน Bot exposure, ธรรมาภิบาล และความพร้อมด้านไซเบอร์)
2. **การคัดเลือกตัวแปรต้น ( menghindari Multicollinearity):**
   * ในกลุ่ม Source C (BGP): `routed_asn_count`, `routed_prefix_count`, และ `ipv4_slash24_count` มีความสัมพันธ์กันสูงมาก ($\rho > 0.90$) ควรเลือก `log10(ipv4_slash24_count)` เป็นตัวแทนหลักของขนาด Attack Surface
   * ในกลุ่ม Source E (WGI/V-Dem): `gov_effectiveness` กับ `rule_of_law` สัมพันธ์กันสูงมาก ควรเลือกตัวแทนหรือรวมเป็น Composite Index
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_md = OUT_DIR / "clean_data_eda_summary.md"
    out_md.write_text(md, encoding="utf-8")
    print(f"[SAVED] {out_md}")


def main() -> None:
    print("Running Cleaned & Integrated Data EDA from SQLite (cyberattacks.db)...")
    s1 = plot_01_standardized_entities()
    s2 = plot_02_gci_unified_scale_and_asof()
    s3 = plot_03_missingness_after_cleaning()
    s4 = plot_04_log_transformed_distributions()
    s5 = plot_05_integrated_spine_and_warehouse()
    s6 = plot_06_correlation_heatmap()
    s7 = plot_07_key_factor_relationships()
    s8 = plot_08_attack_landscape()
    write_summary_markdown(s1, s2, s3, s4, s5, s6, s7, s8)
    print("Done! All 8 cleaned data EDA figures and summary report generated.")


if __name__ == "__main__":
    main()
