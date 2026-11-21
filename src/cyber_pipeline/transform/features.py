"""Feature engineering pipeline: data/integrated/country_year.csv -> data/analytical/features.csv & SQLite.

Implements the exact specification in docs/feature_engineering_plan.md:
1. Causal forward-fill (2018 -> 2024) per country from cleaned World Bank tables (wb_econ, wb_digital).
2. Core Analytical Cohort filtering: in_worldbank == True & traffic_above_0_01pct == True (144 countries x 3 years = 432 rows).
3. Target variables (Y) for H1/H2 (target DDoS intensity) and H3 (origin DDoS / L7 intensity), plus sensitivity target.
4. Log transforms for skewed positive predictors and outlier treatment (Winsorization & arcsinh) for FDI.
5. Within-edition standardization for GCI (solving the 2020 -> 2024 edition methodology shift).
6. Temporal train/test split (Train: 2022-2023 = 288 rows; Test: 2024 = 144 rows).
7. Train-only median imputation and StandardScaler (Z-score) fitting to guarantee zero future data leakage.

Run:
    PYTHONPATH=src python -m cyber_pipeline.transform.features
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from cyber_pipeline.utils.logging_utils import get_logger
from cyber_pipeline.utils.paths import ANALYTICAL, CLEANED, DATA, INTEGRATED

log = get_logger("features")
DB_PATH = Path(os.environ.get("SQLITE_PATH", DATA / "warehouse" / "cyberattacks.db"))

EPS = 1e-4
TRAIN_YEARS = (2022, 2023)
TEST_YEARS = (2024,)

WB_FFILL_COLS = [
    "gdp_per_capita",
    "fdi_net_inflows",
    "internet_users_pct",
    "broadband_subs_per_100",
]

# Columns strictly excluded from predictor matrices X to prevent Target Leakage
TARGET_LEAKAGE_EXCLUSION_LIST = [
    "target_ddos_percent",
    "origin_ddos_percent",
    "target_l7_mitigated_percent",
    "origin_l7_mitigated_percent",
    "http_traffic_percent",
    "http_traffic_mean",
    "origin_mitig_waf_percent",
    "origin_mitig_ddos_percent",
    "origin_mitig_bot_percent",
    "l3_top_vector",
    "l3_syn_percent",
    "l3_udp_percent",
    "is_target_ddos_censored",
    "attack_intensity_log",
    "attack_intensity_causal_log",
    "origin_ddos_intensity_log",
    "origin_l7_intensity_log",
]


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


def apply_causal_wb_ffill(cy: pd.DataFrame) -> pd.DataFrame:
    """Step 1: Causal forward-fill (2018 -> 2024) within each country from cleaned WB tables."""
    wb_econ = _read_csv(CLEANED / "wb_econ.csv")
    wb_digi = _read_csv(CLEANED / "wb_digital.csv").drop(columns=["country_name"])
    wb_full = (
        wb_econ.merge(wb_digi, on=["iso3", "year"], how="outer")
        .sort_values(["iso3", "year"])
        .reset_index(drop=True)
    )
    wb_full[WB_FFILL_COLS] = wb_full.groupby("iso3")[WB_FFILL_COLS].ffill()

    out = cy.drop(columns=WB_FFILL_COLS).merge(
        wb_full[["iso3", "year"] + WB_FFILL_COLS],
        on=["iso3", "year"],
        how="left",
        validate="one_to_one",
    )
    return out


def build_features() -> pd.DataFrame:
    """Execute the full feature engineering pipeline and return the 432-row analytical DataFrame."""
    cy_raw = _read_csv(INTEGRATED / "country_year.csv")
    cy = apply_causal_wb_ffill(cy_raw)

    # Step 2: Filter to Core Analytical Cohort (144 countries x 3 years = 432 rows)
    core_mask = (cy["in_worldbank"].astype(bool)) & (cy["traffic_above_0_01pct"].astype(bool))
    df = cy.loc[core_mask].sort_values(["iso3", "year"]).reset_index(drop=True).copy()
    log.info("Core cohort filtered: %d rows (%d countries x %d years)", len(df), df["iso3"].nunique(), df["year"].nunique())

    # Step 3: Keys, Temporal Split & Missingness / Censor Flags
    df["year_idx"] = df["year"] - 2022
    df["split"] = np.where(df["year"].isin(TRAIN_YEARS), "train", "test")
    train_mask = df["split"] == "train"

    df["is_target_ddos_censored"] = (df["target_ddos_percent"].isna() | (df["target_ddos_percent"] == 0)).astype(int)
    df["has_gci"] = df["gci_score_100"].notna().astype(int)
    df["has_vdem"] = df["v2smgovcapsec"].notna().astype(int)

    # Causal traffic denominator for Sensitivity Check (2023 traffic for 2022-2023, 2024 traffic for 2024)
    traffic_pivot = df.set_index(["iso3", "year"])["http_traffic_percent"].unstack()
    df["http_traffic_causal_pct"] = df.apply(
        lambda r: traffic_pivot.loc[r["iso3"], 2023] if r["year"] in (2022, 2023) else traffic_pivot.loc[r["iso3"], 2024],
        axis=1,
    )

    # Step 4: Target Variables (Y)
    df["attack_intensity_log"] = np.log((df["target_ddos_percent"].fillna(0.0) + EPS) / (df["http_traffic_mean"] + EPS))
    df["attack_intensity_causal_log"] = np.log(
        (df["target_ddos_percent"].fillna(0.0) + EPS) / (df["http_traffic_causal_pct"] + EPS)
    )
    df["origin_ddos_intensity_log"] = np.log((df["origin_ddos_percent"] + EPS) / (df["http_traffic_mean"] + EPS))
    df["origin_l7_intensity_log"] = np.log((df["origin_l7_mitigated_percent"] + EPS) / (df["http_traffic_mean"] + EPS))

    # Step 5: Train-only Median Imputation for residual missing values
    impute_cols = [
        "internet_users_pct",
        "broadband_subs_per_100",
        "routed_asn_count",
        "ipv4_slash24_count",
        "gdp_per_capita",
        "fdi_net_inflows",
        "gci_score_100",
        "v2smgovcapsec",
        "gov_effectiveness",
    ]

    # Compute within-edition GCI Z-score and percentile rank BEFORE cross-edition imputation
    df["gci_z_within_edition"] = df.groupby("gci_edition_used")["gci_score_100"].transform(
        lambda s: (s - s.mean()) / s.std()
    )
    df["gci_pct_rank_within_edition"] = (
        df.groupby("gci_edition_used")["gci_score_100"].rank(pct=True) * 100.0
    )

    train_medians: dict[str, float] = {}
    for col in impute_cols:
        med = float(df.loc[train_mask, col].median())
        train_medians[col] = med
        n_miss = int(df[col].isna().sum())
        if n_miss > 0:
            miss_iso = sorted(df.loc[df[col].isna(), "iso3"].unique().tolist())
            df[col] = df[col].fillna(med)
            log.info("Imputed %-24s (%2d rows, %s) with train median = %.4f", col, n_miss, miss_iso, med)

    # For the 12 rows missing GCI, fill within-edition Z-score with train median of gci_z_within_edition
    gci_z_med = float(df.loc[train_mask, "gci_z_within_edition"].median())
    gci_pct_med = float(df.loc[train_mask, "gci_pct_rank_within_edition"].median())
    df["gci_z_within_edition"] = df["gci_z_within_edition"].fillna(gci_z_med)
    df["gci_pct_rank_within_edition"] = df["gci_pct_rank_within_edition"].fillna(gci_pct_med)

    # Step 6: Log Transforms & FDI Outlier Treatment (Bounds fit strictly on Train)
    df["http_traffic_mean_log"] = np.log(df["http_traffic_mean"])
    df["population_log"] = np.log(df["population"])
    df["routed_asn_count_log"] = np.log(df["routed_asn_count"])
    df["ipv4_slash24_count_log"] = np.log(df["ipv4_slash24_count"])
    df["gdp_per_capita_log"] = np.log(df["gdp_per_capita"])

    fdi_lo = float(df.loc[train_mask, "fdi_net_inflows"].quantile(0.025))
    fdi_hi = float(df.loc[train_mask, "fdi_net_inflows"].quantile(0.975))
    log.info("FDI train clipping bounds [p2.5, p97.5] = [%.4f, %.4f]", fdi_lo, fdi_hi)
    df["fdi_net_inflows_clipped"] = df["fdi_net_inflows"].clip(lower=fdi_lo, upper=fdi_hi)
    df["fdi_net_inflows_asinh"] = np.arcsinh(df["fdi_net_inflows"])

    # Step 7: StandardScaler (Z-score) fitted strictly on Train (2022-2023)
    scale_features = [
        "http_traffic_mean_log",
        "population_log",
        "internet_users_pct",
        "broadband_subs_per_100",
        "routed_asn_count_log",
        "ipv4_slash24_count_log",
        "gdp_per_capita_log",
        "fdi_net_inflows_clipped",
        "fdi_net_inflows_asinh",
        "gci_score_100",
        "v2smgovcapsec",
        "gov_effectiveness",
    ]
    for col in scale_features:
        tr_mean = float(df.loc[train_mask, col].mean())
        tr_std = float(df.loc[train_mask, col].std())
        df[f"{col}_z"] = (df[col] - tr_mean) / tr_std

    # H3 Composite Index: average of within-edition GCI Z-score, V-Dem cyber capacity Z, and WGI gov effectiveness Z
    df["cyber_readiness_index_z"] = (
        df["gci_z_within_edition"] + df["v2smgovcapsec_z"] + df["gov_effectiveness_z"]
    ) / 3.0

    # Select and order final analytical columns cleanly (zero raw attack shares to prevent Target Leakage)
    ordered_cols = [
        # Keys & Split
        "iso3",
        "country_name",
        "year",
        "year_idx",
        "split",
        # Missingness / Censor Flags
        "is_target_ddos_censored",
        "has_gci",
        "has_vdem",
        # Targets (Y)
        "attack_intensity_log",
        "attack_intensity_causal_log",
        "origin_ddos_intensity_log",
        "origin_l7_intensity_log",
        # Baseline Controls (Unscaled Log)
        "http_traffic_mean_log",
        "population_log",
        # H1 Predictors (Unscaled Log / %)
        "internet_users_pct",
        "broadband_subs_per_100",
        "routed_asn_count_log",
        "ipv4_slash24_count_log",
        # H2 Predictors (Unscaled Log / Clipped / Asinh)
        "gdp_per_capita_log",
        "fdi_net_inflows_clipped",
        "fdi_net_inflows_asinh",
        # H3 Predictors (Unscaled & Within-Edition GCI)
        "gci_score_100",
        "gci_z_within_edition",
        "gci_pct_rank_within_edition",
        "v2smgovcapsec",
        "gov_effectiveness",
        # Standardized (Z-score fitted on Train 2022-2023) Predictors ready for Linear / Ridge / ML models
        "http_traffic_mean_log_z",
        "population_log_z",
        "internet_users_pct_z",
        "broadband_subs_per_100_z",
        "routed_asn_count_log_z",
        "ipv4_slash24_count_log_z",
        "gdp_per_capita_log_z",
        "fdi_net_inflows_clipped_z",
        "fdi_net_inflows_asinh_z",
        "gci_score_100_z",
        "v2smgovcapsec_z",
        "gov_effectiveness_z",
        "cyber_readiness_index_z",
    ]
    out = df[ordered_cols].copy()

    # Verify 0 NaNs and 0 infs across the entire engineered dataset
    n_na = int(out.isna().sum().sum())
    num_cols = out.select_dtypes(include=[np.number]).columns
    n_inf = int(np.isinf(out[num_cols].values).sum())
    if n_na > 0 or n_inf > 0:
        raise ValueError(f"Engineered features contain invalid values: NaN={n_na}, Inf={n_inf}")

    return out


def save_outputs(df: pd.DataFrame) -> None:
    """Write features to data/analytical/*.csv and SQLite table `features`."""
    ANALYTICAL.mkdir(parents=True, exist_ok=True)

    full_path = ANALYTICAL / "features.csv"
    train_path = ANALYTICAL / "train_features.csv"
    test_path = ANALYTICAL / "test_features.csv"

    df.to_csv(full_path, index=False, encoding="utf-8")
    df[df["split"] == "train"].to_csv(train_path, index=False, encoding="utf-8")
    df[df["split"] == "test"].to_csv(test_path, index=False, encoding="utf-8")
    log.info("Wrote %s (%d rows x %d cols)", full_path, *df.shape)
    log.info("Wrote %s (%d rows) and %s (%d rows)", train_path.name, (df["split"] == "train").sum(), test_path.name, (df["split"] == "test").sum())

    if DB_PATH.parent.exists():
        con = sqlite3.connect(DB_PATH)
        try:
            with con:
                df.to_sql("features", con, if_exists="replace", index=False)
                con.execute('CREATE UNIQUE INDEX "ux_features" ON "features" (iso3, year)')
            log.info("Loaded table 'features' (%d rows x %d cols) into SQLite %s", *df.shape, DB_PATH)
        finally:
            con.close()


def main() -> pd.DataFrame:
    df = build_features()
    save_outputs(df)
    return df


if __name__ == "__main__":
    main()
