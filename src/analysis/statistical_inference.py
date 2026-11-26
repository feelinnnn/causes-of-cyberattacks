"""Rigorous Statistical Inference & Hypothesis Testing for Causes of Cyberattacks.

Complements the predictive ML pipelines (`train_models.py`, `train_models_v2.py`,
`online_ml.py`) by computing formal inferential statistics suitable for an academic
report:

  1. Bivariate Spearman rank correlations with Benjamini-Hochberg FDR q-values
     (`spearman_correlations.csv`).
  2. Country-Clustered OLS regressions (`cov_type="cluster"`, grouped by `iso3`)
     and Cluster-Robust Wald F-tests across nested hypothesis blocks H1, H2, H3,
     full V1/V2 specifications, and Year Fixed Effects robustness checks
     (`hypothesis_block_tests.csv`, `ols_clustered_coefficients.csv`).
  3. Multicollinearity diagnostics via Variance Inflation Factors for V1 (10 vars)
     and V2 linearly independent predictors (21 vars) (`vif_diagnostics.csv`),
     explicitly omitting the 4 exact algebraic linear combinations (`asn_per_capita_log_z`,
     `traffic_per_capita_log_z`, `ipv4_per_asn_log_z`, `cyber_readiness_index_z`)
     from OLS/VIF design matrices to guarantee full column rank.
  4. Paired Wilcoxon signed-rank tests comparing Batch V2 models against baselines/V1
     on 2024 Test errors (n=144 countries) and Online Champion-Challenger against
     Frozen Baseline / single Challengers on both Monthly Step RMSE (n=30 months)
     and Country-Aggregated MAE/MSE (n=144 countries) (`ml_model_wilcoxon_tests.csv`).

Outputs:
  - `data/analytical/stats/spearman_correlations.csv`
  - `data/analytical/stats/hypothesis_block_tests.csv`
  - `data/analytical/stats/ols_clustered_coefficients.csv`
  - `data/analytical/stats/vif_diagnostics.csv`
  - `data/analytical/stats/ml_model_wilcoxon_tests.csv`

Run:
    PYTHONPATH=src .venv/bin/python -m analysis.statistical_inference
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import false_discovery_control, spearmanr, wilcoxon
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from statsmodels.stats.outliers_influence import variance_inflation_factor

from cyber_pipeline.utils.logging_utils import get_logger
from cyber_pipeline.utils.paths import ANALYTICAL

log = get_logger("statistical_inference")

V1_DIR = ANALYTICAL / "v1"
V2_DIR = ANALYTICAL / "v2"
ONLINE_DIR = ANALYTICAL / "online"
STATS_DIR = ANALYTICAL / "stats"

# ---------------------------------------------------------------------------
# Feature definitions (aligned with V1 Core 10 & V2 Linearly Independent 21)
# ---------------------------------------------------------------------------
CONTROLS_Z = [
    "http_traffic_mean_log_z",
    "population_log_z",
]

H1_V1_Z = [
    "internet_users_pct_z",
    "broadband_subs_per_100_z",
    "routed_asn_count_log_z",
]

H1_V2_EXT_Z = [
    "routed_prefix_count_log_z",
    "ipv4_slash24_count_log_z",
    "secure_servers_per_1m_log_z",
    "ipv6_pct_log_z",
    "tls_1_3_percent_z",
    "bot_traffic_percent_z",
]

H2_PURE_Z = [
    "gdp_per_capita_log_z",
    "fdi_net_inflows_clipped_z",
]

H3_V1_Z = [
    "gci_z_within_edition",
    "v2smgovcapsec_z",
    "gov_effectiveness_z",
]

H3_V2_EXT_Z = [
    "rule_of_law_z",
    "v2smfordom_z",
    "v2x_polyarchy_z",
    "unsecured_asn_z",
    "unsecured_broadband_z",
]

# All 25 V2 features (includes 4 exact algebraic combinations used in tree/Spearman views)
EXACT_LINEAR_COMBO_COLS = [
    "asn_per_capita_log_z",
    "traffic_per_capita_log_z",
    "ipv4_per_asn_log_z",
    "cyber_readiness_index_z",
]

V1_CORE_10 = CONTROLS_Z + H1_V1_Z + H2_PURE_Z + H3_V1_Z
V2_INDEP_21 = CONTROLS_Z + H1_V1_Z + H1_V2_EXT_Z + H2_PURE_Z + H3_V1_Z + H3_V2_EXT_Z
V2_ALL_25 = V2_INDEP_21 + EXACT_LINEAR_COMBO_COLS

HYPOTHESIS_MAP: dict[str, str] = {
    **{c: "Control" for c in CONTROLS_Z},
    **{c: "H1_Digital_Exposure" for c in H1_V1_Z + H1_V2_EXT_Z + ["asn_per_capita_log_z", "traffic_per_capita_log_z", "ipv4_per_asn_log_z"]},
    **{c: "H2_Economy" for c in H2_PURE_Z},
    **{c: "H3_Cyber_Readiness" for c in H3_V1_Z + H3_V2_EXT_Z + ["cyber_readiness_index_z"]},
    "year_2023": "Year_FE",
    "year_2024": "Year_FE",
}


def _sig_stars(p: float) -> str:
    """Return standard academic significance stars for a p-value."""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    if p < 0.10:
        return "."
    return "ns"


def _hypothesis_group(feature: str) -> str:
    """Map a feature column name to its conceptual hypothesis group."""
    return HYPOTHESIS_MAP.get(feature, "Other")


def _compute_vif_map(X_no_const: pd.DataFrame) -> dict[str, float]:
    """Compute Variance Inflation Factor for every column in a full-rank design matrix."""
    X_const = sm.add_constant(X_no_const, has_constant="add")
    rank = int(np.linalg.matrix_rank(X_const.values))
    if rank != X_const.shape[1]:
        raise ValueError(f"Design matrix is rank-deficient: rank={rank} < cols={X_const.shape[1]}")
    vifs: dict[str, float] = {}
    col_names = list(X_const.columns)
    values = X_const.values.astype(float)
    for idx, col in enumerate(col_names):
        if col == "const":
            continue
        vifs[col] = float(variance_inflation_factor(values, idx))
    return vifs


def run_spearman_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Compute bivariate Spearman rank correlations and Benjamini-Hochberg FDR q-values."""
    targets = [
        ("attack_intensity_log", "All_432", df),
        ("attack_intensity_floored_log", "All_432", df),
        ("attack_intensity_log", "Uncensored_399", df[df["is_target_ddos_censored"] == 0]),
        ("origin_ddos_intensity_log", "All_432", df),
        ("origin_l7_intensity_log", "All_432", df),
    ]

    rows: list[dict] = []
    for target, scope, sub in targets:
        raw_rows: list[dict] = []
        pvals: list[float] = []
        for feat in V2_ALL_25:
            rho, p = spearmanr(sub[feat].values, sub[target].values)
            pvals.append(float(p))
            raw_rows.append({
                "target": target,
                "sample_scope": scope,
                "feature": feat,
                "hypothesis_group": _hypothesis_group(feat),
                "n_obs": int(len(sub)),
                "spearman_rho": round(float(rho), 6),
                "p_value": float(p),
            })
        qvals = false_discovery_control(np.asarray(pvals, dtype=float), method="bh")
        for r, q in zip(raw_rows, qvals):
            r["q_value_fdr"] = float(q)
            r["sig_raw"] = _sig_stars(r["p_value"])
            r["sig_fdr"] = _sig_stars(r["q_value_fdr"])
        raw_rows.sort(key=lambda item: abs(item["spearman_rho"]), reverse=True)
        rows.extend(raw_rows)

    return pd.DataFrame(rows)


