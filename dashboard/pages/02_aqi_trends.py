"""
Page 2 — AQI Trends.

Date-range selector, multi-node selector, Plotly time-series with
CPCB category band overlays, tabbed pollutant sub-plots, and a
5-minute aggregated mean/median/IQR overlay.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils.api import get_aggregation, get_history, get_latest
from dashboard.utils.charts import build_aqi_timeseries, get_aqi_colour

st.set_page_config(page_title="AQI Trends | HAQI-SMART", page_icon="📈", layout="wide")

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

st.title("📈 AQI Trends")

# --- Filters sidebar ---
with st.sidebar:
    st.header("Filters")
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(hours=24)

    start_date = st.date_input("Start Date", value=start_dt.date())
    end_date = st.date_input("End Date", value=end_dt.date())
    start_str = f"{start_date}T00:00:00Z"
    end_str = f"{end_date}T23:59:59Z"

    # Node multi-select
    nodes_data = get_latest()
    node_options = {
        n.get("node_name", str(n.get("node_id", ""))): str(n.get("node_id", ""))
        for n in nodes_data
    }
    selected_names = st.multiselect("Nodes", list(node_options.keys()), default=list(node_options.keys())[:3])
    selected_ids = [node_options[n] for n in selected_names if n in node_options]

# --- Fetch history ---
with st.spinner("Loading history…"):
    hist = get_history(start=start_str, end=end_str, page_size=500)
    items = hist.get("items", []) if isinstance(hist, dict) else []

if not items:
    st.info("No historical data found for the selected filters.")
    st.stop()

df = pd.DataFrame(items)
if "timestamp" in df.columns:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
if "node_id" in df.columns:
    df["node_id"] = df["node_id"].astype(str)

# Filter to selected nodes
if selected_ids:
    df = df[df["node_id"].isin(selected_ids)]

if df.empty:
    st.warning("No data for selected nodes in this date range.")
    st.stop()

# --- Main AQI time series ---
st.subheader("AQI Over Time")
fig_ts = build_aqi_timeseries(df, selected_ids if selected_ids else None)
st.plotly_chart(fig_ts, use_container_width=True)

# --- Aggregation overlay ---
st.subheader("5-Minute Aggregated Statistics")
agg_rows: list[dict] = []
for nid in (selected_ids or []):
    agg_rows.extend(get_aggregation(node_id=nid))

if agg_rows:
    agg_df = pd.DataFrame(agg_rows)
    agg_df["window_end"] = pd.to_datetime(agg_df["window_end"])

    fig_agg = go.Figure()
    for node_id, grp in agg_df.groupby("node_id"):
        colour = get_aqi_colour(grp["aqi_mean"].mean() or 0)
        fig_agg.add_trace(go.Scatter(
            x=grp["window_end"], y=grp["aqi_mean"],
            name=f"{str(node_id)[:8]} mean", line=dict(color=colour, width=2),
        ))
        fig_agg.add_trace(go.Scatter(
            x=grp["window_end"], y=grp["aqi_median"],
            name=f"{str(node_id)[:8]} median", line=dict(color=colour, width=1, dash="dot"),
        ))
        # IQR shaded band
        if "aqi_iqr" in grp.columns:
            upper = grp["aqi_mean"] + grp["aqi_iqr"] / 2
            lower = grp["aqi_mean"] - grp["aqi_iqr"] / 2
            fig_agg.add_trace(go.Scatter(
                x=pd.concat([grp["window_end"], grp["window_end"][::-1]]),
                y=pd.concat([upper, lower[::-1]]),
                fill="toself", fillcolor=colour,
                opacity=0.15, line=dict(width=0),
                name=f"{str(node_id)[:8]} IQR band", showlegend=False,
            ))

    fig_agg.update_layout(
        height=350, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16,16,32,0.5)", font={"color": "white"},
        xaxis_title="Time", yaxis_title="AQI",
    )
    st.plotly_chart(fig_agg, use_container_width=True)

# --- Pollutant sub-plots (tabbed) ---
st.subheader("Pollutant Breakdown")
pollutants = ["pm25", "pm10", "no2", "so2", "co", "o3"]
available = [p for p in pollutants if p in df.columns and df[p].notna().any()]

if available:
    tabs = st.tabs([p.upper() for p in available])
    for tab, pollutant in zip(tabs, available):
        with tab:
            fig_p = go.Figure()
            for nid, grp in df.groupby("node_id"):
                colour = get_aqi_colour(50)
                fig_p.add_trace(go.Scatter(
                    x=grp["timestamp"], y=grp[pollutant],
                    name=nid[:8], mode="lines",
                    line=dict(width=2),
                ))
            unit = "mg/m³" if pollutant == "co" else "µg/m³"
            fig_p.update_layout(
                height=300,
                yaxis_title=f"{pollutant.upper()} ({unit})",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(16,16,32,0.5)",
                font={"color": "white"},
            )
            st.plotly_chart(fig_p, use_container_width=True)
