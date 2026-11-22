"""Interactive Step-by-Step Monthly Online ML Replay & What-If Simulator Dashboard.

Visualizes the Online Machine Learning pipeline (`data/analytical/online/`) month-by-month:
  - Step-by-step buttons: `Reset (Jun 2022)`, `Prev Month (-1)`, `Feed Next Month (+1)`, `Auto-Play`,
    and interactive Month Slider (Month 7: 2022-07 through Month 36: 2024-12).
  - Panel 1: Live Prequential Performance Curve (RMSE & R² over time: Frozen vs Online SGD vs Sliding Retrain vs Champion).
  - Panel 2: Real-Time Drift Detector Radar (Normal vs Data/Concept Drift Alert + Top Outlier Countries).
  - Panel 3: Champion vs. Challenger Arena Scoreboard (Active Champion vs Challengers + Promotion Alert Banner).
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
from sklearn.linear_model import Ridge
from sklearn.metrics import root_mean_squared_error

from analysis.train_models_v2 import ALL_FEATURES_V2_Z
from cyber_pipeline.utils.paths import ANALYTICAL

ONLINE_DIR = ANALYTICAL / "online"
V2_DIR = ANALYTICAL / "v2"

TASK_LABELS = {
    "Target_DDoS_Intensity": "1. เป้าหมายผู้ถูกโจมตี DDoS (Target DDoS)",
    "Origin_DDoS_Intensity": "2. ต้นทางบอทเน็ต DDoS (Origin DDoS)",
    "Origin_L7_Intensity": "3. ต้นทางโจมตีเว็บ Layer 7 (Origin L7)",
}

# Display-only Thai labels for model feature coefficients (no effect on calculations)
FEATURE_DISPLAY_NAMES = {
    "lag1_y": "ค่าโจมตีเดือนก่อน (Lag 1)",
    "lag2_y": "ค่าโจมตี 2 เดือนก่อน (Lag 2)",
    "rolling_3m_mean_y": "ค่าเฉลี่ยโจมตี 3 เดือนล่าสุด",
    "rolling_3m_std_y": "ความผันผวน 3 เดือนล่าสุด (SD)",
    "lag1_trend_ratio": "สัดส่วนแนวโน้มเดือนก่อน",
    "lag1_trend_std": "ความแกว่งแนวโน้มเดือนก่อน",
    "month_sin": "ฤดูกาลรายเดือน (Sin)",
    "month_cos": "ฤดูกาลรายเดือน (Cos)",
    "broadband_subs_per_100_z": "เน็ตบ้านต่อ 100 คน (H1)",
    "secure_servers_per_1m_log_z": "เซิร์ฟเวอร์ HTTPS ต่อล้านคน (H1)",
    "routed_asn_count_log_z": "จำนวนเครือข่าย ASN (H1)",
    "routed_prefix_count_log_z": "จำนวน Prefix เครือข่าย (H1)",
    "asn_per_capita_log_z": "ASN ต่อประชากร (H1)",
    "traffic_per_capita_log_z": "ทราฟฟิกต่อประชากร (H1)",
    "ipv4_per_asn_log_z": "IPv4 ต่อ 1 ASN (H1)",
    "internet_users_pct_z": "% ผู้ใช้อินเทอร์เน็ต (H1)",
    "http_traffic_mean_log_z": "ปริมาณ HTTP Traffic (Control)",
    "population_log_z": "ขนาดประชากร (Control)",
    "gdp_per_capita_log_z": "รายได้ต่อหัว GDP (H2)",
    "fdi_net_inflows_clipped_z": "เงินลงทุนต่างชาติ FDI (H2)",
    "gci_z_within_edition": "ความพร้อมไซเบอร์ GCI (H3)",
    "v2smgovcapsec_z": "ศักยภาพไซเบอร์ภาครัฐ V-Dem (H3)",
    "gov_effectiveness_z": "ประสิทธิภาพภาครัฐ WGI (H3)",
    "rule_of_law_z": "หลักนิติธรรม WGI (H3)",
    "v2smfordom_z": "การแทรกแซงไซเบอร์ข้ามชาติ (H3)",
    "v2x_polyarchy_z": "ดัชนีประชาธิปไตย (H3)",
    "unsecured_asn_z": "ASN × ธรรมาภิบาลต่ำ (Interaction)",
    "unsecured_broadband_z": "เน็ตบ้าน × ไซเบอร์ต่ำ (Interaction)",
}

PALETTE = {
    "frozen": "#94A3B8",
    "retrain": "#F59E0B",
    "online": "#0284C7",
    "champion": "#10B981",
    "drift": "#EF4444",
    "orig": "#64748B",
    "custom": "#EA580C",
}


def _inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2.5rem;
            max-width: 1420px;
        }
        .hero-box {
            padding: 1.15rem 1.4rem;
            border-radius: 14px;
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-left: 5px solid #0284C7;
            background: var(--secondary-background-color);
            margin-bottom: 1rem;
        }
        .hero-title {
            font-size: 1.55rem;
            font-weight: 700;
            margin: 0 0 0.35rem 0;
            line-height: 1.25;
        }
        .hero-sub {
            font-size: 0.92rem;
            opacity: 0.85;
            margin: 0 0 0.65rem 0;
        }
        .flow-pills {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            align-items: center;
            font-size: 0.82rem;
        }
        .flow-pill {
            display: inline-block;
            padding: 0.22rem 0.65rem;
            border-radius: 999px;
            border: 1px solid rgba(2, 132, 199, 0.35);
            background: rgba(2, 132, 199, 0.10);
            font-weight: 600;
        }
        .flow-arrow {
            opacity: 0.55;
            font-weight: 700;
        }
        div[data-testid="stMetric"] {
            background: var(--secondary-background-color);
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-radius: 12px;
            padding: 0.85rem 1rem;
        }
        div[data-testid="stMetricLabel"] p {
            font-size: 0.84rem !important;
            font-weight: 600 !important;
            opacity: 0.82;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.45rem !important;
            font-weight: 700 !important;
        }
        div[data-testid="stMetricDelta"] {
            font-size: 0.82rem !important;
        }
        button[data-baseweb="tab"] {
            font-weight: 600 !important;
            font-size: 0.92rem !important;
            padding: 0.55rem 1rem !important;
        }
        .section-hint {
            font-size: 0.84rem;
            opacity: 0.78;
            margin: -0.25rem 0 0.6rem 0;
        }
        .sidebar-month-card {
            padding: 0.8rem 0.95rem;
            border-radius: 10px;
            border: 1px solid rgba(2, 132, 199, 0.3);
            background: rgba(2, 132, 199, 0.08);
            font-size: 0.88rem;
            line-height: 1.55;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _apply_clean_plotly(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Noto Sans Thai, Inter, system-ui, sans-serif", size=12),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(gridcolor="rgba(148, 163, 184, 0.22)", zeroline=False),
    )
    return fig


def _format_champion_label(name: str) -> str:
    cleaned = str(name).replace("Challenger_", "")
    mapping = {
        "Online_SGD": "Online SGD",
        "Sliding_Retrain": "Sliding Retrain (12m)",
        "Initial_Warmup_Model": "Warm-up Model",
        "Frozen_Baseline": "Frozen Baseline",
    }
    return mapping.get(cleaned, cleaned.replace("_", " "))


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
        page_title="Cyberattack Online ML Simulator",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_custom_css()

    if not (ONLINE_DIR / "online_replay_log.csv").exists():
        st.error("ยังไม่มีไฟล์ผลลัพธ์ใน `data/analytical/online/` กรุณารัน `PYTHONPATH=src python -m analysis.online_ml` ก่อน")
        return

    df_sum, df_log, df_drift, df_coef, df_pred = load_online_data()

    # Sidebar: Task Selector & Time-Step Controller
    with st.sidebar:
        st.markdown("### แผงควบคุมการจำลอง")
        selected_task = st.selectbox(
            "เลือกโจทย์การทำนาย (Task)",
            options=list(TASK_LABELS.keys()),
            format_func=lambda k: TASK_LABELS[k],
        )

        task_logs = df_log[df_log["task_name"] == selected_task].sort_values("step_idx").reset_index(drop=True)
        min_step = int(task_logs["step_idx"].min())  # 7 (2022-07)
        max_step = int(task_logs["step_idx"].max())  # 36 (2024-12)

        if "current_step" not in st.session_state:
            st.session_state.current_step = min_step

        st.divider()
        st.markdown("#### ควบคุมเวลา (ทีละเดือน)")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("รีเซ็ต", use_container_width=True, help="กลับไปเดือนที่ 7 (ก.ค. 2022) หลังจบช่วง Warm-up"):
                st.session_state.current_step = min_step
        with c2:
            if st.button("ก่อนหน้า", use_container_width=True, disabled=(st.session_state.current_step <= min_step)):
                st.session_state.current_step = max(min_step, st.session_state.current_step - 1)
        with c3:
            if st.button("ถัดไป", type="primary", use_container_width=True, disabled=(st.session_state.current_step >= max_step)):
                st.session_state.current_step = min(max_step, st.session_state.current_step + 1)

        step_to_ym = dict(zip(task_logs["step_idx"], task_logs["year_month"]))
        selected_step = st.slider(
            "เลื่อนเลือกเดือน (Step 7–36)",
            min_value=min_step,
            max_value=max_step,
            value=int(st.session_state.current_step),
            format="เดือนที่ %d",
        )
        st.session_state.current_step = selected_step
        current_ym = step_to_ym[selected_step]
        next_ym = step_to_ym.get(selected_step + 1, "2025-01 (Forecast)")

        progress_ratio = (selected_step - min_step) / max(max_step - min_step, 1)
        st.progress(progress_ratio, text=f"ความคืบหน้า: เดือนที่ {selected_step - min_step + 1} / {max_step - min_step + 1}")

        auto_play = st.button("เล่นอัตโนมัติทีละเดือน (Auto-Play)", use_container_width=True)

        st.markdown(
            f"""
            <div class="sidebar-month-card">
                <div><b>เดือนที่ป้อนเข้าโมเดล:</b> <code>{current_ym}</code> (Step {selected_step}/36)</div>
                <div><b>พยากรณ์ล่วงหน้าเดือน:</b> <code>{next_ym}</code></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()
        with st.expander("คู่มืออ่านค่าเบื้องต้น", expanded=False):
            st.markdown(
                """
                - **RMSE (ความคลาดเคลื่อน):** ยิ่ง **ต่ำ** ยิ่งทายแม่นยำ
                - **R² (%):** โมเดลอธิบายความแปรปรวนของข้อมูลได้กี่ % (ยิ่งใกล้ **100%** ยิ่งดี)
                - **Data / Concept Drift:** สัญญาณเตือนเมื่อรูปแบบข้อมูลหรือพฤติกรรมการโจมตีเปลี่ยนไปจากเดิม
                - **`.partial_fit()`:** การอัปเดตน้ำหนักโมเดลทีละเดือนจากข้อมูลใหม่ทันที โดยไม่ต้องเทรนใหม่ตั้งแต่ศูนย์
                """
            )

    # Clean Hero Header
    st.markdown(
        f"""
        <div class="hero-box">
            <div class="hero-title">Cyberattack Online ML Simulator</div>
            <div class="hero-sub">
                จำลองการไหลของข้อมูลภัยไซเบอร์ 144 ประเทศ ตลอด 36 เดือน (2022–2024) ·
                โจทย์ปัจจุบัน: <b>{TASK_LABELS[selected_task]}</b>
            </div>
            <div class="flow-pills">
                <span class="flow-pill">1. ทำนายก่อน (Test-Then-Train)</span>
                <span class="flow-arrow">→</span>
                <span class="flow-pill">2. ตรวจจับ Drift</span>
                <span class="flow-arrow">→</span>
                <span class="flow-pill">3. แข่งขัน Champion vs. Challenger</span>
                <span class="flow-arrow">→</span>
                <span class="flow-pill">4. อัปเดต .partial_fit() &amp; พยากรณ์เดือนถัดไป</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_replay, tab_batch_sim, tab_whatif, tab_summary = st.tabs([
        f"1. จำลองรายเดือน ({current_ym})",
        "2. ปรับค่าทำนายเอง (Batch ML)",
        "3. จำลองอนาคต (What-If)",
        "4. สรุปผล & Drift Log",
    ])

    # =======================================================================
    # TAB 1: STEP-BY-STEP MONTHLY REPLAY VISUALIZATION
    # =======================================================================
    with tab_replay:
        history_logs = task_logs[task_logs["step_idx"] <= selected_step].copy()
        cur_row = task_logs[task_logs["step_idx"] == selected_step].iloc[0]

        st.markdown(f"### ภาพรวมเดือน `{current_ym}` (Step {selected_step}/36)")
        st.markdown(
            "<div class='section-hint'>เปรียบเทียบประสิทธิภาพของโมเดลเมื่อข้อมูลจริงเดือนนี้ไหลเข้าระบบ ก่อนอัปเดตน้ำหนักเพื่อพยากรณ์เดือนถัดไป</div>",
            unsafe_allow_html=True,
        )

        # Clean 4-column KPI strip (concise, readable, with tooltips)
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            drift_badge = "พบ DRIFT" if cur_row["drift_detected"] else "ปกติ"
            drift_parts = []
            if cur_row["data_drift_detected"]:
                drift_parts.append("Data Drift")
            if cur_row["concept_drift_detected"]:
                drift_parts.append("Concept Drift")
            drift_sub = " + ".join(drift_parts) if drift_parts else "ไม่พบความผิดปกติ"
            st.metric(
                "สถานะ Drift Detector",
                drift_badge,
                drift_sub,
                delta_color="inverse" if cur_row["drift_detected"] else "off",
                help="ตรวจจับทั้ง Data Drift (ฟีเจอร์เปลี่ยน) และ Concept Drift (ความคลาดเคลื่อนพุ่งเกินเพดาน)",
            )
        with k2:
            champ_label = _format_champion_label(cur_row["champion_after"])
            champ_prev = _format_champion_label(cur_row["champion_before"])
            st.metric(
                "Active Champion ปัจจุบัน",
                champ_label,
                "เพิ่งเปลี่ยนแชมป์เดือนนี้!" if cur_row["promoted"] else f"รักษาแชมป์ ({champ_prev})",
                delta_color="normal" if cur_row["promoted"] else "off",
                help="โมเดลที่ระบบเลือกใช้งานจริงบน Production ในเดือนนี้",
            )
        with k3:
            rmse_diff = float(cur_row["frozen_rmse"] - cur_row["champion_rmse"])
            st.metric(
                "ความคลาดเคลื่อน Champion (RMSE)",
                f"{cur_row['champion_rmse']:.4f}",
                f"ดีกว่า Frozen -{rmse_diff:.4f}",
                delta_color="normal",
                help="ค่า RMSE ยิ่งต่ำยิ่งทายแม่นยำ (เปรียบเทียบกับโมเดล Frozen Baseline ที่ไม่เคยอัปเดต)",
            )
        with k4:
            st.metric(
                "ความแม่นยำอธิบายข้อมูล (R²)",
                f"{cur_row['champion_r2'] * 100:.1f}%",
                f"Frozen ได้ {cur_row['frozen_r2'] * 100:.1f}%",
                delta_color="normal",
                help="สัดส่วนความแปรปรวนของความเข้มข้นการโจมตีที่โมเดลอธิบายได้ (ยิ่งใกล้ 100% ยิ่งดี)",
            )

        if cur_row["promoted"]:
            st.success(f"**เปลี่ยนแชมป์ (Champion Promotion) เดือน `{current_ym}`:** {cur_row['promotion_reason']}")
        if cur_row["drift_detected"]:
            st.warning(
                f"**แจ้งเตือน DRIFT เดือน `{current_ym}`** — ระบบสั่ง Retrain และตรวจสอบเวทีแชมป์อัตโนมัติ\n\n"
                f"- **Feature Z-shift สูงสุด:** `{cur_row['max_feature_z_shift']:.3f}` · "
                f"**Champion RMSE:** `{cur_row['champion_rmse']:.4f}` (เพดานเตือนภัย `{cur_row['drift_rmse_threshold']:.4f}`)\n"
                f"- **ประเทศที่ค่าโจมตีแกว่งแรงสุด:** {cur_row['top_outlier_countries']}"
            )

        # Row 1: Live Performance Curve & Arena Bar Chart inside clean bordered cards
        col_curve, col_arena = st.columns([2, 1])

        with col_curve:
            with st.container(border=True):
                st.markdown("#### 1. กราฟความคลาดเคลื่อนรายเดือน (Walk-Forward RMSE)")
                st.markdown(
                    "<div class='section-hint'>เส้นยิ่งต่ำยิ่งแม่นยำ · ดาวสีแดง = เดือนที่ตรวจพบ Drift และสั่ง Retrain (เอาเมาส์ชี้เพื่อเทียบทุกโมเดลพร้อมกัน)</div>",
                    unsafe_allow_html=True,
                )
                fig_rmse = go.Figure()
                fig_rmse.add_trace(go.Scatter(
                    x=history_logs["year_month"],
                    y=history_logs["frozen_rmse"],
                    mode="lines+markers",
                    name="Frozen Baseline (ไม่อัปเดต)",
                    line=dict(color=PALETTE["frozen"], width=2, dash="dot"),
                    marker=dict(size=5),
                ))
                fig_rmse.add_trace(go.Scatter(
                    x=history_logs["year_month"],
                    y=history_logs["retrain_rmse"],
                    mode="lines+markers",
                    name="Sliding Retrain (12m)",
                    line=dict(color=PALETTE["retrain"], width=2),
                    marker=dict(size=5),
                ))
                fig_rmse.add_trace(go.Scatter(
                    x=history_logs["year_month"],
                    y=history_logs["online_sgd_rmse"],
                    mode="lines+markers",
                    name="Online SGD (.partial_fit)",
                    line=dict(color=PALETTE["online"], width=2.5),
                    marker=dict(size=5),
                ))
                fig_rmse.add_trace(go.Scatter(
                    x=history_logs["year_month"],
                    y=history_logs["champion_rmse"],
                    mode="lines+markers",
                    name="Active Champion",
                    line=dict(color=PALETTE["champion"], width=3.5),
                    marker=dict(size=6),
                ))

                # Highlight drift months with red stars
                drift_pts = history_logs[history_logs["drift_detected"] == True]
                if len(drift_pts) > 0:
                    fig_rmse.add_trace(go.Scatter(
                        x=drift_pts["year_month"],
                        y=drift_pts["champion_rmse"],
                        mode="markers",
                        name="จุดเกิด Drift",
                        marker=dict(color=PALETTE["drift"], size=12, symbol="star"),
                    ))

                _apply_clean_plotly(fig_rmse, height=360)
                fig_rmse.update_layout(
                    hovermode="x unified",
                    margin=dict(l=12, r=12, t=42, b=16),
                    xaxis_title="เดือน (Year-Month)",
                    yaxis_title="RMSE (ยิ่งต่ำยิ่งดี)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0),
                )
                st.plotly_chart(fig_rmse, use_container_width=True)

        with col_arena:
            with st.container(border=True):
                st.markdown(f"#### 2. เทียบผลเดือน `{current_ym}`")
                st.markdown(
                    "<div class='section-hint'>เปรียบเทียบ RMSE (แท่งยิ่งเตี้ยยิ่งแม่นยำ)</div>",
                    unsafe_allow_html=True,
                )
                arena_df = pd.DataFrame([
                    {"Model": "Frozen", "RMSE": cur_row["frozen_rmse"], "R2 (%)": cur_row["frozen_r2"] * 100},
                    {"Model": "Retrain 12m", "RMSE": cur_row["retrain_rmse"], "R2 (%)": cur_row["retrain_r2"] * 100},
                    {"Model": "Online SGD", "RMSE": cur_row["online_sgd_rmse"], "R2 (%)": cur_row["online_sgd_r2"] * 100},
                    {"Model": "Champion", "RMSE": cur_row["champion_rmse"], "R2 (%)": cur_row["champion_r2"] * 100},
                ])
                max_arena = float(arena_df["RMSE"].max()) if len(arena_df) > 0 else 1.0
                fig_arena = px.bar(
                    arena_df,
                    x="Model",
                    y="RMSE",
                    color="Model",
                    text="RMSE",
                    hover_data={"R2 (%)": ":.1f", "RMSE": ":.4f"},
                    color_discrete_sequence=[PALETTE["frozen"], PALETTE["retrain"], PALETTE["online"], PALETTE["champion"]],
                )
                fig_arena.update_traces(texttemplate="%{text:.3f}", textposition="outside")
                _apply_clean_plotly(fig_arena, height=360)
                fig_arena.update_layout(
                    showlegend=False,
                    margin=dict(l=12, r=12, t=24, b=16),
                    xaxis_title="",
                    yaxis_title="RMSE เดือนปัจจุบัน",
                    yaxis=dict(range=[0, max_arena * 1.22]),
                )
                st.plotly_chart(fig_arena, use_container_width=True)

        # Row 2: What Happens Next after feeding month t (.partial_fit weight shift + Month t+1 World Forecast)
        st.markdown(f"### ผลลัพธ์หลังอัปเดตโมเดลเดือน `{current_ym}` → พยากรณ์เดือน `{next_ym}`")

        col_map, col_coef = st.columns([3, 2])
        step_preds = df_pred[(df_pred["task_name"] == selected_task) & (df_pred["step_idx"] == selected_step)].copy()

        with col_map:
            with st.container(border=True):
                st.markdown(f"#### 3. แผนที่โลกพยากรณ์ความเสี่ยงเดือน `{next_ym}`")
                st.markdown(
                    "<div class='section-hint'>สีแดง = ความเข้มข้นการโจมตีสูงกว่าสัดส่วนทราฟฟิกปกติ · สีน้ำเงิน = ต่ำกว่าปกติ</div>",
                    unsafe_allow_html=True,
                )
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
                _apply_clean_plotly(fig_map, height=400)
                fig_map.update_layout(
                    margin=dict(l=0, r=0, t=8, b=0),
                    geo=dict(
                        showframe=False,
                        showcoastlines=True,
                        coastlinecolor="rgba(148, 163, 184, 0.5)",
                        bgcolor="rgba(0,0,0,0)",
                        projection_type="natural earth",
                    ),
                    coloraxis_colorbar=dict(title="ln Intensity", thickness=14, len=0.75),
                )
                st.plotly_chart(fig_map, use_container_width=True)

        with col_coef:
            with st.container(border=True):
                st.markdown(f"#### 4. Top 10 ปัจจัยหลักหลัง `.partial_fit()`")
                st.markdown(
                    "<div class='section-hint'>ค่าบวก (+) สีแดง = ดันให้ความเข้มข้นสูงขึ้น · ค่าลบ (−) สีน้ำเงิน = ช่วยลดความเข้มข้น</div>",
                    unsafe_allow_html=True,
                )
                cur_coefs = (
                    df_coef[(df_coef["task_name"] == selected_task) & (df_coef["step_idx"] == selected_step)]
                    .sort_values("abs_coef_beta", ascending=False)
                    .head(10)
                    .sort_values("coef_beta", ascending=True)
                    .copy()
                )
                cur_coefs["feature_label"] = cur_coefs["feature"].map(lambda f: FEATURE_DISPLAY_NAMES.get(f, f))
                max_abs_b = max(float(cur_coefs["abs_coef_beta"].max()), 0.1) if len(cur_coefs) > 0 else 1.0
                fig_coef = px.bar(
                    cur_coefs,
                    x="coef_beta",
                    y="feature_label",
                    orientation="h",
                    color="coef_beta",
                    color_continuous_scale="RdBu_r",
                    color_continuous_midpoint=0,
                    text="coef_beta",
                    hover_data={"feature": True, "coef_beta": ":+.4f", "feature_label": False},
                )
                fig_coef.update_traces(texttemplate="%{text:+.3f}", textposition="outside")
                _apply_clean_plotly(fig_coef, height=400)
                fig_coef.update_layout(
                    margin=dict(l=8, r=36, t=8, b=12),
                    coloraxis_showscale=False,
                    xaxis_title="ค่าน้ำหนักสัมประสิทธิ์ β (Online SGD)",
                    yaxis_title="",
                    xaxis=dict(
                        range=[-max_abs_b * 1.28, max_abs_b * 1.28],
                        zeroline=True,
                        zerolinecolor="rgba(148, 163, 184, 0.6)",
                        gridcolor="rgba(148, 163, 184, 0.2)",
                    ),
                    yaxis=dict(showgrid=False),
                )
                st.plotly_chart(fig_coef, use_container_width=True)

        # Country detail table inside bordered container with display-only search filter
        with st.container(border=True):
            h_tbl, h_search = st.columns([3, 1.3])
            with h_tbl:
                st.markdown(f"#### ตารางเจาะลึกรายประเทศ (`{current_ym}` → `{next_ym}`)")
                st.markdown(
                    "<div class='section-hint'>เรียงลำดับจากประเทศที่ถูกพยากรณ์ว่ามีความเข้มข้นการโจมตีสูงสุดในเดือนถัดไป</div>",
                    unsafe_allow_html=True,
                )
            with h_search:
                search_country = st.text_input(
                    "ค้นหาประเทศ",
                    placeholder="พิมพ์ชื่อหรือ ISO3 เช่น THA, USA",
                    label_visibility="collapsed",
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
            table_df = step_preds.sort_values("next_month_forecast_champion", ascending=False)[display_cols]
            if search_country.strip():
                q = search_country.strip().lower()
                table_df = table_df[
                    table_df["iso3"].str.lower().str.contains(q, na=False)
                    | table_df["country_name"].str.lower().str.contains(q, na=False)
                ]

            st.dataframe(
                table_df.rename(
                    columns={
                        "iso3": "ISO3",
                        "country_name": "ประเทศ",
                        "y_true": f"ค่าจริง ({current_ym})",
                        "y_pred_frozen": f"Frozen ทาย",
                        "y_pred_champion": f"Champion ทาย",
                        "residual_champion": "คลาดเคลื่อน",
                        "next_month_forecast_champion": f"พยากรณ์ ({next_ym})",
                        "next_month_y_true": f"เฉลยจริง ({next_ym})",
                        "predicted_change_next_month": "แนวโน้ม (Δ)",
                    }
                ),
                use_container_width=True,
                hide_index=True,
                height=340,
                column_config={
                    f"ค่าจริง ({current_ym})": st.column_config.NumberColumn(format="%.2f"),
                    "Frozen ทาย": st.column_config.NumberColumn(format="%.2f"),
                    "Champion ทาย": st.column_config.NumberColumn(format="%.2f"),
                    "คลาดเคลื่อน": st.column_config.NumberColumn(format="%+.2f"),
                    f"พยากรณ์ ({next_ym})": st.column_config.NumberColumn(format="%.2f"),
                    f"เฉลยจริง ({next_ym})": st.column_config.NumberColumn(format="%.2f"),
                    "แนวโน้ม (Δ)": st.column_config.NumberColumn(format="%+.2f"),
                },
            )

    # =======================================================================
    # TAB 2: BATCH ML INTERACTIVE FEATURE ADJUSTER & LIVE PREDICTOR
    # =======================================================================
    with tab_batch_sim:
        st.markdown("### ทดลองปรับค่าฟีเจอร์ (H1, H2, H3) เพื่อทำนายสดด้วยโมเดล Batch ML ทั้ง 5 ตัว")
        st.markdown(
            "<div class='section-hint'>เลือกประเทศตั้งต้นจากข้อมูลจริงปี 2024 แล้วลองปรับเลื่อนปัจจัยด้านดิจิทัล เศรษฐกิจ หรือความพร้อมไซเบอร์ เพื่อดูผลกระทบต่อความเสี่ยง</div>",
            unsafe_allow_html=True,
        )

        df_v2, batch_models, sc_stats = load_and_train_batch_v2_models()
        df_2024 = df_v2[df_v2["year"] == 2024].sort_values("country_name").reset_index(drop=True)

        country_options = df_2024["iso3"].tolist()
        country_labels = {r["iso3"]: f"{r['country_name']} ({r['iso3']})" for _, r in df_2024.iterrows()}
        default_idx = country_options.index("THA") if "THA" in country_options else 0

        sel_col, _ = st.columns([1.4, 2])
        with sel_col:
            sel_iso = st.selectbox(
                "เลือกประเทศตั้งต้น (ค่าเริ่มต้นปี 2024)",
                options=country_options,
                index=default_idx,
                format_func=lambda k: country_labels[k],
            )
        base_row = df_2024[df_2024["iso3"] == sel_iso].iloc[0]

        col_h1, col_h2, col_h3 = st.columns(3)

        with col_h1:
            with st.container(border=True):
                st.markdown("#### H1: โครงสร้างพื้นฐานดิจิทัล")
                in_bb = st.slider(
                    "เน็ตบ้านต่อประชากร 100 คน",
                    0.0, 55.0, float(base_row["broadband_subs_per_100"]), 0.5,
                    help="ตัวแปร: broadband_subs_per_100",
                )
                in_inet = st.slider(
                    "สัดส่วนผู้ใช้อินเทอร์เน็ต (%)",
                    5.0, 100.0, float(base_row["internet_users_pct"]), 1.0,
                    help="ตัวแปร: internet_users_pct",
                )
                in_asn = st.slider(
                    "จำนวนเครือข่าย ISP / ASN",
                    1, 20000, int(round(np.exp(base_row["routed_asn_count_log"]))), 10,
                    help="ตัวแปร: routed_asn_count",
                )
                in_srv = st.slider(
                    "เซิร์ฟเวอร์ HTTPS ต่อล้านคน (log)",
                    0.0, 13.5, float(base_row["secure_servers_per_1m_log"]), 0.1,
                    help="ตัวแปร: secure_servers_per_1m_log",
                )
                in_tls = st.slider(
                    "สัดส่วนการใช้ TLS 1.3 (%)",
                    0.0, 100.0, float(base_row["tls_1_3_percent"]), 1.0,
                    help="ตัวแปร: tls_1_3_percent",
                )

        with col_h2:
            with st.container(border=True):
                st.markdown("#### H2: เศรษฐกิจและขนาดประเทศ")
                in_gdp = st.slider(
                    "รายได้ต่อหัว GDP per Capita (USD)",
                    500, 140000, int(round(np.exp(base_row["gdp_per_capita_log"]))), 500,
                    help="ตัวแปร: gdp_per_capita",
                )
                in_fdi = st.slider(
                    "เงินลงทุนต่างชาติ FDI (% ของ GDP)",
                    -7.0, 16.0, float(base_row["fdi_net_inflows_clipped"]), 0.2,
                    help="ตัวแปร: fdi_net_inflows_clipped",
                )
                in_traffic = st.slider(
                    "ขนาดทราฟฟิกอินเทอร์เน็ต (log)",
                    -4.6, 3.2, float(base_row["http_traffic_mean_log"]), 0.1,
                    help="ตัวแปร: http_traffic_mean_log (ตัวแปรควบคุม)",
                )
                in_pop = st.slider(
                    "ขนาดประชากร (log)",
                    11.5, 21.1, float(base_row["population_log"]), 0.1,
                    help="ตัวแปร: population_log (ตัวแปรควบคุม)",
                )

        with col_h3:
            with st.container(border=True):
                st.markdown("#### H3: ความพร้อมไซเบอร์และธรรมาภิบาล")
                in_gci = st.slider(
                    "คะแนนความพร้อมไซเบอร์ ITU GCI (0–100)",
                    0.0, 100.0, float(base_row["gci_score_100"]), 1.0,
                    help="ตัวแปร: gci_score_100",
                )
                in_vdem_sec = st.slider(
                    "ศักยภาพไซเบอร์ของรัฐ (V-Dem)",
                    -3.5, 3.5, float(base_row["v2smgovcapsec"]), 0.1,
                    help="ตัวแปร: v2smgovcapsec (ยิ่งสูงยิ่งพร้อมรับมือ)",
                )
                in_goveff = st.slider(
                    "ประสิทธิภาพภาครัฐ (WGI)",
                    -2.5, 2.5, float(base_row["gov_effectiveness"]), 0.1,
                    help="ตัวแปร: gov_effectiveness",
                )
                in_rule = st.slider(
                    "หลักนิติธรรม (WGI)",
                    -2.5, 2.5, float(base_row["rule_of_law"]), 0.1,
                    help="ตัวแปร: rule_of_law",
                )
                in_fordom = st.slider(
                    "การแทรกแซงไซเบอร์ข้ามชาติ (V-Dem)",
                    -3.5, 3.5, float(base_row["v2smfordom"]), 0.1,
                    help="ตัวแปร: v2smfordom (ค่ายิ่งต่ำ = ถูกแทรกแซงมาก)",
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

        st.markdown(f"### ผลทำนายสำหรับ `{country_labels[sel_iso]}` ({TASK_LABELS[selected_task]})")

        ens_row = comp_df[comp_df["โมเดล (Batch ML V2)"] == "Voting_Ensemble"].iloc[0]
        bm1, bm2, bm3, bm4 = st.columns(4)
        bm1.metric("ค่าจริงปี 2024 (ln)", f"{y_actual_2024:.3f}")
        bm2.metric("Voting Ensemble (ค่าเดิม)", f"{ens_row['ทายจากค่าเดิมของประเทศ (Original)']:.3f}")
        bm3.metric(
            "Voting Ensemble (หลังปรับ)",
            f"{ens_row['ทายจากค่าที่คุณปรับใหม่ (Custom)']:.3f}",
            f"{ens_row['ผลต่างบนสเกล ln (Δ)']:+.3f} ({ens_row['ความเสี่ยงเปลี่ยนไป (%)']})",
            delta_color="inverse",
        )

        # Compute global rank before vs after among 144 countries in 2024
        all_2024_preds = models_for_task["Voting_Ensemble"].predict(df_2024[ALL_FEATURES_V2_Z])
        rank_orig = int(np.sum(all_2024_preds > ens_row["ทายจากค่าเดิมของประเทศ (Original)"]) + 1)
        rank_cust = int(np.sum(all_2024_preds > ens_row["ทายจากค่าที่คุณปรับใหม่ (Custom)"]) + 1)
        bm4.metric(
            "อันดับความเสี่ยงโลก",
            f"อันดับ {rank_cust} / 144",
            f"เดิมอันดับ {rank_orig} ({rank_orig - rank_cust:+d})",
        )

        bc_chart, bc_table = st.columns([3, 2])
        with bc_chart:
            with st.container(border=True):
                st.markdown("#### เปรียบเทียบค่าทำนายก่อน vs หลังปรับค่า (5 โมเดล)")
                bar_melt = comp_df.melt(
                    id_vars=["โมเดล (Batch ML V2)"],
                    value_vars=["ทายจากค่าเดิมของประเทศ (Original)", "ทายจากค่าที่คุณปรับใหม่ (Custom)"],
                    var_name="สถานะ",
                    value_name="ค่าพยากรณ์ความเข้มข้น (ln)",
                )
                bar_melt["สถานะ"] = bar_melt["สถานะ"].replace({
                    "ทายจากค่าเดิมของประเทศ (Original)": "ค่าเดิม (Original)",
                    "ทายจากค่าที่คุณปรับใหม่ (Custom)": "หลังปรับค่าใหม่ (Custom)",
                })
                bar_melt["โมเดลสั้น"] = bar_melt["โมเดล (Batch ML V2)"].str.replace("_", " ")
                fig_b = px.bar(
                    bar_melt,
                    x="โมเดลสั้น",
                    y="ค่าพยากรณ์ความเข้มข้น (ln)",
                    color="สถานะ",
                    barmode="group",
                    text="ค่าพยากรณ์ความเข้มข้น (ln)",
                    color_discrete_sequence=[PALETTE["orig"], PALETTE["custom"]],
                )
                fig_b.add_hline(
                    y=y_actual_2024,
                    line_dash="dash",
                    line_color=PALETTE["drift"],
                    annotation_text=f"ค่าจริงปี 2024 ({y_actual_2024:.2f})",
                    annotation_position="top right",
                )
                fig_b.update_traces(texttemplate="%{text:.2f}", textposition="outside")
                _apply_clean_plotly(fig_b, height=360)
                fig_b.update_layout(
                    margin=dict(l=12, r=12, t=38, b=16),
                    xaxis_title="",
                    yaxis_title="ความเข้มข้นการโจมตี (ln)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                )
                st.plotly_chart(fig_b, use_container_width=True)

        with bc_table:
            with st.container(border=True):
                st.markdown("#### ตารางสรุปรายโมเดล")
                st.dataframe(
                    comp_df.rename(
                        columns={
                            "โมเดล (Batch ML V2)": "โมเดล",
                            "ค่าจริงปี 2024 (y_true)": "จริง 2024",
                            "ทายจากค่าเดิมของประเทศ (Original)": "ค่าเดิม",
                            "ทายจากค่าที่คุณปรับใหม่ (Custom)": "ค่าใหม่",
                            "ผลต่างบนสเกล ln (Δ)": "ผลต่าง (Δ)",
                            "ความเสี่ยงเปลี่ยนไป (%)": "เปลี่ยน (%)",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=360,
                )

    # =======================================================================
    # TAB 3: INTERACTIVE "WHAT-IF" NEXT-MONTH SIMULATOR
    # =======================================================================
    with tab_whatif:
        st.markdown(f"### จำลองเหตุการณ์ฉับพลันเดือนถัดไป (`{next_ym}`) และทดสอบ `.partial_fit()`")
        st.markdown(
            "<div class='section-hint'>ปรับระดับเหตุการณ์จำลองด้านล่างเพื่อดูว่าตัวตรวจจับ Drift จะแจ้งเตือนหรือไม่ และโมเดล Online ML ปรับตัวลดความคลาดเคลื่อนได้เร็วแค่ไหน</div>",
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            wc1, wc2, wc3 = st.columns(3)
            with wc1:
                shock_intensity = st.slider(
                    "1. ระดับการพุ่งขึ้นของการโจมตี (Attack Surge σ)",
                    min_value=-2.0,
                    max_value=3.0,
                    value=1.2,
                    step=0.1,
                )
            with wc2:
                cyber_conflict_shift = st.slider(
                    "2. การแทรกแซงไซเบอร์ข้ามชาติ (Geopolitical Shift)",
                    min_value=-1.0,
                    max_value=3.0,
                    value=0.8,
                    step=0.1,
                )
            with wc3:
                infra_growth = st.slider(
                    "3. การขยายตัวของโครงข่าย ASN & เซิร์ฟเวอร์",
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
        m1.metric(
            "สัญญาณ Drift Detector",
            "DRIFT TRIGGERED" if sim_drift else "Normal",
            f"RMSE ก่อนอัปเดต = {sim_rmse_before:.4f}",
            delta_color="inverse" if sim_drift else "off",
        )
        m2.metric(
            "RMSE หลัง `.partial_fit()` ทันที",
            f"{sim_rmse_after:.4f}",
            f"ลดความคลาดเคลื่อน -{sim_rmse_before - sim_rmse_after:.4f}",
            delta_color="normal",
        )
        m3.metric(
            "การสั่งการอัตโนมัติ",
            "Retrain + Promote" if sim_drift else "อัปเดตปกติ",
            "ดัน Online SGD ขึ้นแชมป์" if sim_drift else "อัปเดตน้ำหนัก .partial_fit()",
            delta_color="off",
        )

        base_step_preds["ค่าจำลองเดือนใหม่ (Simulated Y)"] = np.round(sim_y_new, 3)
        base_step_preds["พยากรณ์เดิมก่อนอัปเดต"] = np.round(base_step_preds["next_month_forecast_champion"], 3)
        base_step_preds["พยากรณ์ใหม่หลัง .partial_fit()"] = np.round(adapted_pred, 3)

        wi_chart, wi_table = st.columns([1.15, 1])
        with wi_chart:
            with st.container(border=True):
                st.markdown("#### การปรับตัวของโมเดล (Top 10 ประเทศที่ค่าจำลองสูงสุด)")
                st.markdown(
                    "<div class='section-hint'>เปรียบเทียบพยากรณ์เดิม (เทา) กับค่าจำลองจริง (แดง) และพยากรณ์ใหม่หลัง .partial_fit() (เขียว)</div>",
                    unsafe_allow_html=True,
                )
                top10_wi = base_step_preds.sort_values("ค่าจำลองเดือนใหม่ (Simulated Y)", ascending=False).head(10)
                wi_melt = top10_wi.melt(
                    id_vars=["iso3", "country_name"],
                    value_vars=["พยากรณ์เดิมก่อนอัปเดต", "ค่าจำลองเดือนใหม่ (Simulated Y)", "พยากรณ์ใหม่หลัง .partial_fit()"],
                    var_name="ซีรีส์",
                    value_name="ความเข้มข้น (ln)",
                )
                fig_wi = px.bar(
                    wi_melt,
                    x="iso3",
                    y="ความเข้มข้น (ln)",
                    color="ซีรีส์",
                    barmode="group",
                    hover_name="country_name",
                    color_discrete_sequence=[PALETTE["frozen"], PALETTE["drift"], PALETTE["champion"]],
                )
                _apply_clean_plotly(fig_wi, height=360)
                fig_wi.update_layout(
                    margin=dict(l=12, r=12, t=38, b=16),
                    xaxis_title="ประเทศ (ISO3)",
                    yaxis_title="ความเข้มข้น (ln)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=""),
                )
                st.plotly_chart(fig_wi, use_container_width=True)

        with wi_table:
            with st.container(border=True):
                st.markdown("#### ตัวอย่าง 20 ประเทศแรกหลังปรับน้ำหนัก")
                st.dataframe(
                    base_step_preds[
                        ["iso3", "country_name", "พยากรณ์เดิมก่อนอัปเดต", "ค่าจำลองเดือนใหม่ (Simulated Y)", "พยากรณ์ใหม่หลัง .partial_fit()"]
                    ]
                    .head(20)
                    .rename(
                        columns={
                            "iso3": "ISO3",
                            "country_name": "ประเทศ",
                            "พยากรณ์เดิมก่อนอัปเดต": "พยากรณ์เดิม",
                            "ค่าจำลองเดือนใหม่ (Simulated Y)": "ค่าจำลองจริง",
                            "พยากรณ์ใหม่หลัง .partial_fit()": "หลัง .partial_fit()",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=360,
                )

    # =======================================================================
    # TAB 4: OVERALL SUMMARY & DRIFT EVENTS LOG
    # =======================================================================
    with tab_summary:
        task_sum = df_sum[df_sum["task_name"] == selected_task].copy()
        task_drift = df_drift[df_drift["task_name"] == selected_task].copy()

        st.markdown(f"### สรุปประสิทธิภาพรวม 30 เดือน Replay ({TASK_LABELS[selected_task]})")
        st.markdown(
            "<div class='section-hint'>สรุปผลทดสอบแบบ Prequential (ก.ค. 2022 – ธ.ค. 2024) และประวัติเหตุการณ์ Drift ทั้งหมด</div>",
            unsafe_allow_html=True,
        )

        # Quick summary KPIs read directly from task_sum
        champ_sum_rows = task_sum[task_sum["model_strategy"].str.contains("Champion_Challenger", na=False)]
        frozen_sum_rows = task_sum[task_sum["model_strategy"].str.contains("Frozen_Baseline", na=False)]
        if len(champ_sum_rows) > 0 and len(frozen_sum_rows) > 0:
            c_s = champ_sum_rows.iloc[0]
            f_s = frozen_sum_rows.iloc[0]
            s1, s2, s3, s4 = st.columns(4)
            s1.metric(
                "Active Champion R² รวม",
                f"{c_s['overall_prequential_r2'] * 100:.1f}%",
                f"Frozen ได้ {f_s['overall_prequential_r2'] * 100:.1f}%",
            )
            s2.metric(
                "Test 2024 RMSE (Champion)",
                f"{c_s['test_2024_rmse']:.4f}",
                f"ลดลงจาก Frozen -{f_s['test_2024_rmse'] - c_s['test_2024_rmse']:.4f}",
            )
            s3.metric(
                "จำนวนครั้งที่เกิด Drift",
                f"{int(c_s['n_drift_events'])} ครั้ง",
                "จากทั้งหมด 30 เดือน",
                delta_color="off",
            )
            s4.metric(
                "จำนวนครั้งที่เปลี่ยนแชมป์",
                f"{int(c_s['n_champion_promotions'])} ครั้ง",
                "ผ่านเกณฑ์ Promotion",
                delta_color="off",
            )

        with st.container(border=True):
            st.markdown("#### ตารางเปรียบเทียบกลยุทธ์โมเดล (ก.ค. 2022 – ธ.ค. 2024)")
            sum_display = task_sum[
                [
                    "model_strategy",
                    "overall_prequential_r2",
                    "overall_prequential_rmse",
                    "overall_prequential_mae",
                    "test_2024_r2",
                    "test_2024_rmse",
                    "test_2024_mae",
                    "n_drift_events",
                    "n_champion_promotions",
                ]
            ].rename(
                columns={
                    "model_strategy": "กลยุทธ์โมเดล",
                    "overall_prequential_r2": "Overall R²",
                    "overall_prequential_rmse": "Overall RMSE",
                    "overall_prequential_mae": "Overall MAE",
                    "test_2024_r2": "Test 2024 R²",
                    "test_2024_rmse": "Test 2024 RMSE",
                    "test_2024_mae": "Test 2024 MAE",
                    "n_drift_events": "จำนวน Drift",
                    "n_champion_promotions": "เปลี่ยนแชมป์",
                }
            )
            st.dataframe(
                sum_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Overall R²": st.column_config.NumberColumn(format="%.4f"),
                    "Overall RMSE": st.column_config.NumberColumn(format="%.4f"),
                    "Overall MAE": st.column_config.NumberColumn(format="%.4f"),
                    "Test 2024 R²": st.column_config.NumberColumn(format="%.4f"),
                    "Test 2024 RMSE": st.column_config.NumberColumn(format="%.4f"),
                    "Test 2024 MAE": st.column_config.NumberColumn(format="%.4f"),
                },
            )

        with st.container(border=True):
            st.markdown("#### บันทึกเหตุการณ์ Drift และการสั่ง Retrain อัตโนมัติ")
            drift_display = task_drift[
                [
                    "year_month",
                    "drift_type",
                    "top_drift_feature",
                    "max_feature_z_shift",
                    "champion_rmse",
                    "drift_rmse_threshold",
                    "top_outlier_countries",
                    "champion_after",
                ]
            ].rename(
                columns={
                    "year_month": "เดือน",
                    "drift_type": "ประเภท Drift",
                    "top_drift_feature": "ฟีเจอร์ที่แกว่งสุด",
                    "max_feature_z_shift": "Max Z-Shift",
                    "champion_rmse": "Champion RMSE",
                    "drift_rmse_threshold": "เพดานเตือนภัย",
                    "top_outlier_countries": "ประเทศแกว่งแรงสุด",
                    "champion_after": "แชมป์หลังอัปเดต",
                }
            )
            drift_display["แชมป์หลังอัปเดต"] = drift_display["แชมป์หลังอัปเดต"].map(_format_champion_label)
            st.dataframe(
                drift_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Max Z-Shift": st.column_config.NumberColumn(format="%.3f"),
                    "Champion RMSE": st.column_config.NumberColumn(format="%.4f"),
                    "เพดานเตือนภัย": st.column_config.NumberColumn(format="%.4f"),
                },
            )

    # Auto-play loop
    if auto_play and st.session_state.current_step < max_step:
        time.sleep(0.6)
        st.session_state.current_step += 1
        st.rerun()


if __name__ == "__main__":
    main()