def run_clustered_ols_and_hypothesis_tests(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fit country-clustered OLS models, nested block Wald F-tests, and VIF tables."""
    df = df.copy()
    df["year_2023"] = (df["year"] == 2023).astype(float)
    df["year_2024"] = (df["year"] == 2024).astype(float)
    year_cols = ["year_2023", "year_2024"]

    targets = [
        ("attack_intensity_log", "All_432", df),
        ("attack_intensity_floored_log", "All_432", df),
        ("attack_intensity_log", "Uncensored_399", df[df["is_target_ddos_censored"] == 0].copy()),
        ("origin_ddos_intensity_log", "All_432", df),
        ("origin_l7_intensity_log", "All_432", df),
    ]

    h1_v1_cols = CONTROLS_Z + H1_V1_Z
    h1_v2_cols = CONTROLS_Z + H1_V1_Z + H1_V2_EXT_Z
    h2_cols = CONTROLS_Z + H2_PURE_Z
    h3_v1_cols = CONTROLS_Z + H3_V1_Z
    h3_v2_cols = CONTROLS_Z + H3_V1_Z + H3_V2_EXT_Z
    full_v2_indep_only = [c for c in V2_INDEP_21 if c not in CONTROLS_Z]
    full_v1_non_ctrl = [c for c in V1_CORE_10 if c not in CONTROLS_Z]

    specs = [
        ("M0_Controls_Only", "Controls_vs_Intercept", False, CONTROLS_Z, CONTROLS_Z),
        ("M1a_Controls_plus_H1_V1", "H1_V1_Digital (3 vars)", False, h1_v1_cols, H1_V1_Z),
        ("M1b_Controls_plus_H1_V2", "H1_V2_Digital_Ext (9 vars)", False, h1_v2_cols, H1_V1_Z + H1_V2_EXT_Z),
        ("M2_Controls_plus_H2_Pure", "H2_Economy_Pure (2 vars)", False, h2_cols, H2_PURE_Z),
        ("M3a_Controls_plus_H3_V1", "H3_V1_Readiness (3 vars)", False, h3_v1_cols, H3_V1_Z),
        ("M3b_Controls_plus_H3_V2", "H3_V2_Readiness_Ext (8 vars)", False, h3_v2_cols, H3_V1_Z + H3_V2_EXT_Z),
        ("M4a_Full_V1_Core_10", "Full_V1_NonControl (8 vars)", False, V1_CORE_10, full_v1_non_ctrl),
        ("M4b_Full_V2_Extended_21", "Full_V2_NonControl (19 vars)", False, V2_INDEP_21, full_v2_indep_only),
        ("M4c_Full_V2_plus_YearFE", "Full_V2_NonControl_with_YearFE (19 vars)", True, V2_INDEP_21 + year_cols, full_v2_indep_only),
    ]

    block_rows: list[dict] = []
    coef_rows: list[dict] = []

    for target, scope, sub in targets:
        m0_r2: float | None = None
        clusters = sub["iso3"].values

        for spec_name, block_label, has_year_fe, x_cols, block_vars in specs:
            X_no_const = sub[x_cols].astype(float)
            vif_map = _compute_vif_map(X_no_const)

            X = sm.add_constant(X_no_const, has_constant="add")
            y = sub[target].astype(float)
            res = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": clusters})

            if spec_name == "M0_Controls_Only":
                m0_r2 = float(res.rsquared)

            # Cluster-robust Wald F-test for the added hypothesis block
            R = np.zeros((len(block_vars), len(X.columns)), dtype=float)
            x_col_list = list(X.columns)
            for row_idx, bcol in enumerate(block_vars):
                R[row_idx, x_col_list.index(bcol)] = 1.0
            ft = res.f_test(R)
            block_f = float(np.asarray(ft.fvalue).item())
            block_p = float(np.asarray(ft.pvalue).item())

            block_rows.append({
                "target": target,
                "sample_scope": scope,
                "model_spec": spec_name,
                "block_tested": block_label,
                "year_fe": has_year_fe,
                "n_obs": int(len(sub)),
                "n_clusters": int(sub["iso3"].nunique()),
                "n_predictors": int(len(x_cols)),
                "r2": round(float(res.rsquared), 6),
                "adj_r2": round(float(res.rsquared_adj), 6),
                "delta_r2_vs_m0": round(float(res.rsquared) - float(m0_r2), 6),
                "aic": round(float(res.aic), 2),
                "bic": round(float(res.bic), 2),
                "overall_f": round(float(np.asarray(res.fvalue).item()), 4),
                "overall_f_pvalue": float(np.asarray(res.f_pvalue).item()),
                "block_wald_f": round(block_f, 4),
                "block_df_num": int(ft.df_num),
                "block_df_denom": int(ft.df_denom),
                "block_wald_pvalue": block_p,
                "block_sig": _sig_stars(block_p),
            })

            conf_int = res.conf_int(alpha=0.05)
            for col in x_cols:
                pval = float(res.pvalues[col])
                coef_rows.append({
                    "target": target,
                    "sample_scope": scope,
                    "model_spec": spec_name,
                    "feature": col,
                    "hypothesis_group": _hypothesis_group(col),
                    "n_obs": int(len(sub)),
                    "n_clusters": int(sub["iso3"].nunique()),
                    "beta_std": round(float(res.params[col]), 6),
                    "cluster_se": round(float(res.bse[col]), 6),
                    "t_stat": round(float(res.tvalues[col]), 4),
                    "p_value": pval,
                    "ci_95_lower": round(float(conf_int.loc[col, 0]), 6),
                    "ci_95_upper": round(float(conf_int.loc[col, 1]), 6),
                    "sig": _sig_stars(pval),
                    "vif": round(float(vif_map[col]), 4),
                })

    # Standalone VIF diagnostic summary on All_432 for V1_Core_10 vs V2_Extended_21
    vif_rows: list[dict] = []
    for set_label, cols in [("V1_Core_10", V1_CORE_10), ("V2_Extended_21", V2_INDEP_21)]:
        vif_map = _compute_vif_map(df[cols].astype(float))
        for col, vval in vif_map.items():
            severity = "Severe (>=10)" if vval >= 10.0 else ("Moderate (5-10)" if vval >= 5.0 else "Low (<5)")
            vif_rows.append({
                "feature_set": set_label,
                "n_features": len(cols),
                "feature": col,
                "hypothesis_group": _hypothesis_group(col),
                "vif": round(float(vval), 4),
                "severity": severity,
            })

    return (
        pd.DataFrame(block_rows),
        pd.DataFrame(coef_rows),
        pd.DataFrame(vif_rows),
    )


def _run_wilcoxon_pair(
    domain: str,
    task_name: str,
    comparison: str,
    eval_unit: str,
    ref_err: np.ndarray,
    cand_err: np.ndarray,
    metric_basis: str,
) -> dict:
    """Run paired two-sided and one-sided Wilcoxon signed-rank tests (H1: ref > cand)."""
    ref_arr = np.asarray(ref_err, dtype=float)
    cand_arr = np.asarray(cand_err, dtype=float)
    diff = ref_arr - cand_arr
    if len(diff) == 0 or np.allclose(diff, 0.0):
        stat, p_two, p_one = 0.0, 1.0, 1.0
    else:
        res_two = wilcoxon(ref_arr, cand_arr, alternative="two-sided", zero_method="wilcox")
        res_one = wilcoxon(ref_arr, cand_arr, alternative="greater", zero_method="wilcox")
        stat = float(res_two.statistic)
        p_two = float(res_two.pvalue)
        p_one = float(res_one.pvalue)

    ref_mean = float(np.mean(ref_arr))
    cand_mean = float(np.mean(cand_arr))
    red_pct = ((ref_mean - cand_mean) / ref_mean * 100.0) if ref_mean > 0 else 0.0

    return {
        "domain": domain,
        "task_name": task_name,
        "comparison": comparison,
        "eval_unit": eval_unit,
        "n_pairs": int(len(diff)),
        "metric_basis": metric_basis,
        "ref_mean_err": round(ref_mean, 6),
        "cand_mean_err": round(cand_mean, 6),
        "err_reduction_pct": round(red_pct, 2),
        "wilcoxon_stat": round(stat, 2),
        "p_value_two_sided": p_two,
        "p_value_one_sided_better": p_one,
        "sig_two_sided": _sig_stars(p_two),
    }


def _reconstruct_baseline_preds(
    df_feat: pd.DataFrame,
    target_col: str,
    model_type: str,
    train_years: list[int],
) -> pd.DataFrame:
    """Reproduce exact 2024 Test predictions for Dummy_Mean or Controls_Only_OLS."""
    train_df = df_feat[df_feat["year"].isin(train_years)].reset_index(drop=True)
    test_df = df_feat[df_feat["year"] == 2024].sort_values("iso3").reset_index(drop=True)

    if model_type == "Dummy_Mean":
        est = DummyRegressor(strategy="mean").fit(train_df[CONTROLS_Z], train_df[target_col])
        preds = est.predict(test_df[CONTROLS_Z])
    elif model_type == "Controls_Only_OLS":
        est = LinearRegression().fit(train_df[CONTROLS_Z], train_df[target_col])
        preds = est.predict(test_df[CONTROLS_Z])
    else:
        raise ValueError(f"Unsupported baseline type: {model_type}")

    out = test_df[["iso3", "year", target_col]].copy()
    out = out.rename(columns={target_col: "y_true"})
    out["y_pred"] = preds
    out["residual"] = out["y_true"] - out["y_pred"]
    return out


def run_wilcoxon_ml_comparisons(df_feat: pd.DataFrame) -> pd.DataFrame:
    """Compare ML error distributions via paired Wilcoxon signed-rank tests."""
    p1 = pd.read_csv(V1_DIR / "model_predictions.csv")
    p2 = pd.read_csv(V2_DIR / "model_predictions.csv")
    m1 = pd.read_csv(V1_DIR / "model_metrics.csv")

    # Sanity verify reconstructed Controls_Only_OLS matches stored V1 test R2
    ctrl_target = _reconstruct_baseline_preds(df_feat, "attack_intensity_log", "Controls_Only_OLS", [2022, 2023])
    expected_r2 = float(
        m1[(m1["task_name"] == "Target_DDoS_Intensity") & (m1["model_name"] == "Controls_Only_OLS")]["test_2024_r2"].iloc[0]
    )
    actual_r2 = float(r2_score(ctrl_target["y_true"], ctrl_target["y_pred"]))
    if abs(actual_r2 - expected_r2) > 1e-3:
        raise RuntimeError(f"Baseline reconstruction mismatch: actual_r2={actual_r2:.4f} vs expected={expected_r2:.4f}")

    def _get_preds(df_p: pd.DataFrame, task: str, model: str) -> pd.DataFrame:
        sub = df_p[(df_p["task_name"] == task) & (df_p["model_name"] == model) & (df_p["split"] == "test")].copy()
        return sub.sort_values("iso3").reset_index(drop=True)

    rows: list[dict] = []

    # --- Batch ML Paired Comparisons on 2024 Test Set (n=144 countries) ---
    batch_specs = [
        (
            "Target_DDoS_Intensity",
            "V2 Extra_Trees vs Dummy_Mean",
            _reconstruct_baseline_preds(df_feat, "attack_intensity_log", "Dummy_Mean", [2022, 2023]),
            _get_preds(p2, "Target_DDoS_Intensity", "Extra_Trees"),
        ),
        (
            "Target_DDoS_Intensity",
            "V2 Extra_Trees vs Controls_Only_OLS",
            _reconstruct_baseline_preds(df_feat, "attack_intensity_log", "Controls_Only_OLS", [2022, 2023]),
            _get_preds(p2, "Target_DDoS_Intensity", "Extra_Trees"),
        ),
        (
            "Target_DDoS_Intensity",
            "V2 Extra_Trees vs V1 Gradient_Boosting",
            _get_preds(p1, "Target_DDoS_Intensity", "Gradient_Boosting"),
            _get_preds(p2, "Target_DDoS_Intensity", "Extra_Trees"),
        ),
        (
            "Target_DDoS_Floored",
            "V2 Voting_Ensemble vs Dummy_Mean",
            _reconstruct_baseline_preds(df_feat, "attack_intensity_floored_log", "Dummy_Mean", [2022, 2023]),
            _get_preds(p2, "Target_DDoS_Floored", "Voting_Ensemble"),
        ),
        (
            "Target_DDoS_Floored",
            "V2 Voting_Ensemble vs Controls_Only_OLS",
            _reconstruct_baseline_preds(df_feat, "attack_intensity_floored_log", "Controls_Only_OLS", [2022, 2023]),
            _get_preds(p2, "Target_DDoS_Floored", "Voting_Ensemble"),
        ),
        (
            "Target_DDoS_Forecast_Lag1",
            "V2 Forecast Extra_Trees vs Controls_Only_OLS (2023 Train)",
            _reconstruct_baseline_preds(df_feat, "attack_intensity_floored_log", "Controls_Only_OLS", [2023]),
            _get_preds(p2, "Target_DDoS_Forecast_Lag1", "Extra_Trees"),
        ),
        (
            "Target_DDoS_Forecast_Lag1",
            "V2 Forecast Extra_Trees vs V2 Structural Voting_Ensemble (Floored)",
            _get_preds(p2, "Target_DDoS_Floored", "Voting_Ensemble"),
            _get_preds(p2, "Target_DDoS_Forecast_Lag1", "Extra_Trees"),
        ),
        (
            "Origin_DDoS_Intensity",
            "V2 Extra_Trees vs Dummy_Mean",
            _reconstruct_baseline_preds(df_feat, "origin_ddos_intensity_log", "Dummy_Mean", [2022, 2023]),
            _get_preds(p2, "Origin_DDoS_Intensity", "Extra_Trees"),
        ),
        (
            "Origin_DDoS_Intensity",
            "V2 Extra_Trees vs Controls_Only_OLS",
            _reconstruct_baseline_preds(df_feat, "origin_ddos_intensity_log", "Controls_Only_OLS", [2022, 2023]),
            _get_preds(p2, "Origin_DDoS_Intensity", "Extra_Trees"),
        ),
        (
            "Origin_DDoS_Intensity",
            "V2 Extra_Trees vs V1 (H3_Readiness) Extra_Trees",
            _get_preds(p1, "Origin_DDoS_Intensity", "Extra_Trees"),
            _get_preds(p2, "Origin_DDoS_Intensity", "Extra_Trees"),
        ),
        (
            "Origin_DDoS_Forecast_Lag1",
            "V2 Forecast Voting_Ensemble vs V2 Structural Extra_Trees",
            _get_preds(p2, "Origin_DDoS_Intensity", "Extra_Trees"),
            _get_preds(p2, "Origin_DDoS_Forecast_Lag1", "Voting_Ensemble"),
        ),
        (
            "Origin_L7_Intensity",
            "V2 Gradient_Boosting vs Dummy_Mean",
            _reconstruct_baseline_preds(df_feat, "origin_l7_intensity_log", "Dummy_Mean", [2022, 2023]),
            _get_preds(p2, "Origin_L7_Intensity", "Gradient_Boosting"),
        ),
        (
            "Origin_L7_Intensity",
            "V2 Gradient_Boosting vs Controls_Only_OLS",
            _reconstruct_baseline_preds(df_feat, "origin_l7_intensity_log", "Controls_Only_OLS", [2022, 2023]),
            _get_preds(p2, "Origin_L7_Intensity", "Gradient_Boosting"),
        ),
        (
            "Origin_L7_Intensity",
            "V2 Gradient_Boosting vs V1 (H3_Readiness) Extra_Trees",
            _get_preds(p1, "Origin_L7_Intensity", "Extra_Trees"),
            _get_preds(p2, "Origin_L7_Intensity", "Gradient_Boosting"),
        ),
        (
            "Origin_L7_Forecast_Lag1",
            "V2 Forecast Extra_Trees vs V2 Structural Gradient_Boosting",
            _get_preds(p2, "Origin_L7_Intensity", "Gradient_Boosting"),
            _get_preds(p2, "Origin_L7_Forecast_Lag1", "Extra_Trees"),
        ),
    ]

    for task, comp, ref_df, cand_df in batch_specs:
        merged = ref_df[["iso3", "residual"]].merge(
            cand_df[["iso3", "residual"]], on="iso3", suffixes=("_ref", "_cand"), validate="one_to_one"
        )
        e_ref = merged["residual_ref"].values
        e_cand = merged["residual_cand"].values
        rows.append(
            _run_wilcoxon_pair("Batch_ML_2024", task, comp, "Country_2024", np.abs(e_ref), np.abs(e_cand), "abs_error")
        )
        rows.append(
            _run_wilcoxon_pair("Batch_ML_2024", task, comp, "Country_2024", e_ref**2, e_cand**2, "squared_error")
        )

    # --- Online ML Paired Comparisons ---
    replay_log = pd.read_csv(ONLINE_DIR / "online_replay_log.csv")
    online_preds = pd.read_csv(ONLINE_DIR / "online_predictions.csv")
    online_preds["residual_retrain"] = online_preds["y_true"] - online_preds["y_pred_retrain"]

    for task in ["Target_DDoS_Intensity", "Origin_DDoS_Intensity", "Origin_L7_Intensity"]:
        sub_r = replay_log[replay_log["task_name"] == task].sort_values("step_idx")
        for comp_label, ref_col in [
            ("Champion_Challenger vs Frozen_Baseline", "frozen_rmse"),
            ("Champion_Challenger vs Online_SGD", "online_sgd_rmse"),
            ("Champion_Challenger vs Sliding_Retrain_8m", "retrain_rmse"),
        ]:
            rows.append(
                _run_wilcoxon_pair(
                    "Online_ML_30m",
                    task,
                    comp_label,
                    "Monthly_Step",
                    sub_r[ref_col].values,
                    sub_r["champion_rmse"].values,
                    "monthly_rmse",
                )
            )

        # Country-level aggregated MAE across 30 replay months (n=144 independent spatial units)
        sub_p = online_preds[online_preds["task_name"] == task].copy()
        for col in ["residual_frozen", "residual_online_sgd", "residual_retrain", "residual_champion"]:
            sub_p[f"abs_{col}"] = np.abs(sub_p[col])
        c_agg = sub_p.groupby("iso3")[
            ["abs_residual_frozen", "abs_residual_online_sgd", "abs_residual_retrain", "abs_residual_champion"]
        ].mean()
        for comp_label, ref_col in [
            ("Champion_Challenger vs Frozen_Baseline", "abs_residual_frozen"),
            ("Champion_Challenger vs Online_SGD", "abs_residual_online_sgd"),
            ("Champion_Challenger vs Sliding_Retrain_8m", "abs_residual_retrain"),
        ]:
            rows.append(
                _run_wilcoxon_pair(
                    "Online_ML_30m",
                    task,
                    comp_label,
                    "Country_Agg_30m",
                    c_agg[ref_col].values,
                    c_agg["abs_residual_champion"].values,
                    "country_mean_abs_error",
                )
            )

    return pd.DataFrame(rows)


def main() -> None:
    """Execute all statistical inference pipelines and export CSVs under `data/analytical/stats/`."""
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    df_feat = pd.read_csv(V2_DIR / "features.csv")
    log.info("Loaded v2/features.csv: %s rows x %s cols (%d countries)", len(df_feat), df_feat.shape[1], df_feat["iso3"].nunique())

    df_spear = run_spearman_analysis(df_feat)
    df_blocks, df_coefs, df_vif = run_clustered_ols_and_hypothesis_tests(df_feat)
    df_wilcox = run_wilcoxon_ml_comparisons(df_feat)

    outputs: list[tuple[Path, pd.DataFrame]] = [
        (STATS_DIR / "spearman_correlations.csv", df_spear),
        (STATS_DIR / "hypothesis_block_tests.csv", df_blocks),
        (STATS_DIR / "ols_clustered_coefficients.csv", df_coefs),
        (STATS_DIR / "vif_diagnostics.csv", df_vif),
        (STATS_DIR / "ml_model_wilcoxon_tests.csv", df_wilcox),
    ]
    for out_path, frame in outputs:
        n_na = int(frame.isna().sum().sum())
        num_cols = frame.select_dtypes(include=[np.number]).columns
        n_inf = int(np.isinf(frame[num_cols].values).sum()) if len(num_cols) > 0 else 0
        if n_na > 0 or n_inf > 0:
            raise ValueError(f"{out_path.name} has invalid entries: NaN={n_na}, Inf={n_inf}")
        frame.to_csv(out_path, index=False)
        log.info("Saved %s (%d rows x %d cols, NaN=0, Inf=0)", out_path, len(frame), frame.shape[1])

    # Console summary of key statistical highlights
    print("\n=== HYPOTHESIS BLOCK WALD F-TESTS (Country-Clustered SE by iso3) ===")
    summary_mask = df_blocks["target"].isin(["attack_intensity_floored_log", "origin_ddos_intensity_log", "origin_l7_intensity_log"])
    print(
        df_blocks.loc[
            summary_mask,
            ["target", "model_spec", "r2", "adj_r2", "delta_r2_vs_m0", "block_wald_f", "block_wald_pvalue", "block_sig"],
        ].to_string(index=False)
    )

    print("\n=== WILCOXON MODEL COMPARISONS (abs_error / monthly_rmse) ===")
    w_sub = df_wilcox[df_wilcox["metric_basis"].isin(["abs_error", "monthly_rmse"])]
    print(
        w_sub[
            ["domain", "task_name", "comparison", "n_pairs", "ref_mean_err", "cand_mean_err", "err_reduction_pct", "p_value_two_sided", "sig_two_sided"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
