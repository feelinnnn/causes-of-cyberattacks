"""V2 Feature Engineering & Model Training Pipeline (Implements all 4 improvements).

Improvements implemented:
  1. Ratio & Interaction Features:
     - `asn_per_capita_log_z` = log(routed_asn_count) - log(population)
     - `traffic_per_capita_log_z` = log(http_traffic_mean) - log(population)
     - `ipv4_per_asn_log_z` = log(ipv4_slash24_count) - log(routed_asn_count)
     - `unsecured_asn_z` = routed_asn_count_log_z * (-gov_effectiveness_z)
     - `unsecured_broadband_z` = broadband_subs_per_100_z * (-cyber_readiness_index_z)
  2. Censored Target Flooring & Outlier-Robust Models:
     - `attack_intensity_floored_log`: floors left-censored target rows (`is_target_ddos_censored == 1`)
       at the 2nd percentile of uncensored training rows (~ -4.85) instead of -9.99 (Iran outlier).
     - Adds Huber loss (`loss="huber"`) option to GradientBoostingRegressor and adds `Voting_Ensemble`.
  3. Additional Structural Features from `data/integrated/country_year.csv`:
     - H1 Digital/Network: `secure_servers_per_1m_log_z`, `routed_prefix_count_log_z`,
       `ipv4_slash24_count_log_z`, `ipv6_pct_log_z`, `tls_1_3_pct_z`, `bot_traffic_pct_z`
     - H3 Governance/Geopolitics: `rule_of_law_z`, `v2smfordom_z`, `v2x_polyarchy_z`, `cyber_readiness_index_z`
  4. Temporal Lag-1 Forecasting Models (`*_Forecast_Lag1`):
     - Evaluates 1-year-ahead forecasting (Train: 2022 -> 2023, n=144; Test: 2023 -> 2024, n=144)
       combining structural features with `lag1_target_z` (Y_{t-1}).

Outputs saved to `data/analytical/v2/`:
  - `data/analytical/v2/features.csv` (plus `train_features.csv`, `test_features.csv`)
  - `data/analytical/v2/model_metrics.csv`
  - `data/analytical/v2/feature_importance.csv`
  - `data/analytical/v2/model_predictions.csv`

Run:
    PYTHONPATH=src .venv/bin/python -m analysis.train_models_v2
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    RandomForestRegressor,
    VotingRegressor,
)
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import GridSearchCV, GroupKFold, cross_validate

from cyber_pipeline.transform.features import _read_csv
from cyber_pipeline.utils.logging_utils import get_logger
from cyber_pipeline.utils.paths import ANALYTICAL, CLEANED, DATA, INTEGRATED

log = get_logger("train_models_v2")
V2_DIR = ANALYTICAL / "v2"
DB_PATH = Path(os.environ.get("SQLITE_PATH", DATA / "warehouse" / "cyberattacks.db"))

EPS = 1e-4
TRAIN_YEARS = (2022, 2023)
TEST_YEARS = (2024,)

WB_FFILL_COLS_V2 = [
    "gdp_per_capita",
    "fdi_net_inflows",
    "secure_internet_servers_per_1m",
    "internet_users_pct",
    "broadband_subs_per_100",
]


def apply_causal_wb_ffill_v2(cy: pd.DataFrame) -> pd.DataFrame:
    """Causal forward-fill (2018 -> 2024) within each country including secure_internet_servers_per_1m."""
    wb_econ = _read_csv(CLEANED / "wb_econ.csv")
    wb_digi = _read_csv(CLEANED / "wb_digital.csv").drop(columns=["country_name"])
    wb_full = (
        wb_econ.merge(wb_digi, on=["iso3", "year"], how="outer")
        .sort_values(["iso3", "year"])
        .reset_index(drop=True)
    )
    wb_full[WB_FFILL_COLS_V2] = wb_full.groupby("iso3")[WB_FFILL_COLS_V2].ffill()

    out = cy.drop(columns=WB_FFILL_COLS_V2).merge(
        wb_full[["iso3", "year"] + WB_FFILL_COLS_V2],
        on=["iso3", "year"],
        how="left",
        validate="one_to_one",
    )
    return out


def build_features_v2() -> pd.DataFrame:
    """Build enhanced v2 feature table with Ratio/Interaction, Unused country_year cols, Floored Target, and Lag-1."""
    cy_raw = _read_csv(INTEGRATED / "country_year.csv")
    cy = apply_causal_wb_ffill_v2(cy_raw)

    core_mask = (cy["in_worldbank"].astype(bool)) & (cy["traffic_above_0_01pct"].astype(bool))
    df = cy.loc[core_mask].sort_values(["iso3", "year"]).reset_index(drop=True).copy()

    df["year_idx"] = df["year"] - 2022
    df["split"] = np.where(df["year"].isin(TRAIN_YEARS), "train", "test")
    train_mask = df["split"] == "train"

    df["is_target_ddos_censored"] = (df["target_ddos_percent"].isna() | (df["target_ddos_percent"] == 0)).astype(int)
    df["has_gci"] = df["gci_score_100"].notna().astype(int)
    df["has_vdem"] = df["v2smgovcapsec"].notna().astype(int)

    # Target Variables (Y)
    df["attack_intensity_log"] = np.log((df["target_ddos_percent"].fillna(0.0) + EPS) / (df["http_traffic_mean"] + EPS))
    df["origin_ddos_intensity_log"] = np.log((df["origin_ddos_percent"] + EPS) / (df["http_traffic_mean"] + EPS))
    df["origin_l7_intensity_log"] = np.log((df["origin_l7_mitigated_percent"] + EPS) / (df["http_traffic_mean"] + EPS))

    # Improvement 2: Floored target for left-censored rows (fit strictly on uncensored Train 2nd percentile)
    uncensored_train_y = df.loc[train_mask & (df["is_target_ddos_censored"] == 0), "attack_intensity_log"]
    censor_floor = float(uncensored_train_y.quantile(0.02))
    df["attack_intensity_floored_log"] = np.where(
        df["is_target_ddos_censored"] == 1,
        np.maximum(df["attack_intensity_log"], censor_floor),
        df["attack_intensity_log"],
    )
    log.info("Floored censored attack_intensity_log at 2nd percentile of uncensored train = %.4f", censor_floor)

    # Within-edition GCI Z-score
    df["gci_z_within_edition"] = df.groupby("gci_edition_used")["gci_score_100"].transform(
        lambda s: (s - s.mean()) / s.std()
    )

    # Train-only median imputation for base + v2 columns
    impute_cols = [
        "internet_users_pct",
        "broadband_subs_per_100",
        "routed_asn_count",
        "routed_prefix_count",
        "ipv4_slash24_count",
        "secure_internet_servers_per_1m",
        "ipv6_percent",
        "tls_1_3_percent",
        "bot_traffic_percent",
        "gdp_per_capita",
        "fdi_net_inflows",
        "gci_score_100",
        "v2smgovcapsec",
        "v2smfordom",
        "v2x_polyarchy",
        "gov_effectiveness",
        "rule_of_law",
    ]
    for col in impute_cols:
        med = float(df.loc[train_mask, col].median())
        df[col] = df[col].fillna(med)

    gci_z_med = float(df.loc[train_mask, "gci_z_within_edition"].median())
    df["gci_z_within_edition"] = df["gci_z_within_edition"].fillna(gci_z_med)

    # Log transforms & FDI Winsorization
    df["http_traffic_mean_log"] = np.log(df["http_traffic_mean"])
    df["population_log"] = np.log(df["population"])
    df["routed_asn_count_log"] = np.log(df["routed_asn_count"])
    df["routed_prefix_count_log"] = np.log1p(df["routed_prefix_count"])
    df["ipv4_slash24_count_log"] = np.log(df["ipv4_slash24_count"])
    df["secure_servers_per_1m_log"] = np.log1p(df["secure_internet_servers_per_1m"])
    df["ipv6_pct_log"] = np.log1p(np.maximum(df["ipv6_percent"], 0.0))
    df["gdp_per_capita_log"] = np.log(df["gdp_per_capita"])

    fdi_lo = float(df.loc[train_mask, "fdi_net_inflows"].quantile(0.025))
    fdi_hi = float(df.loc[train_mask, "fdi_net_inflows"].quantile(0.975))
    df["fdi_net_inflows_clipped"] = df["fdi_net_inflows"].clip(lower=fdi_lo, upper=fdi_hi)

    # Improvement 1: Ratio features (before standardization)
    df["asn_per_capita_log"] = df["routed_asn_count_log"] - df["population_log"]
    df["traffic_per_capita_log"] = df["http_traffic_mean_log"] - df["population_log"]
    df["ipv4_per_asn_log"] = df["ipv4_slash24_count_log"] - df["routed_asn_count_log"]

    # Standardize all continuous predictors strictly on Train (2022-2023)
    scale_features = [
        "http_traffic_mean_log",
        "population_log",
        "internet_users_pct",
        "broadband_subs_per_100",
        "routed_asn_count_log",
        "routed_prefix_count_log",
        "ipv4_slash24_count_log",
        "secure_servers_per_1m_log",
        "ipv6_pct_log",
        "tls_1_3_percent",
        "bot_traffic_percent",
        "gdp_per_capita_log",
        "fdi_net_inflows_clipped",
        "gci_score_100",
        "v2smgovcapsec",
        "v2smfordom",
        "v2x_polyarchy",
        "gov_effectiveness",
        "rule_of_law",
        "asn_per_capita_log",
        "traffic_per_capita_log",
        "ipv4_per_asn_log",
    ]
    for col in scale_features:
        tr_mean = float(df.loc[train_mask, col].mean())
        tr_std = float(df.loc[train_mask, col].std())
        df[f"{col}_z"] = (df[col] - tr_mean) / tr_std

    # H3 Composite Index & Improvement 1 Interaction Features (H1 x H3)
    df["cyber_readiness_index_z"] = (
        df["gci_z_within_edition"] + df["v2smgovcapsec_z"] + df["gov_effectiveness_z"]
    ) / 3.0

    df["unsecured_asn_raw"] = df["routed_asn_count_log_z"] * (-df["gov_effectiveness_z"])
    df["unsecured_broadband_raw"] = df["broadband_subs_per_100_z"] * (-df["cyber_readiness_index_z"])
    for raw_col, z_col in [
        ("unsecured_asn_raw", "unsecured_asn_z"),
        ("unsecured_broadband_raw", "unsecured_broadband_z"),
    ]:
        m_val = float(df.loc[train_mask, raw_col].mean())
        s_val = float(df.loc[train_mask, raw_col].std())
        df[z_col] = (df[raw_col] - m_val) / s_val
    df = df.drop(columns=["unsecured_asn_raw", "unsecured_broadband_raw"])

    # Improvement 4: Lag-1 Target features (Y_{t-1}) for 1-year-ahead Forecasting (2023 and 2024 rows)
    df = df.sort_values(["iso3", "year"]).reset_index(drop=True)
    for t_col, lag_col in [
        ("attack_intensity_log", "lag1_attack_intensity_log"),
        ("attack_intensity_floored_log", "lag1_attack_floored_log"),
        ("origin_ddos_intensity_log", "lag1_origin_ddos_log"),
        ("origin_l7_intensity_log", "lag1_origin_l7_log"),
    ]:
        df[lag_col] = df.groupby("iso3")[t_col].shift(1)
        # For 2022 rows (where lag1 is NaN), fill with train median so table has 0 NaNs;
        # note that Forecast_Lag1 tasks filter strictly to year >= 2023 (2023=train, 2024=test)
        tr_2023_mask = df["year"] == 2023
        m_lag = float(df.loc[tr_2023_mask, lag_col].mean())
        s_lag = float(df.loc[tr_2023_mask, lag_col].std())
        df[lag_col] = df[lag_col].fillna(m_lag)
        df[f"{lag_col}_z"] = (df[lag_col] - m_lag) / s_lag

    # Select strictly clean engineered columns (zero NaNs, zero Infs, zero raw target leakage columns)
    ordered_cols_v2 = [
        # Keys, Split & Flags
        "iso3",
        "country_name",
        "year",
        "year_idx",
        "split",
        "is_target_ddos_censored",
        "has_gci",
        "has_vdem",
        # Targets (Y)
        "attack_intensity_log",
        "attack_intensity_floored_log",
        "origin_ddos_intensity_log",
        "origin_l7_intensity_log",
        # Clean Unscaled Predictors (for interpretability & interactive dashboard sliders)
        "http_traffic_mean_log",
        "population_log",
        "internet_users_pct",
        "broadband_subs_per_100",
        "routed_asn_count_log",
        "routed_prefix_count_log",
        "ipv4_slash24_count_log",
        "secure_servers_per_1m_log",
        "ipv6_pct_log",
        "tls_1_3_percent",
        "bot_traffic_percent",
        "gdp_per_capita_log",
        "fdi_net_inflows_clipped",
        "gci_score_100",
        "v2smgovcapsec",
        "v2smfordom",
        "v2x_polyarchy",
        "gov_effectiveness",
        "rule_of_law",
        "asn_per_capita_log",
        "traffic_per_capita_log",
        "ipv4_per_asn_log",
        # Standardized Predictors (Z-score fitted strictly on Train 2022-2023)
        "http_traffic_mean_log_z",
        "population_log_z",
        "internet_users_pct_z",
        "broadband_subs_per_100_z",
        "routed_asn_count_log_z",
        "routed_prefix_count_log_z",
        "ipv4_slash24_count_log_z",
        "secure_servers_per_1m_log_z",
        "ipv6_pct_log_z",
        "tls_1_3_percent_z",
        "bot_traffic_percent_z",
        "gdp_per_capita_log_z",
        "fdi_net_inflows_clipped_z",
        "gci_score_100_z",
        "gci_z_within_edition",
        "v2smgovcapsec_z",
        "v2smfordom_z",
        "v2x_polyarchy_z",
        "gov_effectiveness_z",
        "rule_of_law_z",
        "cyber_readiness_index_z",
        "asn_per_capita_log_z",
        "traffic_per_capita_log_z",
        "ipv4_per_asn_log_z",
        "unsecured_asn_z",
        "unsecured_broadband_z",
        # Lag-1 Target Features for Temporal Forecasting
        "lag1_attack_intensity_log",
        "lag1_attack_intensity_log_z",
        "lag1_attack_floored_log",
        "lag1_attack_floored_log_z",
        "lag1_origin_ddos_log",
        "lag1_origin_ddos_log_z",
        "lag1_origin_l7_log",
        "lag1_origin_l7_log_z",
    ]
    out = df[ordered_cols_v2].copy()

    n_na = int(out.isna().sum().sum())
    num_cols = out.select_dtypes(include=[np.number]).columns
    n_inf = int(np.isinf(out[num_cols].values).sum())
    if n_na > 0 or n_inf > 0:
        raise ValueError(f"V2 engineered features contain invalid values: NaN={n_na}, Inf={n_inf}")

    return out


# ---------------------------------------------------------------------------
# Feature Sets V2 aligned with Hypotheses H1, H2, H3 + Ratios + Unused Cols + Lag-1
# ---------------------------------------------------------------------------
CONTROLS_Z = [
    "http_traffic_mean_log_z",
    "population_log_z",
]

H1_DIGITAL_V2_Z = CONTROLS_Z + [
    "internet_users_pct_z",
    "broadband_subs_per_100_z",
    "routed_asn_count_log_z",
    "routed_prefix_count_log_z",
    "ipv4_slash24_count_log_z",
    "secure_servers_per_1m_log_z",
    "ipv6_pct_log_z",
    "tls_1_3_percent_z",
    "bot_traffic_percent_z",
    "asn_per_capita_log_z",
    "traffic_per_capita_log_z",
    "ipv4_per_asn_log_z",
]

H2_ECONOMY_V2_Z = CONTROLS_Z + [
    "gdp_per_capita_log_z",
    "fdi_net_inflows_clipped_z",
    "asn_per_capita_log_z",
    "traffic_per_capita_log_z",
]

H3_READINESS_V2_Z = CONTROLS_Z + [
    "gci_z_within_edition",
    "v2smgovcapsec_z",
    "gov_effectiveness_z",
    "rule_of_law_z",
    "v2smfordom_z",
    "v2x_polyarchy_z",
    "cyber_readiness_index_z",
    "unsecured_asn_z",
    "unsecured_broadband_z",
]

ALL_FEATURES_V2_Z = [
    # Baseline Controls
    "http_traffic_mean_log_z",
    "population_log_z",
    # H1 Digital & Network Exposure + Unused country_year cols
    "internet_users_pct_z",
    "broadband_subs_per_100_z",
    "routed_asn_count_log_z",
    "routed_prefix_count_log_z",
    "ipv4_slash24_count_log_z",
    "secure_servers_per_1m_log_z",
    "ipv6_pct_log_z",
    "tls_1_3_percent_z",
    "bot_traffic_percent_z",
    # H2 Economy
    "gdp_per_capita_log_z",
    "fdi_net_inflows_clipped_z",
    # H3 Readiness, Governance & Geopolitical Interference
    "gci_z_within_edition",
    "v2smgovcapsec_z",
    "gov_effectiveness_z",
    "rule_of_law_z",
    "v2smfordom_z",
    "v2x_polyarchy_z",
    "cyber_readiness_index_z",
    # Improvement 1: Ratios & H1xH3 Interactions
    "asn_per_capita_log_z",
    "traffic_per_capita_log_z",
    "ipv4_per_asn_log_z",
    "unsecured_asn_z",
    "unsecured_broadband_z",
]

# Experiments: (task_name, target_col, feature_set_name, feature_cols, filter_mode)
# filter_mode: "all" (432 rows), "uncensored" (399 rows), "forecast_lag1" (288 rows: 2023 train, 2024 test)
EXPERIMENTS_V2: list[tuple[str, str, str, list[str], str]] = [
    # 1. Target DDoS Intensity (Original Target + V2 Features)
    ("Target_DDoS_Intensity", "attack_intensity_log", "All_Features_v2 (H1+H2+H3)", ALL_FEATURES_V2_Z, "all"),
    ("Target_DDoS_Intensity", "attack_intensity_log", "H1_Digital_Exposure_v2", H1_DIGITAL_V2_Z, "all"),
    ("Target_DDoS_Intensity", "attack_intensity_log", "H2_Economy_v2", H2_ECONOMY_V2_Z, "all"),
    # 2. Target DDoS Intensity with Censored Flooring (Improvement 2) & Uncensored 399
    ("Target_DDoS_Floored", "attack_intensity_floored_log", "All_Features_v2 (Floored Censored)", ALL_FEATURES_V2_Z, "all"),
    ("Target_DDoS_Uncensored_399", "attack_intensity_log", "All_Features_v2 (Uncensored 399)", ALL_FEATURES_V2_Z, "uncensored"),
    # 3. Origin DDoS Intensity (H3_v2 & All_Features_v2)
    ("Origin_DDoS_Intensity", "origin_ddos_intensity_log", "H3_Cyber_Readiness_v2", H3_READINESS_V2_Z, "all"),
    ("Origin_DDoS_Intensity", "origin_ddos_intensity_log", "All_Features_v2 (H1+H2+H3)", ALL_FEATURES_V2_Z, "all"),
    # 4. Origin L7 Intensity (H3_v2 & All_Features_v2)
    ("Origin_L7_Intensity", "origin_l7_intensity_log", "H3_Cyber_Readiness_v2", H3_READINESS_V2_Z, "all"),
    ("Origin_L7_Intensity", "origin_l7_intensity_log", "All_Features_v2 (H1+H2+H3)", ALL_FEATURES_V2_Z, "all"),
    # 5. Improvement 4: 1-Year-Ahead Forecasting Models with Lag-1 Target (Y_{t-1})
    (
        "Target_DDoS_Forecast_Lag1",
        "attack_intensity_floored_log",
        "All_Features_v2 + Lag1_Y",
        ALL_FEATURES_V2_Z + ["lag1_attack_floored_log_z"],
        "forecast_lag1",
    ),
    (
        "Origin_DDoS_Forecast_Lag1",
        "origin_ddos_intensity_log",
        "All_Features_v2 + Lag1_Y",
        ALL_FEATURES_V2_Z + ["lag1_origin_ddos_log_z"],
        "forecast_lag1",
    ),
    (
        "Origin_L7_Forecast_Lag1",
        "origin_l7_intensity_log",
        "All_Features_v2 + Lag1_Y",
        ALL_FEATURES_V2_Z + ["lag1_origin_l7_log_z"],
        "forecast_lag1",
    ),
]


def get_model_families_v2() -> list[tuple[str, str, object, dict]]:
    """Return the model families including Huber-loss Gradient Boosting and Voting Ensemble."""
    rf_base = RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=3, random_state=42, n_jobs=1)
    et_base = ExtraTreesRegressor(n_estimators=200, max_depth=5, min_samples_leaf=3, random_state=42, n_jobs=1)
    gb_base = GradientBoostingRegressor(
        loss="huber", n_estimators=80, learning_rate=0.03, max_depth=3, min_samples_leaf=5, random_state=42
    )
    ridge_base = Ridge(alpha=100.0, random_state=42)

    return [
        (
            "1_Baseline",
            "Dummy_Mean",
            DummyRegressor(strategy="mean"),
            {},
        ),
        (
            "1_Baseline",
            "Controls_Only_OLS",
            LinearRegression(),
            {},
        ),
        (
            "2_Regularized_Linear",
            "Ridge_Regression",
            Ridge(random_state=42),
            {"alpha": [1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 200.0]},
        ),
        (
            "3_Bagging_Tree",
            "Random_Forest",
            RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=1),
            {"max_depth": [2, 3, 4, 5], "min_samples_leaf": [3, 4, 6, 8]},
        ),
        (
            "3_Bagging_Tree",
            "Extra_Trees",
            ExtraTreesRegressor(n_estimators=200, random_state=42, n_jobs=1),
            {"max_depth": [2, 3, 4, 5, 6], "min_samples_leaf": [3, 4, 6, 8]},
        ),
        (
            "4_Boosting_Tree",
            "Gradient_Boosting",
            GradientBoostingRegressor(random_state=42),
            {
                "loss": ["squared_error", "huber"],
                "max_depth": [2, 3],
                "n_estimators": [50, 80, 100],
                "learning_rate": [0.03, 0.05],
                "min_samples_leaf": [4, 6, 8],
            },
        ),
        (
            "5_Ensemble",
            "Voting_Ensemble",
            VotingRegressor([("rf", rf_base), ("et", et_base), ("gb", gb_base), ("ridge", ridge_base)]),
            {},
        ),
    ]


def fit_and_evaluate_v2(
    df: pd.DataFrame,
    task_name: str,
    target_col: str,
    feature_set_name: str,
    feature_cols: list[str],
    filter_mode: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Train all v2 model families and compute validation, test 2024, importance, and predictions."""
    if filter_mode == "uncensored":
        sub = df[df["is_target_ddos_censored"] == 0].copy()
    elif filter_mode == "forecast_lag1":
        # In lag-1 forecasting, 2022 provides the lag for 2023 (train: year==2023, test: year==2024)
        sub = df[df["year"] >= 2023].copy()
    else:
        sub = df.copy()

    train_df = sub[sub["split"] == "train"].reset_index(drop=True)
    test_df = sub[sub["split"] == "test"].reset_index(drop=True)

    gkf = GroupKFold(n_splits=5)
    scoring = {
        "r2": "r2",
        "neg_rmse": "neg_root_mean_squared_error",
        "neg_mae": "neg_mean_absolute_error",
    }

    metrics_rows: list[dict] = []
    importance_rows: list[dict] = []
    pred_rows: list[dict] = []

    for model_group, model_name, estimator, param_grid in get_model_families_v2():
        cols_use = CONTROLS_Z if model_name == "Controls_Only_OLS" else feature_cols
        X_train = train_df[cols_use]
        y_train = train_df[target_col]
        groups_train = train_df["iso3"]

        X_test = test_df[cols_use]
        y_test = test_df[target_col]

        if param_grid:
            gs = GridSearchCV(
                estimator=clone(estimator),
                param_grid=param_grid,
                cv=gkf,
                scoring="r2",
                n_jobs=1,
                refit=True,
            )
            gs.fit(X_train, y_train, groups=groups_train)
            best_est = gs.best_estimator_
            best_params = gs.best_params_
        else:
            best_est = clone(estimator).fit(X_train, y_train)
            best_params = {}

        cv_res = cross_validate(
            clone(best_est),
            X_train,
            y_train,
            groups=groups_train,
            cv=gkf,
            scoring=scoring,
            n_jobs=1,
        )
        val_r2 = float(np.mean(cv_res["test_r2"]))
        val_rmse = float(-np.mean(cv_res["test_neg_rmse"]))
        val_mae = float(-np.mean(cv_res["test_neg_mae"]))

        pred_train = best_est.predict(X_train)
        pred_test = best_est.predict(X_test)

        train_r2 = float(r2_score(y_train, pred_train))
        train_rmse = float(root_mean_squared_error(y_train, pred_train))

        test_r2 = float(r2_score(y_test, pred_test))
        test_rmse = float(root_mean_squared_error(y_test, pred_test))
        test_mae = float(mean_absolute_error(y_test, pred_test))

        metrics_rows.append({
            "task_name": task_name,
            "target_col": target_col,
            "feature_set": feature_set_name,
            "model_group": model_group,
            "model_name": model_name,
            "n_train": len(train_df),
            "n_test": len(test_df),
            "val_gkf_r2": round(val_r2, 4),
            "val_gkf_rmse": round(val_rmse, 4),
            "val_gkf_mae": round(val_mae, 4),
            "test_2024_r2": round(test_r2, 4),
            "test_2024_rmse": round(test_rmse, 4),
            "test_2024_mae": round(test_mae, 4),
            "train_r2": round(train_r2, 4),
            "train_rmse": round(train_rmse, 4),
            "best_params": json.dumps(best_params),
        })

        # Extract Feature Importance for non-dummy models
        if model_name != "Dummy_Mean":
            if hasattr(best_est, "coef_"):
                native_vals = np.asarray(best_est.coef_, dtype=float)
                native_type = "standardized_coef_beta"
            elif hasattr(best_est, "feature_importances_"):
                native_vals = np.asarray(best_est.feature_importances_, dtype=float)
                native_type = "gini_impurity_importance"
            else:
                native_vals = np.zeros(len(cols_use))
                native_type = "ensemble_permutation"

            perm = permutation_importance(
                best_est,
                X_test,
                y_test,
                scoring="r2",
                n_repeats=20,
                random_state=42,
                n_jobs=1,
            )

            if native_type == "ensemble_permutation":
                native_vals = perm.importances_mean

            imp_df = pd.DataFrame({
                "feature": cols_use,
                "native_importance": native_vals,
                "abs_native_importance": np.abs(native_vals),
                "perm_r2_drop_mean": perm.importances_mean,
                "perm_r2_drop_std": perm.importances_std,
            }).sort_values("abs_native_importance", ascending=False).reset_index(drop=True)
            imp_df["rank_by_native"] = np.arange(1, len(imp_df) + 1)

            for _, r in imp_df.iterrows():
                importance_rows.append({
                    "task_name": task_name,
                    "target_col": target_col,
                    "feature_set": feature_set_name,
                    "model_name": model_name,
                    "feature": r["feature"],
                    "importance_type": native_type,
                    "native_importance": round(float(r["native_importance"]), 5),
                    "abs_native_importance": round(float(r["abs_native_importance"]), 5),
                    "perm_test_r2_drop_mean": round(float(r["perm_r2_drop_mean"]), 5),
                    "perm_test_r2_drop_std": round(float(r["perm_r2_drop_std"]), 5),
                    "rank_by_native": int(r["rank_by_native"]),
                })

        # Improvement 2 Fix: Save predictions for the BEST primary feature set (All_Features_v2 & Forecast_Lag1)
        is_primary_set = (
            (task_name in ("Target_DDoS_Intensity", "Origin_DDoS_Intensity", "Origin_L7_Intensity") and feature_set_name == "All_Features_v2 (H1+H2+H3)")
            or (task_name == "Target_DDoS_Floored" and feature_set_name == "All_Features_v2 (Floored Censored)")
            or (task_name in ("Target_DDoS_Forecast_Lag1", "Origin_DDoS_Forecast_Lag1", "Origin_L7_Forecast_Lag1"))
        )
        if is_primary_set and model_name in ("Ridge_Regression", "Random_Forest", "Extra_Trees", "Gradient_Boosting", "Voting_Ensemble"):
            for split_label, part_df, preds in [("train", train_df, pred_train), ("test", test_df, pred_test)]:
                for idx_row, r in part_df.iterrows():
                    y_t = float(r[target_col])
                    y_p = float(preds[idx_row])
                    pred_rows.append({
                        "task_name": task_name,
                        "target_col": target_col,
                        "model_name": model_name,
                        "iso3": r["iso3"],
                        "country_name": r["country_name"],
                        "year": int(r["year"]),
                        "split": split_label,
                        "y_true": round(y_t, 5),
                        "y_pred": round(y_p, 5),
                        "residual": round(y_t - y_p, 5),
                    })

    return metrics_rows, importance_rows, pred_rows


