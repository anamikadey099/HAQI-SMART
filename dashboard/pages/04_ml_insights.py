"""
Page 4 — ML Insights.

Prediction panel with sliders, anomaly detection timeline,
classification probability chart, and ML server health badge in sidebar.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from dashboard.utils.api import get_history, get_latest, get_ml_health, post_classify, post_predict
from dashboard.utils.charts import get_aqi_colour, get_category_colour

st.set_page_config(page_title="ML Insights | HAQI-SMART", page_icon="🤖", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: linear-gradient(135deg, #0a0a1a 0%, #0d1117 100%); }
</style>
""", unsafe_allow_html=True)

if "jwt_token" not in st.session_state:
    st.error("Please log in first.")
    st.stop()

st.title("🤖 ML Insights")

# ML Health in sidebar
with st.sidebar:
    st.subheader("ML Server Health")
    health = get_ml_health()
    ml_status = health.get("ml_server", "unknown")
    if ml_status == "ok":
        st.success("🟢 ML Server: Online")
    else:
        st.error("🔴 ML Server: Offline / Unreachable")

    db_status = health.get("database", "unknown")
    sched_status = health.get("scheduler", "unknown")
    st.info(f"🗄️ DB: {db_status}\n⏱ Scheduler: {sched_status}")

# --- Node selector ---
nodes = get_latest()
node_options = {
    n.get("node_name", str(n.get("node_id", ""))): str(n.get("node_id", ""))
    for n in nodes
}
selected_node_name = st.selectbox("Select Node", list(node_options.keys()))
selected_node_id = node_options.get(selected_node_name, "00000000-0000-0000-0000-000000000000")

col_pred, col_classify = st.columns(2)

# ---- Prediction panel ----
with col_pred:
    st.subheader("🔮 AQI Prediction")
    with st.form("predict_form"):
        pm25 = st.slider("PM2.5 (µg/m³)", 0.0, 500.0, 65.0)
        pm10 = st.slider("PM10 (µg/m³)", 0.0, 600.0, 120.0)
        temp = st.slider("Temperature (°C)", -10.0, 50.0, 30.0)
        humidity = st.slider("Humidity (%)", 0.0, 100.0, 60.0)
        no2 = st.slider("NO₂ (µg/m³)", 0.0, 400.0, 40.0)
        co = st.slider("CO (mg/m³)", 0.0, 34.0, 1.5)

        predict_submitted = st.form_submit_button("🚀 Predict AQI", use_container_width=True)

    if predict_submitted:
        with st.spinner("Requesting prediction…"):
            pred = post_predict(
                node_id=selected_node_id,
                pm25=pm25, pm10=pm10,
                temperature=temp, humidity=humidity,
                no2=no2, co=co,
            )
        if pred:
            predicted_aqi = pred.get("predicted_aqi", 0)
            confidence = pred.get("confidence", 0)
            category = pred.get("category", "Unknown")
            colour = get_aqi_colour(predicted_aqi)
            cat_colour = get_category_colour(category)

            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);
                        border-radius:12px;padding:20px;text-align:center;margin-top:12px;">
                <div style="font-size:3rem;font-weight:700;color:{colour}">{predicted_aqi:.0f}</div>
                <div style="font-size:1rem;color:#BDC1C6;">Predicted AQI</div>
                <span style="background:{cat_colour};color:#000;padding:4px 14px;
                             border-radius:20px;font-weight:700;">{category}</span><br/><br/>
                <div style="color:#BDC1C6;">Confidence: <b>{confidence:.1%}</b></div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("ML server unavailable. Prediction could not be retrieved.")

# ---- Classification panel ----
with col_classify:
    st.subheader("📊 AQI Classification")
    if st.button("Classify Current Readings", use_container_width=True):
        readings = {
            "pm25": pm25 if "pm25" in dir() else 65.0,
            "pm10": pm10 if "pm10" in dir() else 120.0,
        }
        with st.spinner("Classifying…"):
            cls_result = post_classify(node_id=selected_node_id, readings=readings)

        if cls_result:
            probs = cls_result.get("probabilities", {})
            if probs:
                categories = list(probs.keys())
                values = list(probs.values())
                colours = [get_category_colour(c) for c in categories]

                fig_cls = go.Figure(go.Bar(
                    x=values, y=categories,
                    orientation="h",
                    marker_color=colours,
                    text=[f"{v:.1%}" for v in values],
                    textposition="auto",
                ))
                fig_cls.update_layout(
                    title="Category Probabilities",
                    xaxis=dict(title="Probability", range=[0, 1]),
                    height=300,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(16,16,32,0.5)",
                    font={"color": "white"},
                )
                st.plotly_chart(fig_cls, use_container_width=True)

            st.info(f"Top Category: **{cls_result.get('category', 'N/A')}**")
        else:
            st.warning("ML classification unavailable.")

# ---- Anomaly timeline ----
st.subheader("🚨 Anomaly Timeline")
with st.spinner("Loading anomaly history…"):
    history = get_history(page_size=200)
    items = history.get("items", []) if isinstance(history, dict) else []

anomalies = [r for r in items if r.get("is_anomaly")]

if anomalies:
    for record in anomalies[:20]:
        score = record.get("anomaly_score") or 0.0
        ts = (record.get("timestamp") or "")[:19].replace("T", " ")
        nid = str(record.get("node_id", ""))[:8]
        aqi_val = record.get("aqi") or 0.0
        colour = get_aqi_colour(aqi_val)

        # Heatmap colour for anomaly score
        alpha = min(int(score * 255), 255)
        heat_colour = f"rgba(255,0,0,{score:.2f})"

        st.markdown(f"""
        <div style="background:{heat_colour};border-radius:8px;padding:10px 16px;
                    margin-bottom:8px;border:1px solid rgba(255,0,0,0.3);">
            ⚠️ <b>{ts}</b> — Node <code>{nid}</code>
            AQI: <span style="color:{colour};font-weight:700">{aqi_val:.0f}</span>
            | Score: <b>{score:.3f}</b>
        </div>
        """, unsafe_allow_html=True)
else:
    st.success("✅ No anomalies detected in recent history.")
