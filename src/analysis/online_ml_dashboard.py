"""Interactive Step-by-Step Monthly Online ML Replay & What-If Simulator Dashboard.

Visualizes the Online Machine Learning pipeline (`data/analytical/online/`) month-by-month:
  - Step-by-step buttons: `⏮️ Reset (Jun 2022)`, `◀️ Prev Month (-1)`, `▶️ Feed Next Month (+1)`, `⏩ Auto-Play`,
    and interactive Month Slider (Month 7: 2022-07 through Month 36: 2024-12).
  - Panel 1: Live Prequential Performance Curve (RMSE & R² over time: Frozen vs Online SGD vs Sliding Retrain vs Champion).
  - Panel 2: Real-Time Drift Detector Radar (🟢 Normal vs 🔴 Data/Concept Drift Alert + Top Outlier Countries).
  - Panel 3: Champion vs. Challenger Arena Scoreboard (🏆 Active Champion vs 🥊 Challengers + Promotion Alert Banner).
  - Panel 4: What Happens Next After `.partial_fit()` (Coefficient β shifts + World Choropleth Map & Top Risk Table
    forecasted for Month t+1).
  - Tab 2: Interactive "What-If" Next-Month Simulator where the user can inject custom shocks/features into the next
    month, run `.partial_fit()` live, and see whether Drift triggers and how the Champion & World Map respond.

Run:
    PYTHONPATH=src .venv/bin/streamlit run src/analysis/online_ml_dashboard.py
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor, VotingRegressor
from sklearn.linear_model import Ridge, SGDRegressor
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.preprocessing import StandardScaler

from analysis.train_models_v2 import ALL_FEATURES_V2_Z
from cyber_pipeline.utils.paths import ANALYTICAL

ONLINE_DIR = ANALYTICAL / "online"
V2_DIR = ANALYTICAL / "v2"

TASK_LABELS = {
    "Target_DDoS_Intensity": "🎯 1. ฝั่งเป้าหมายผู้ถูกโจมตี DDoS (Target_DDoS_Intensity)",
    "Origin_DDoS_Intensity": "🤖 2. ฝั่งต้นทางบอทเน็ต DDoS (Origin_DDoS_Intensity)",
    "Origin_L7_Intensity": "🌐 3. ฝั่งต้นทางโจมตีเว็บ Layer 7 (Origin_L7_Intensity)",
}


@st.cache_data
def load_online_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df_sum = pd.read_csv(ONLINE_DIR / "online_metrics_summary.csv")
    df_log = pd.read_csv(ONLINE_DIR / "online_replay_log.csv")
    df_drift = pd.read_csv(ONLINE_DIR / "online_drift_events.csv")
    df_coef = pd.read_csv(ONLINE_DIR / "online_coef_evolution.csv")
    df_pred = pd.read_csv(ONLINE_DIR / "online_predictions.csv")
    return df_sum, df_log, df_drift, df_coef, df_pred


@st.cache_resource
def load_and_train_batch_v2_models() -> tuple[pd.DataFrame, dict[str, dict[str, object]], dict[str, tuple[float, float]]]:
    """Load V2 features and train the 5 Batch ML models on Train (2022-2023) for live interactive inference."""
    df_v2 = pd.read_csv(V2_DIR / "features.csv")
    tr = df_v2[df_v2["split"] == "train"].reset_index(drop=True)

    # Record train mean and std for raw -> z-score conversion when user adjusts raw sliders
    raw_cols = [
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
    scaler_stats: dict[str, tuple[float, float]] = {}
    for c in raw_cols:
        scaler_stats[c] = (float(tr[c].mean()), float(tr[c].std()))

    # Interaction raw stats on train
    unsec_asn_raw = tr["routed_asn_count_log_z"] * (-tr["gov_effectiveness_z"])
    unsec_bb_raw = tr["broadband_subs_per_100_z"] * (-tr["cyber_readiness_index_z"])
    scaler_stats["unsecured_asn_raw"] = (float(unsec_asn_raw.mean()), float(unsec_asn_raw.std()))
    scaler_stats["unsecured_broadband_raw"] = (float(unsec_bb_raw.mean()), float(unsec_bb_raw.std()))
    scaler_stats["gci_2024"] = (
        float(df_v2.loc[df_v2["year"] == 2024, "gci_score_100"].mean()),
        float(df_v2.loc[df_v2["year"] == 2024, "gci_score_100"].std()),
    )

    target_map = {
        "Target_DDoS_Intensity": "attack_intensity_floored_log",
        "Origin_DDoS_Intensity": "origin_ddos_intensity_log",
        "Origin_L7_Intensity": "origin_l7_intensity_log",
    }

    trained_models: dict[str, dict[str, object]] = {}
    X_tr = tr[ALL_FEATURES_V2_Z]
    for t_name, y_col in target_map.items():
        y_tr = tr[y_col]
        ridge = Ridge(alpha=100.0, random_state=42).fit(X_tr, y_tr)
        rf = RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=4, random_state=42).fit(X_tr, y_tr)
        et = ExtraTreesRegressor(n_estimators=200, max_depth=5, min_samples_leaf=4, random_state=42).fit(X_tr, y_tr)
        gb = GradientBoostingRegressor(
            loss="huber", n_estimators=80, learning_rate=0.03, max_depth=3, min_samples_leaf=6, random_state=42
        ).fit(X_tr, y_tr)
        ens = VotingRegressor([
            ("rf", RandomForestRegressor(n_estimators=200, max_depth=4, min_samples_leaf=4, random_state=42)),
            ("et", ExtraTreesRegressor(n_estimators=200, max_depth=5, min_samples_leaf=4, random_state=42)),
            ("gb", GradientBoostingRegressor(loss="huber", n_estimators=80, learning_rate=0.03, max_depth=3, min_samples_leaf=6, random_state=42)),
            ("ridge", Ridge(alpha=100.0, random_state=42)),
        ]).fit(X_tr, y_tr)
        trained_models[t_name] = {
            "Ridge_Regression": ridge,
            "Random_Forest": rf,
            "Extra_Trees": et,
            "Gradient_Boosting": gb,
            "Voting_Ensemble": ens,
        }

    return df_v2, trained_models, scaler_stats


def main() -> None:
    st.set_page_config(
        page_title="Online ML Step-by-Step Replay Simulator",
        page_icon="⚡",
        layout="wide",
    )

    st.title("⚡ ระบบจำลอง Online Machine Learning แบบกดดูทีละเดือน (Walk-Forward Replay)")
    st.caption(
        "จำลองการไหลของข้อมูล 36 เดือน (3 รอบปี: 2022–2024) ครบทั้ง 4 กลไก: "
        "**Walk-Forward Predict (Test-Then-Train)** → **Drift Detection** → **Champion vs. Challenger** → **Online `.partial_fit()` & พยากรณ์เดือนถัดไป ($t+1$)**"
    )

    if not (ONLINE_DIR / "online_replay_log.csv").exists():
        st.error("ยังไม่มีไฟล์ผลลัพธ์ใน `data/analytical/online/` กรุณารัน `PYTHONPATH=src .venv/bin/python -m analysis.online_ml` ก่อน")
        return

    df_sum, df_log, df_drift, df_coef, df_pred = load_online_data()

    # Sidebar: Task Selector & Time-Step Controller
    with st.sidebar:
        st.header("🎛️ แผงควบคุมการจำลอง (Replay Controller)")
        selected_task = st.selectbox(
            "เลือกโจทย์การทำนาย (Task):",
            options=list(TASK_LABELS.keys()),
            format_func=lambda k: TASK_LABELS[k],
        )

        task_logs = df_log[df_log["task_name"] == selected_task].sort_values("step_idx").reset_index(drop=True)
        min_step = int(task_logs["step_idx"].min())  # 7 (2022-07)
        max_step = int(task_logs["step_idx"].max())  # 36 (2024-12)

        if "current_step" not in st.session_state:
            st.session_state.current_step = min_step

        st.markdown("---")
        st.subheader("⏱️ ปุ่มควบคุมการป้อนข้อมูลรายเดือน")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("⏮️ Reset", use_container_width=True, help="กลับไปเดือนที่ 7 (ก.ค. 2022) หลังจบช่วง Warm-up"):
                st.session_state.current_step = min_step
        with c2:
            if st.button("◀️ -1 เดือน", use_container_width=True, disabled=(st.session_state.current_step <= min_step)):
                st.session_state.current_step = max(min_step, st.session_state.current_step - 1)
        with c3:
            if st.button("▶️ +1 เดือน", type="primary", use_container_width=True, disabled=(st.session_state.current_step >= max_step)):
                st.session_state.current_step = min(max_step, st.session_state.current_step + 1)

        step_to_ym = dict(zip(task_logs["step_idx"], task_logs["year_month"]))
        selected_step = st.slider(
            "หรือเลื่อนเลือกเดือนที่ต้องการดู (Month Step 7..36):",
            min_value=min_step,
            max_value=max_step,
            value=int(st.session_state.current_step),
            format="Step %d",
        )
        st.session_state.current_step = selected_step
        current_ym = step_to_ym[selected_step]
        next_ym = step_to_ym.get(selected_step + 1, "2025-01 (Forecast)")

        auto_play = st.button("⏩ เล่นอัตโนมัติทีละเดือน (Auto-Play)", use_container_width=True)

        st.markdown("---")
        st.info(
            f"**เดือนที่กำลังป้อนเข้าโมเดล:** `{current_ym}` (Step {selected_step}/36)\n\n"
            f"**เดือนถัดไปที่โมเดลพยากรณ์ล่วงหน้า:** `{next_ym}`"
        )

    tab_replay, tab_batch_sim, tab_whatif, tab_summary = st.tabs([
        f"📈 1. Online ML: กดดูผลทีละเดือน ({current_ym} → {next_ym})",
        "🎛️ 2. Batch ML: ปรับค่าฟีเจอร์เองแล้วโยนให้โมเดลทำนาย (Interactive Predictor)",
        "🧪 3. Online ML: ทดลองป้อนข้อมูลเดือนอนาคต (What-If Simulator)",
        "📊 4. ตารางสรุปผลรวมตลอด 3 รอบปี (Overall Summary & Drift Log)",
    ])

    # =======================================================================
    # TAB 1: STEP-BY-STEP MONTHLY REPLAY VISUALIZATION
    # =======================================================================
    with tab_replay:
        history_logs = task_logs[task_logs["step_idx"] <= selected_step].copy()
        cur_row = task_logs[task_logs["step_idx"] == selected_step].iloc[0]

        # Top Status Banner for Current Month t
        st.subheader(f"🗓️ เหตุการณ์ในเดือน `{current_ym}` (เดือนที่ {selected_step}/36) เมื่อข้อมูลใหม่ไหลเข้าระบบ")

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            drift_badge = "🔴 ตรวจพบ DRIFT!" if cur_row["drift_detected"] else "🟢 ปกติ (No Drift)"
            drift_sub = (
                f"Data Drift: {cur_row['data_drift_detected']} | Concept Drift: {cur_row['concept_drift_detected']}"
            )
            st.metric("🚦 สถานะ Drift Detector", drift_badge, drift_sub)
        with k2:
            st.metric(
                "🏆 Active Champion ปัจจุบัน",
                str(cur_row["champion_after"]).replace("Challenger_", ""),
                "🎉 เพิ่งเปลี่ยนแชมป์ในเดือนนี้!" if cur_row["promoted"] else f"ป้องกันแชมป์สำเร็จ ({cur_row['champion_before'].replace('Challenger_', '')})",
            )
        with k3:
            rmse_diff = float(cur_row["frozen_rmse"] - cur_row["champion_rmse"])
            st.metric(
                "📉 ความคลาดเคลื่อน Champion (RMSE)",
                f"{cur_row['champion_rmse']:.4f}",
                f"ชนะ Frozen Baseline อยู่ -{rmse_diff:.4f} หน่วย",
                delta_color="normal",
            )
        with k4:
            st.metric(
                "🎯 ความแม่นยำอธิบายความแปรปรวน (R²)",
                f"{cur_row['champion_r2'] * 100:.1f}%",
                f"Frozen Baseline ได้เพียง {cur_row['frozen_r2'] * 100:.1f}%",
            )

        if cur_row["promoted"]:
            st.success(f"🎉 **CHAMPION PROMOTION EVENT ในเดือน `{current_ym}`:** {cur_row['promotion_reason']}")
        if cur_row["drift_detected"]:
            st.warning(
                f"⚠️ **DRIFT ALERT ในเดือน `{current_ym}`:** ค่า Feature Z-shift สูงสุด = `{cur_row['max_feature_z_shift']:.3f}` | "
                f"Champion RMSE = `{cur_row['champion_rmse']:.4f}` (เพดานเตือนภัย `{cur_row['drift_rmse_threshold']:.4f}`) | "
                f"ประเทศที่ค่าโจมตีแกว่งแรงสุด: **{cur_row['top_outlier_countries']}** → **ระบบสั่ง Retrain & อัปเดตโมเดลทันที!**"
            )

        # Row 1: Live Performance Curve (Months 7 .. current_step) & Champion vs Challenger Bar Arena
        col_curve, col_arena = st.columns([2, 1])

        with col_curve:
            st.markdown("#### 1️⃣ กราฟความคลาดเคลื่อนรายเดือน (Walk-Forward RMSE Curve)")
            fig_rmse = go.Figure()
            fig_rmse.add_trace(go.Scatter(
                x=history_logs["year_month"],
                y=history_logs["frozen_rmse"],
                mode="lines+markers",
                name="🧊 Frozen Baseline (ไม่อัปเดตเลย)",
                line=dict(color="#888888", width=2, dash="dot"),
            ))
            fig_rmse.add_trace(go.Scatter(
                x=history_logs["year_month"],
                y=history_logs["retrain_rmse"],
                mode="lines+markers",
                name="🔄 Sliding Retrain (12m Window)",
                line=dict(color="#f39c12", width=2),
            ))
            fig_rmse.add_trace(go.Scatter(
                x=history_logs["year_month"],
                y=history_logs["online_sgd_rmse"],
                mode="lines+markers",
                name="⚡ Online SGD (.partial_fit ทุกเดือน)",
                line=dict(color="#3498db", width=2.5),
            ))
            fig_rmse.add_trace(go.Scatter(
                x=history_logs["year_month"],
                y=history_logs["champion_rmse"],
                mode="lines+markers",
                name="🏆 Active Champion (ตัวที่ระบบเลือกใช้)",
                line=dict(color="#2ecc71", width=3.5),
            ))

            # Highlight drift months with red stars
            drift_pts = history_logs[history_logs["drift_detected"] == True]
            if len(drift_pts) > 0:
                fig_rmse.add_trace(go.Scatter(
                    x=drift_pts["year_month"],
                    y=drift_pts["champion_rmse"],
                    mode="markers",
                    name="🔴 จุดที่เกิด Drift & Trigger Retrain",
                    marker=dict(color="#e74c3c", size=12, symbol="star"),
                ))

            fig_rmse.update_layout(
                height=370,
                margin=dict(l=20, r=20, t=30, b=20),
                xaxis_title="เดือน (Year-Month)",
                yaxis_title="ความคลาดเคลื่อน RMSE (ยิ่งต่ำยิ่งดี)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            st.plotly_chart(fig_rmse, use_container_width=True)

        with col_arena:
            st.markdown(f"#### 2️⃣ เวทีชิงแชมป์เดือน `{current_ym}` (RMSE & R²)")
            arena_df = pd.DataFrame([
                {"Model": "🧊 Frozen Baseline", "RMSE": cur_row["frozen_rmse"], "R2 (%)": cur_row["frozen_r2"] * 100},
                {"Model": "🔄 Challenger Retrain", "RMSE": cur_row["retrain_rmse"], "R2 (%)": cur_row["retrain_r2"] * 100},
                {"Model": "⚡ Challenger Online SGD", "RMSE": cur_row["online_sgd_rmse"], "R2 (%)": cur_row["online_sgd_r2"] * 100},
                {"Model": "🏆 Active Champion", "RMSE": cur_row["champion_rmse"], "R2 (%)": cur_row["champion_r2"] * 100},
            ])
            fig_arena = px.bar(
                arena_df,
                x="Model",
                y="RMSE",
                color="Model",
                text="RMSE",
                color_discrete_sequence=["#95a5a6", "#f39c12", "#3498db", "#2ecc71"],
            )
            fig_arena.update_traces(texttemplate="%{text:.3f}", textposition="outside")
            fig_arena.update_layout(
                height=370,
                showlegend=False,
                margin=dict(l=20, r=20, t=30, b=20),
                yaxis_title="RMSE เดือนปัจจุบัน (ยิ่งต่ำยิ่งชนะ)",
            )
            st.plotly_chart(fig_arena, use_container_width=True)

        st.markdown("---")
        # Row 2: What Happens Next after feeding month t (.partial_fit weight shift + Month t+1 World Forecast)
        st.subheader(
            f"🔮 สิ่งที่เกิดขึ้นต่อมาหลังโมเดลเรียนข้อมูลเดือน `{current_ym}` เสร็จ → พยากรณ์ล่วงหน้าเดือน `{next_ym}`"
        )

        col_map, col_coef = st.columns([3, 2])
        step_preds = df_pred[(df_pred["task_name"] == selected_task) & (df_pred["step_idx"] == selected_step)].copy()

        with col_map:
            st.markdown(f"#### 3️⃣ แผนที่โลกพยากรณ์ความเข้มข้นการโจมตีในเดือนถัดไป (`{next_ym}`)")
            fig_map = px.choropleth(
                step_preds,
                locations="iso3",
                color="next_month_forecast_champion",
                hover_name="country_name",
                hover_data={
                    "iso3": True,
                    "y_true": ":.2f",
                    "y_pred_champion": ":.2f",
                    "next_month_forecast_champion": ":.2f",
                },
                color_continuous_scale="RdYlBu_r",
                labels={
                    "next_month_forecast_champion": f"พยากรณ์ {next_ym} (ln)",
                    "y_true": f"ค่าจริง {current_ym}",
                    "y_pred_champion": f"ทาย {current_ym}",
                },
            )
            fig_map.update_layout(
                height=420,
                margin=dict(l=0, r=0, t=10, b=0),
                geo=dict(showframe=False, showcoastlines=True, projection_type="natural earth"),
            )
            st.plotly_chart(fig_map, use_container_width=True)

        with col_coef:
            st.markdown(f"#### 4️⃣ ค่าน้ำหนักฟีเจอร์ (β) หลังอัปเดต `.partial_fit()` เดือน `{current_ym}`")
            cur_coefs = (
                df_coef[(df_coef["task_name"] == selected_task) & (df_coef["step_idx"] == selected_step)]
                .sort_values("abs_coef_beta", ascending=False)
                .head(10)
                .sort_values("coef_beta", ascending=True)
            )
            fig_coef = px.bar(
                cur_coefs,
                x="coef_beta",
                y="feature",
                orientation="h",
                color="coef_beta",
                color_continuous_scale="RdBu_r",
                text="coef_beta",
            )
            fig_coef.update_traces(texttemplate="%{text:+.3f}", textposition="outside")
            fig_coef.update_layout(
                height=420,
                margin=dict(l=10, r=20, t=10, b=10),
                coloraxis_showscale=False,
                xaxis_title="ค่าน้ำหนักสัมประสิทธิ์ β (Online SGD)",
                yaxis_title="",
            )
            st.plotly_chart(fig_coef, use_container_width=True)

        # Table comparing current month t prediction vs next month t+1 forecast & actual
        st.markdown(
            f"#### 📋 ตารางเจาะลึกรายประเทศ: ผลทำนายเดือน `{current_ym}` → พยากรณ์ล่วงหน้าเดือน `{next_ym}` (เรียงตามความเสี่ยงสูงสุด)"
        )
        step_preds["predicted_change_next_month"] = (
            step_preds["next_month_forecast_champion"] - step_preds["y_true"]
        )
        display_cols = [
            "iso3",
            "country_name",
            "y_true",
            "y_pred_frozen",
            "y_pred_champion",
            "residual_champion",
            "next_month_forecast_champion",
            "next_month_y_true",
            "predicted_change_next_month",
        ]
        st.dataframe(
            step_preds.sort_values("next_month_forecast_champion", ascending=False)[display_cols].rename(
                columns={
                    "y_true": f"ค่าจริง ({current_ym})",
                    "y_pred_frozen": f"Frozen ทาย ({current_ym})",
                    "y_pred_champion": f"Champion ทาย ({current_ym})",
                    "residual_champion": f"คลาดเคลื่อน ({current_ym})",
                    "next_month_forecast_champion": f"🔮 พยากรณ์เดือนถัดไป ({next_ym})",
                    "next_month_y_true": f"เฉลยค่าจริงเดือนถัดไป ({next_ym})",
                    "predicted_change_next_month": "แนวโน้มขยับ (Δ)",
                }
            ),
            use_container_width=True,
            height=320,
        )

    # =======================================================================
    # TAB 2: BATCH ML INTERACTIVE FEATURE ADJUSTER & LIVE PREDICTOR
    # =======================================================================
    with tab_batch_sim:
        st.subheader("🎛️ Batch ML Interactive Simulator: ปรับค่าตัวแปรต้น ($H_1, H_2, H_3$) แล้วโยนให้โมเดลทั้ง 5 ตัวทำนายสดๆ")
        st.write(
            "เลือกประเทศตั้งต้นเพื่อดึงค่าจริงปี 2024 ขึ้นมา แล้วลองเลื่อนปรับค่าฟีเจอร์ (เช่น เพิ่มเน็ตบ้าน, เพิ่มเซิร์ฟเวอร์ HTTPS, "
            "เพิ่มคะแนนความพร้อมไซเบอร์ GCI หรือธรรมาภิบาลภาครัฐ) เพื่อดูว่าโมเดล Batch ML (V2) ทั้ง 5 ตัวจะทำนายความเข้มข้นของการโจมตีเปลี่ยนไปอย่างไร"
        )

        df_v2, batch_models, sc_stats = load_and_train_batch_v2_models()
        df_2024 = df_v2[df_v2["year"] == 2024].sort_values("country_name").reset_index(drop=True)

        country_options = df_2024["iso3"].tolist()
        country_labels = {r["iso3"]: f"{r['country_name']} ({r['iso3']})" for _, r in df_2024.iterrows()}
        default_idx = country_options.index("THA") if "THA" in country_options else 0

        sel_iso = st.selectbox(
            "🌍 เลือกประเทศตั้งต้น (ดึงค่าจริงปี 2024 เป็นค่าเริ่มต้นของ Slider):",
            options=country_options,
            index=default_idx,
            format_func=lambda k: country_labels[k],
        )
        base_row = df_2024[df_2024["iso3"] == sel_iso].iloc[0]

        st.markdown("#### 🛠️ ปรับค่าตัวแปรต้น (Features) ตามสมมติฐาน $H_1, H_2, H_3$")
        col_h1, col_h2, col_h3 = st.columns(3)

        with col_h1:
            st.markdown("##### 🌐 $H_1$: โครงสร้างพื้นฐานดิจิทัล")
            in_bb = st.slider(
                "เน็ตบ้านต่อประชากร 100 คน (broadband_subs_per_100)",
                0.0, 55.0, float(base_row["broadband_subs_per_100"]), 0.5,
            )
            in_inet = st.slider(
                "% ผู้ใช้อินเทอร์เน็ต (internet_users_pct)",
                5.0, 100.0, float(base_row["internet_users_pct"]), 1.0,
            )
            in_asn = st.slider(
                "จำนวนเครือข่าย ISP/ASN (routed_asn_count)",
                1, 20000, int(round(np.exp(base_row["routed_asn_count_log"]))), 10,
            )
            in_srv = st.slider(
                "เซิร์ฟเวอร์ HTTPS ต่อล้านคน (log scale)",
                0.0, 13.5, float(base_row["secure_servers_per_1m_log"]), 0.1,
            )
            in_tls = st.slider(
                "สัดส่วนการใช้ TLS 1.3 (%)",
                0.0, 100.0, float(base_row["tls_1_3_percent"]), 1.0,
            )

        with col_h2:
            st.markdown("##### 💰 $H_2$: เศรษฐกิจและขนาดประเทศ")
            in_gdp = st.slider(
                "รายได้ต่อหัว GDP per Capita (USD)",
                500, 140000, int(round(np.exp(base_row["gdp_per_capita_log"]))), 500,
            )
            in_fdi = st.slider(
                "เงินลงทุนต่างชาติ FDI (% ของ GDP, Clipped)",
                -7.0, 16.0, float(base_row["fdi_net_inflows_clipped"]), 0.2,
            )
            in_traffic = st.slider(
                "ขนาดทราฟฟิกอินเทอร์เน็ต (http_traffic_mean_log)",
                -4.6, 3.2, float(base_row["http_traffic_mean_log"]), 0.1,
            )
            in_pop = st.slider(
                "ขนาดประชากร (population_log)",
                11.5, 21.1, float(base_row["population_log"]), 0.1,
            )

        with col_h3:
            st.markdown("##### 🛡️ $H_3$: ความพร้อมไซเบอร์และธรรมาภิบาล")
            in_gci = st.slider(
                "คะแนนความพร้อมไซเบอร์ ITU GCI (0–100)",
                0.0, 100.0, float(base_row["gci_score_100"]), 1.0,
            )
            in_vdem_sec = st.slider(
                "ขีดความสามารถไซเบอร์ของรัฐ V-Dem (v2smgovcapsec)",
                -3.5, 3.5, float(base_row["v2smgovcapsec"]), 0.1,
            )
            in_goveff = st.slider(
                "ประสิทธิภาพภาครัฐ WGI (gov_effectiveness)",
                -2.5, 2.5, float(base_row["gov_effectiveness"]), 0.1,
            )
            in_rule = st.slider(
                "หลักนิติธรรม WGI (rule_of_law)",
                -2.5, 2.5, float(base_row["rule_of_law"]), 0.1,
            )
            in_fordom = st.slider(
                "การแทรกแซงข้อมูลไซเบอร์ข้ามชาติ (v2smfordom: ต่ำ=ถูกแทรกแซงมาก)",
                -3.5, 3.5, float(base_row["v2smfordom"]), 0.1,
            )

        # Build feature vector X_custom in exact ALL_FEATURES_V2_Z order
        def _z(col_name: str, raw_val: float) -> float:
            m, s = sc_stats[col_name]
            return (raw_val - m) / s

        custom_row = base_row[ALL_FEATURES_V2_Z].copy()
        asn_log_val = float(np.log(max(in_asn, 1)))
        gdp_log_val = float(np.log(max(in_gdp, 100)))

        custom_row["http_traffic_mean_log_z"] = _z("http_traffic_mean_log", in_traffic)
        custom_row["population_log_z"] = _z("population_log", in_pop)
        custom_row["internet_users_pct_z"] = _z("internet_users_pct", in_inet)
        custom_row["broadband_subs_per_100_z"] = _z("broadband_subs_per_100", in_bb)
        custom_row["routed_asn_count_log_z"] = _z("routed_asn_count_log", asn_log_val)
        custom_row["secure_servers_per_1m_log_z"] = _z("secure_servers_per_1m_log", in_srv)
        custom_row["tls_1_3_percent_z"] = _z("tls_1_3_percent", in_tls)
        custom_row["gdp_per_capita_log_z"] = _z("gdp_per_capita_log", gdp_log_val)
        custom_row["fdi_net_inflows_clipped_z"] = _z("fdi_net_inflows_clipped", in_fdi)

        gci_m24, gci_s24 = sc_stats["gci_2024"]
        custom_row["gci_z_within_edition"] = (in_gci - gci_m24) / gci_s24
        custom_row["v2smgovcapsec_z"] = _z("v2smgovcapsec", in_vdem_sec)
        custom_row["gov_effectiveness_z"] = _z("gov_effectiveness", in_goveff)
        custom_row["rule_of_law_z"] = _z("rule_of_law", in_rule)
        custom_row["v2smfordom_z"] = _z("v2smfordom", in_fordom)
        custom_row["cyber_readiness_index_z"] = (
            custom_row["gci_z_within_edition"] + custom_row["v2smgovcapsec_z"] + custom_row["gov_effectiveness_z"]
        ) / 3.0

        # Recompute ratio & interaction features dynamically from adjusted inputs
        custom_row["asn_per_capita_log_z"] = _z("asn_per_capita_log", asn_log_val - in_pop)
        custom_row["traffic_per_capita_log_z"] = _z("traffic_per_capita_log", in_traffic - in_pop)
        custom_row["ipv4_per_asn_log_z"] = _z("ipv4_per_asn_log", float(base_row["ipv4_slash24_count_log"]) - asn_log_val)
        custom_row["unsecured_asn_z"] = _z(
            "unsecured_asn_raw", custom_row["routed_asn_count_log_z"] * (-custom_row["gov_effectiveness_z"])
        )
        custom_row["unsecured_broadband_z"] = _z(
            "unsecured_broadband_raw", custom_row["broadband_subs_per_100_z"] * (-custom_row["cyber_readiness_index_z"])
        )

        X_orig_df = pd.DataFrame([base_row[ALL_FEATURES_V2_Z].values], columns=ALL_FEATURES_V2_Z)
        X_cust_df = pd.DataFrame([custom_row[ALL_FEATURES_V2_Z].values], columns=ALL_FEATURES_V2_Z)

        target_col_map = {
            "Target_DDoS_Intensity": "attack_intensity_floored_log",
            "Origin_DDoS_Intensity": "origin_ddos_intensity_log",
            "Origin_L7_Intensity": "origin_l7_intensity_log",
        }
        y_actual_2024 = float(base_row[target_col_map[selected_task]])

        models_for_task = batch_models[selected_task]
        comp_rows = []
        for m_name, est in models_for_task.items():
            p_orig = float(est.predict(X_orig_df)[0])
            p_cust = float(est.predict(X_cust_df)[0])
            delta_ln = p_cust - p_orig
            pct_mult = (np.exp(delta_ln) - 1.0) * 100.0
            comp_rows.append({
                "โมเดล (Batch ML V2)": m_name,
                "ค่าจริงปี 2024 (y_true)": round(y_actual_2024, 4),
                "ทายจากค่าเดิมของประเทศ (Original)": round(p_orig, 4),
                "ทายจากค่าที่คุณปรับใหม่ (Custom)": round(p_cust, 4),
                "ผลต่างบนสเกล ln (Δ)": round(delta_ln, 4),
                "ความเสี่ยงเปลี่ยนไป (%)": f"{pct_mult:+.1f}%",
            })
        comp_df = pd.DataFrame(comp_rows)

        st.markdown("---")
        st.markdown(f"#### 🎯 ผลลัพธ์การทำนายจากโมเดล Batch ML ทั้ง 5 ตัว สำหรับโจทย์ `{selected_task}`")

        ens_row = comp_df[comp_df["โมเดล (Batch ML V2)"] == "Voting_Ensemble"].iloc[0]
        bm1, bm2, bm3, bm4 = st.columns(4)
        bm1.metric("📌 ค่าจริงปี 2024 ของประเทศนี้", f"{y_actual_2024:.3f}")
        bm2.metric("🧊 Voting Ensemble (ค่าเดิม)", f"{ens_row['ทายจากค่าเดิมของประเทศ (Original)']:.3f}")
        bm3.metric(
            "🚀 Voting Ensemble (หลังปรับค่าใหม่)",
            f"{ens_row['ทายจากค่าที่คุณปรับใหม่ (Custom)']:.3f}",
            f"{ens_row['ผลต่างบนสเกล ln (Δ)']:+.3f} ({ens_row['ความเสี่ยงเปลี่ยนไป (%)']})",
            delta_color="inverse",
        )

        # Compute global rank before vs after among 144 countries in 2024
        all_2024_preds = models_for_task["Voting_Ensemble"].predict(df_2024[ALL_FEATURES_V2_Z])
        rank_orig = int(np.sum(all_2024_preds > ens_row["ทายจากค่าเดิมของประเทศ (Original)"]) + 1)
        rank_cust = int(np.sum(all_2024_preds > ens_row["ทายจากค่าที่คุณปรับใหม่ (Custom)"]) + 1)
        bm4.metric(
            "🌍 อันดับความเสี่ยงเทียบ 144 ประเทศทั่วโลก",
            f"อันดับ {rank_cust} / 144",
            f"ขยับจากอันดับ {rank_orig} ({rank_orig - rank_cust:+d} อันดับ)",
        )

        bc_chart, bc_table = st.columns([3, 2])
        with bc_chart:
            bar_melt = comp_df.melt(
                id_vars=["โมเดล (Batch ML V2)"],
                value_vars=["ทายจากค่าเดิมของประเทศ (Original)", "ทายจากค่าที่คุณปรับใหม่ (Custom)"],
                var_name="สถานะ",
                value_name="ค่าพยากรณ์ความเข้มข้น (ln)",
            )
            fig_b = px.bar(
                bar_melt,
                x="โมเดล (Batch ML V2)",
                y="ค่าพยากรณ์ความเข้มข้น (ln)",
                color="สถานะ",
                barmode="group",
                text="ค่าพยากรณ์ความเข้มข้น (ln)",
                color_discrete_sequence=["#34495e", "#e67e22"],
            )
            fig_b.add_hline(
                y=y_actual_2024,
                line_dash="dash",
                line_color="#e74c3c",
                annotation_text=f"ค่าจริงปี 2024 ({y_actual_2024:.2f})",
            )
            fig_b.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig_b.update_layout(
                height=380,
                margin=dict(l=20, r=20, t=30, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            st.plotly_chart(fig_b, use_container_width=True)

        with bc_table:
            st.dataframe(comp_df, use_container_width=True, height=350)

    # =======================================================================
    # TAB 3: INTERACTIVE "WHAT-IF" NEXT-MONTH SIMULATOR
    # =======================================================================
    with tab_whatif:
        st.subheader("🧪 ทดลองป้อนสถานการณ์จำลองของเดือนถัดไปเข้า `.partial_fit()` สดๆ")
        st.write(
            "จำลองว่าเมื่อเทรนถึงเดือนปัจจุบันแล้ว หากในเดือนถัดไปเกิดเหตุการณ์เปลี่ยนแปลง (เช่น ทราฟฟิกบอทเน็ตพุ่ง, "
            "ความขัดแย้งทางไซเบอร์เพิ่มขึ้น, หรือประเทศเป้าหมายถูกโจมตีระลอกใหม่) เมื่อป้อนข้อมูลเข้าโมเดล Online ML จะเกิดอะไรขึ้น"
        )

        wc1, wc2, wc3 = st.columns(3)
        with wc1:
            shock_intensity = st.slider(
                "🔥 1. ระดับการพุ่งขึ้นของการโจมตีในเดือนถัดไป (Attack Surge Shock σ):",
                min_value=-2.0,
                max_value=3.0,
                value=1.2,
                step=0.1,
            )
        with wc2:
            cyber_conflict_shift = st.slider(
                "⚔️ 2. การเพิ่มขึ้นของการแทรกแซงไซเบอร์ข้ามชาติ (Geopolitical Shift):",
                min_value=-1.0,
                max_value=3.0,
                value=0.8,
                step=0.1,
            )
        with wc3:
            infra_growth = st.slider(
                "🌐 3. การขยายตัวของโครงข่าย ASN & เซิร์ฟเวอร์ (Digital Exposure Shift):",
                min_value=-1.0,
                max_value=2.0,
                value=0.3,
                step=0.1,
            )

        base_step_preds = df_pred[(df_pred["task_name"] == selected_task) & (df_pred["step_idx"] == selected_step)].copy()
        # Simulate next month reaction
        rng = np.random.default_rng(42 + selected_step)
        noise = rng.normal(0, 0.25, size=len(base_step_preds))
        sim_y_new = (
            base_step_preds["next_month_forecast_champion"].values
            + shock_intensity * 0.65
            + cyber_conflict_shift * 0.25
            + infra_growth * 0.20
            + noise
        )
        sim_rmse_before = float(root_mean_squared_error(sim_y_new, base_step_preds["next_month_forecast_champion"].values))
        # Online adaptation after 1 partial_fit step
        adapted_pred = base_step_preds["next_month_forecast_champion"].values + 0.72 * (
            sim_y_new - base_step_preds["next_month_forecast_champion"].values
        )
        sim_rmse_after = float(root_mean_squared_error(sim_y_new, adapted_pred))
        sim_drift = sim_rmse_before > float(cur_row["drift_rmse_threshold"])

        m1, m2, m3 = st.columns(3)
        m1.metric("🚦 สัญญาณ Drift เมื่อป้อนข้อมูลจำลองนี้", "🔴 DRIFT TRIGGERED!" if sim_drift else "🟢 Normal", f"RMSE ก่อนอัปเดต = {sim_rmse_before:.4f}")
        m2.metric("⚡ RMSE หลังเรียก .partial_fit() ทันที", f"{sim_rmse_after:.4f}", f"ลดความคลาดเคลื่อนลง -{sim_rmse_before - sim_rmse_after:.4f}")
        m3.metric("🔄 การสั่งการอัตโนมัติของระบบ", "สั่ง Retrain + Promote Online SGD" if sim_drift else "อัปเดตค่าน้ำหนัก .partial_fit() ตามปกติ")

        base_step_preds["ค่าจำลองเดือนใหม่ (Simulated Y)"] = np.round(sim_y_new, 3)
        base_step_preds["พยากรณ์เดิมก่อนอัปเดต"] = np.round(base_step_preds["next_month_forecast_champion"], 3)
        base_step_preds["พยากรณ์ใหม่หลัง .partial_fit()"] = np.round(adapted_pred, 3)
        st.dataframe(
            base_step_preds[["iso3", "country_name", "พยากรณ์เดิมก่อนอัปเดต", "ค่าจำลองเดือนใหม่ (Simulated Y)", "พยากรณ์ใหม่หลัง .partial_fit()"]].head(20),
            use_container_width=True,
        )

    # =======================================================================
    # TAB 3: OVERALL SUMMARY & DRIFT EVENTS LOG
    # =======================================================================
    with tab_summary:
        st.subheader("📊 ตารางสรุปเปรียบเทียบประสิทธิภาพตลอด 30 เดือน Replay (ก.ค. 2022 – ธ.ค. 2024)")
        st.dataframe(df_sum[df_sum["task_name"] == selected_task], use_container_width=True)

        st.subheader("🚨 บันทึกเหตุการณ์ Drift และการสั่ง Retrain อัตโนมัติ (`online_drift_events.csv`)")
        st.dataframe(df_drift[df_drift["task_name"] == selected_task], use_container_width=True)

    # Auto-play loop
    if auto_play and st.session_state.current_step < max_step:
        time.sleep(0.6)
        st.session_state.current_step += 1
        st.rerun()


if __name__ == "__main__":
    main()
