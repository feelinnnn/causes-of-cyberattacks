"""Model training, validation (Method 1: GroupKFold on 2022-2023), testing (2024), and feature importance.

Reads engineered features from SQLite `data/warehouse/cyberattacks.db` (table `features`,
or fallback `data/analytical/features.csv`) and trains the 4 selected model families:
  1. Baseline: DummyRegressor (Mean) & Controls-Only OLS (`http_traffic_mean_log_z`, `population_log_z`)
  2. Regularized Linear: Ridge Regression (L2 penalty tuned via 5-Fold GroupKFold by `iso3`)
  3. Bagging Tree Ensemble: Random Forest Regressor & Extra Trees Regressor (depth/leaf tuned via GroupKFold)
  4. Boosting Tree Ensemble: Gradient Boosting Regressor (depth/lr/leaf tuned via GroupKFold)

Outputs:
  - SQLite tables in `data/warehouse/cyberattacks.db`:
      * `model_metrics`
      * `feature_importance`
      * `model_predictions`
  - CSV files in `data/analytical/`:
      * `data/analytical/model_metrics.csv`
      * `data/analytical/feature_importance.csv`
      * `data/analytical/model_predictions.csv`

Run:
    PYTHONPATH=src python -m analysis.train_models
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
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import GridSearchCV, GroupKFold, cross_validate

from cyber_pipeline.utils.logging_utils import get_logger
from cyber_pipeline.utils.paths import ANALYTICAL, DATA

log = get_logger("train_models")
DB_PATH = Path(os.environ.get("SQLITE_PATH", DATA / "warehouse" / "cyberattacks.db"))

# ---------------------------------------------------------------------------
# Feature Sets aligned with Hypotheses H1, H2, H3
# ---------------------------------------------------------------------------
CONTROLS_Z = [
    "http_traffic_mean_log_z",
    "population_log_z",
]

H1_DIGITAL_Z = CONTROLS_Z + [
    "internet_users_pct_z",
    "broadband_subs_per_100_z",
    "routed_asn_count_log_z",
]

H2_ECONOMY_Z = CONTROLS_Z + [
    "gdp_per_capita_log_z",
    "fdi_net_inflows_clipped_z",
]

H3_READINESS_Z = CONTROLS_Z + [
    "gci_z_within_edition",
    "v2smgovcapsec_z",
    "gov_effectiveness_z",
]

ALL_FEATURES_Z = [
    "http_traffic_mean_log_z",
    "population_log_z",
    "internet_users_pct_z",
    "broadband_subs_per_100_z",
    "routed_asn_count_log_z",
    "gdp_per_capita_log_z",
    "fdi_net_inflows_clipped_z",
    "gci_z_within_edition",
    "v2smgovcapsec_z",
    "gov_effectiveness_z",
]

# Tasks to evaluate: (task_name, target_col, feature_set_name, feature_cols, uncensored_only)
EXPERIMENTS: list[tuple[str, str, str, list[str], bool]] = [
    # 1. Target DDoS Attack Intensity (H1 + H2 + Full)
    ("Target_DDoS_Intensity", "attack_intensity_log", "All_Features (H1+H2+H3)", ALL_FEATURES_Z, False),
    ("Target_DDoS_Intensity", "attack_intensity_log", "H1_Digital_Exposure", H1_DIGITAL_Z, False),
    ("Target_DDoS_Intensity", "attack_intensity_log", "H2_Economy", H2_ECONOMY_Z, False),
    ("Target_DDoS_Uncensored_399", "attack_intensity_log", "All_Features (Uncensored 399)", ALL_FEATURES_Z, True),
    # 2. Origin DDoS Attack Intensity (H3 + Full)
    ("Origin_DDoS_Intensity", "origin_ddos_intensity_log", "H3_Cyber_Readiness", H3_READINESS_Z, False),
    ("Origin_DDoS_Intensity", "origin_ddos_intensity_log", "All_Features (H1+H2+H3)", ALL_FEATURES_Z, False),
    # 3. Origin L7 Attack Intensity (H3 + Full)
    ("Origin_L7_Intensity", "origin_l7_intensity_log", "H3_Cyber_Readiness", H3_READINESS_Z, False),
    ("Origin_L7_Intensity", "origin_l7_intensity_log", "All_Features (H1+H2+H3)", ALL_FEATURES_Z, False),
]


def load_features() -> pd.DataFrame:
    """Load engineered features from SQLite `features` table or CSV fallback."""
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as con:
            tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if "features" in tables:
                log.info("Loaded 'features' table from SQLite %s", DB_PATH)
                return pd.read_sql_query('SELECT * FROM "features"', con)
    csv_path = ANALYTICAL / "features.csv"
    log.info("Loaded features from CSV %s", csv_path)
    return pd.read_csv(csv_path, keep_default_na=False, na_values=[""])


def get_model_families() -> list[tuple[str, str, object, dict]]:
    """Return the 4 selected model families: (model_group, model_name, estimator, param_grid)."""
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
            {"alpha": [0.1, 1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 200.0]},
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
            {"max_depth": [2, 3, 4, 6], "min_samples_leaf": [3, 4, 6, 8]},
        ),
        (
            "4_Boosting_Tree",
            "Gradient_Boosting",
            GradientBoostingRegressor(random_state=42),
            {
                "max_depth": [2, 3],
                "n_estimators": [50, 100],
                "learning_rate": [0.03, 0.05, 0.1],
                "min_samples_leaf": [4, 8],
            },
        ),
    ]


def fit_and_evaluate(
    df: pd.DataFrame,
    task_name: str,
    target_col: str,
    feature_set_name: str,
    feature_cols: list[str],
    uncensored_only: bool,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Train all model families using Method 1 (5-Fold GroupKFold on 2022-2023 + Test on 2024)."""
    sub = df[df["is_target_ddos_censored"] == 0].copy() if uncensored_only else df.copy()
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

    for model_group, model_name, estimator, param_grid in get_model_families():
        cols_use = CONTROLS_Z if model_name == "Controls_Only_OLS" else feature_cols
        X_train = train_df[cols_use]
        y_train = train_df[target_col]
        groups_train = train_df["iso3"]

        X_test = test_df[cols_use]
        y_test = test_df[target_col]

        # 1. Tune hyperparameters using 5-Fold GroupKFold on Train (2022-2023)
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

        # 2. Compute 5-Fold GroupKFold Validation metrics (R2, RMSE, MAE) for the best estimator
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

        # 3. Evaluate on Train (2022-2023) and Holdout Test (2024)
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

        # 4. Extract Feature Importance (for non-dummy models)
        if model_name != "Dummy_Mean":
            # Native importance: signed coefficient beta for linear models, impurity importance for trees
            if hasattr(best_est, "coef_"):
                native_vals = np.asarray(best_est.coef_, dtype=float)
                native_type = "standardized_coef_beta"
            elif hasattr(best_est, "feature_importances_"):
                native_vals = np.asarray(best_est.feature_importances_, dtype=float)
                native_type = "gini_impurity_importance"
            else:
                native_vals = np.zeros(len(cols_use))
                native_type = "none"

            # Permutation importance on Test 2024 (model-agnostic out-of-sample ΔR2 impact)
            perm = permutation_importance(
                best_est,
                X_test,
                y_test,
                scoring="r2",
                n_repeats=20,
                random_state=42,
                n_jobs=1,
            )

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

        # 5. Store row-level predictions for the primary feature set of each target
        is_primary_set = (
            (task_name == "Target_DDoS_Intensity" and feature_set_name == "All_Features (H1+H2+H3)")
            or (task_name in ("Origin_DDoS_Intensity", "Origin_L7_Intensity") and feature_set_name == "H3_Cyber_Readiness")
        )
        if is_primary_set and model_name in ("Ridge_Regression", "Random_Forest", "Extra_Trees", "Gradient_Boosting"):
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


