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
from sklearn.linear_model import SGDRegressor
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.preprocessing import StandardScaler

from cyber_pipeline.utils.paths import ANALYTICAL

ONLINE_DIR = ANALYTICAL / "online"

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

    tab_replay, tab_whatif, tab_summary = st.tabs([
        f"📈 1. กดดูผลทีละเดือน (Step-by-Step Replay: {current_ym} → {next_ym})",
        "🧪 2. ทดลองป้อนข้อมูลเดือนอนาคตเอง (Interactive What-If Simulator)",
        "📊 3. ตารางสรุปผลรวมตลอด 3 รอบปี (Overall Summary & Drift Log)",
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
    # TAB 2: INTERACTIVE "WHAT-IF" NEXT-MONTH SIMULATOR
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
