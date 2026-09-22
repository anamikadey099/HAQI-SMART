"""
Page 1 — Live Monitor.

Auto-refreshes every 60 seconds. Shows per-node AQI gauges, metric
cards (AQI / responsible pollutant / category badge), sub-index
horizontal bar charts, and an anomaly banner when is_anomaly=True.

All colours via get_aqi_colour() using CPCB hex codes only.
"""

from __future__ import annotations

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from dashboard.utils.api import get_latest
from dashboard.utils.charts import build_aqi_gauge, build_sub_index_bar, get_aqi_colour, get_category_colour

st.set_page_config(page_title="Live Monitor | HAQI-SMART", page_icon="📡", layout="wide")

# Auto-refresh every 60 seconds
st_autorefresh(interval=60_000, key="live_monitor_refresh")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: linear-gradient(135deg, #0a0a1a 0%, #0d1117 100%); }
</style>
""", unsafe_allow_html=True)

# Auth guard
if "jwt_token" not in st.session_state:
    st.error("Please log in first. Return to the main page.")
    st.stop()

st.title("📡 Live Air Quality Monitor")
st.caption("Auto-refreshes every 60 seconds | All values use CPCB AQI methodology")

# Fetch latest data
with st.spinner("Fetching latest readings…"):
    nodes = get_latest()

if not nodes:
    st.warning("No sensor nodes found or backend is unavailable.")
    st.stop()

# --- Anomaly banner ---
anomaly_nodes = [
    n["node_name"] for n in nodes
    if n.get("latest") and n["latest"].get("is_anomaly")
]
if anomaly_nodes:
    st.error(
        f"⚠️ **ANOMALY DETECTED** on node(s): {', '.join(anomaly_nodes)}. "
        "High pollution levels detected within the last 30 minutes.",
        icon="🚨",
    )

# --- Node cards ---
cols = st.columns(min(len(nodes), 3))

for idx, node in enumerate(nodes):
    col = cols[idx % len(cols)]
    latest = node.get("latest") or {}
    aqi_val = latest.get("aqi") or 0.0
    category = latest.get("category") or "Unknown"
    responsible = latest.get("responsible_pollutant") or "N/A"
    sub_indices = latest.get("sub_indices") or {}

    colour = get_aqi_colour(aqi_val)
    cat_colour = get_category_colour(category)

    with col:
        # Gauge
        st.plotly_chart(
            build_aqi_gauge(aqi_val, node.get("node_name", "Node")),
            use_container_width=True,
            key=f"gauge_{node.get('node_id', idx)}",
        )

        # Metric cards row
        m1, m2 = st.columns(2)
        with m1:
            st.metric(label="AQI", value=f"{aqi_val:.0f}")
        with m2:
            st.metric(label="Responsible Pollutant", value=responsible.upper())

        # Category badge
        st.markdown(
            f'<span style="background:{cat_colour};color:#000;padding:4px 14px;'
            f'border-radius:20px;font-weight:700;font-size:14px;">'
            f'{category}</span>',
            unsafe_allow_html=True,
        )
        st.markdown("")

        # Sub-index bar chart (only if data available)
        if sub_indices:
            st.plotly_chart(
                build_sub_index_bar(sub_indices, responsible),
                use_container_width=True,
                key=f"bar_{node.get('node_id', idx)}",
            )

        # Node meta
        region = node.get("region") or "Unknown"
        lat = node.get("latitude", 0)
        lon = node.get("longitude", 0)
        ts = (latest.get("timestamp") or "")[:19].replace("T", " ")
        st.caption(f"📍 {region} ({lat:.4f}, {lon:.4f}) | ⏱ {ts}")
        st.divider()