def save_results(
    df_metrics: pd.DataFrame,
    df_imp: pd.DataFrame,
    df_preds: pd.DataFrame,
) -> None:
    """Save metrics, feature importance, and predictions to CSV and SQLite."""
    ANALYTICAL.mkdir(parents=True, exist_ok=True)
    m_path = ANALYTICAL / "model_metrics.csv"
    i_path = ANALYTICAL / "feature_importance.csv"
    p_path = ANALYTICAL / "model_predictions.csv"

    df_metrics.to_csv(m_path, index=False, encoding="utf-8")
    df_imp.to_csv(i_path, index=False, encoding="utf-8")
    df_preds.to_csv(p_path, index=False, encoding="utf-8")
    log.info("Saved %s (%d rows), %s (%d rows), %s (%d rows)", m_path.name, len(df_metrics), i_path.name, len(df_imp), p_path.name, len(df_preds))

    if DB_PATH.parent.exists():
        con = sqlite3.connect(DB_PATH)
        try:
            with con:
                df_metrics.to_sql("model_metrics", con, if_exists="replace", index=False)
                df_imp.to_sql("feature_importance", con, if_exists="replace", index=False)
                df_preds.to_sql("model_predictions", con, if_exists="replace", index=False)
            log.info("Saved tables 'model_metrics', 'feature_importance', 'model_predictions' into SQLite %s", DB_PATH)
        finally:
            con.close()


def main() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = load_features()
    all_metrics: list[dict] = []
    all_imp: list[dict] = []
    all_preds: list[dict] = []

    for task_name, target_col, feature_set_name, feature_cols, uncensored_only in EXPERIMENTS:
        log.info("Training models for %-28s | Feature set: %s", task_name, feature_set_name)
        m_rows, i_rows, p_rows = fit_and_evaluate(
            df=df,
            task_name=task_name,
            target_col=target_col,
            feature_set_name=feature_set_name,
            feature_cols=feature_cols,
            uncensored_only=uncensored_only,
        )
        all_metrics.extend(m_rows)
        all_imp.extend(i_rows)
        all_preds.extend(p_rows)

    df_metrics = pd.DataFrame(all_metrics)
    df_imp = pd.DataFrame(all_imp)
    df_preds = pd.DataFrame(all_preds)
    save_results(df_metrics, df_imp, df_preds)
    return df_metrics, df_imp, df_preds


if __name__ == "__main__":
    main()