def save_v2_results(
    df_feat: pd.DataFrame,
    df_metrics: pd.DataFrame,
    df_imp: pd.DataFrame,
    df_preds: pd.DataFrame,
) -> None:
    """Save v2 features, metrics, feature importance, and predictions to `data/analytical/v2/` and SQLite."""
    V2_DIR.mkdir(parents=True, exist_ok=True)

    f_path = V2_DIR / "features.csv"
    tr_path = V2_DIR / "train_features.csv"
    te_path = V2_DIR / "test_features.csv"
    m_path = V2_DIR / "model_metrics.csv"
    i_path = V2_DIR / "feature_importance.csv"
    p_path = V2_DIR / "model_predictions.csv"

    df_feat.to_csv(f_path, index=False, encoding="utf-8")
    df_feat[df_feat["split"] == "train"].to_csv(tr_path, index=False, encoding="utf-8")
    df_feat[df_feat["split"] == "test"].to_csv(te_path, index=False, encoding="utf-8")
    df_metrics.to_csv(m_path, index=False, encoding="utf-8")
    df_imp.to_csv(i_path, index=False, encoding="utf-8")
    df_preds.to_csv(p_path, index=False, encoding="utf-8")

    log.info(
        "Saved to %s: features.csv (%d rows x %d cols), model_metrics.csv (%d rows), feature_importance.csv (%d rows), model_predictions.csv (%d rows)",
        V2_DIR,
        *df_feat.shape,
        len(df_metrics),
        len(df_imp),
        len(df_preds),
    )

    if DB_PATH.parent.exists():
        con = sqlite3.connect(DB_PATH)
        try:
            with con:
                df_feat.to_sql("features_v2", con, if_exists="replace", index=False)
                df_metrics.to_sql("model_metrics_v2", con, if_exists="replace", index=False)
                df_imp.to_sql("feature_importance_v2", con, if_exists="replace", index=False)
                df_preds.to_sql("model_predictions_v2", con, if_exists="replace", index=False)
            log.info("Saved v2 tables into SQLite %s", DB_PATH)
        finally:
            con.close()


def main() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df_feat = build_features_v2()
    all_metrics: list[dict] = []
    all_imp: list[dict] = []
    all_preds: list[dict] = []

    for task_name, target_col, feature_set_name, feature_cols, filter_mode in EXPERIMENTS_V2:
        log.info("Training V2 models for %-28s | Feature set: %s", task_name, feature_set_name)
        m_rows, i_rows, p_rows = fit_and_evaluate_v2(
            df=df_feat,
            task_name=task_name,
            target_col=target_col,
            feature_set_name=feature_set_name,
            feature_cols=feature_cols,
            filter_mode=filter_mode,
        )
        all_metrics.extend(m_rows)
        all_imp.extend(i_rows)
        all_preds.extend(p_rows)

    df_metrics = pd.DataFrame(all_metrics)
    df_imp = pd.DataFrame(all_imp)
    df_preds = pd.DataFrame(all_preds)
    save_v2_results(df_feat, df_metrics, df_imp, df_preds)
    return df_feat, df_metrics, df_imp, df_preds


if __name__ == "__main__":
    main()
