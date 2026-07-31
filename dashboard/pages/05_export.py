"""
Page 5 — Data Export.

Date-range picker, node selector, pollutant checkboxes, preview of
first 100 rows, and CSV download button via GET /history?format=csv.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from dashboard.utils.api import get_history, get_latest

st.set_page_config(page_title="Export | HAQI-SMART", page_icon="💾", layout="wide")

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

st.title("💾 Data Export")
st.caption("Export raw AQI readings as CSV for offline analysis.")

# --- Filters ---
with st.sidebar:
    st.header("Export Filters")

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(hours=24)

    start_date = st.date_input("Start Date", value=start_dt.date())
    end_date = st.date_input("End Date", value=end_dt.date())

    nodes_data = get_latest()
    node_options: dict[str, str] = {"All Nodes": ""}
    for n in nodes_data:
        name = n.get("node_name") or str(n.get("node_id", ""))
        node_options[name] = str(n.get("node_id", ""))

    selected_node_name = st.selectbox("Node", list(node_options.keys()))
    selected_node_id = node_options.get(selected_node_name, "") or None

    all_pollutants = ["pm25", "pm10", "no2", "so2", "co", "o3", "nh3"]
    st.markdown("**Pollutant Columns**")
    selected_pollutants = [
        p for p in all_pollutants
        if st.checkbox(p.upper(), value=True, key=f"poll_{p}")
    ]

start_str = f"{start_date}T00:00:00Z"
end_str = f"{end_date}T23:59:59Z"

# --- Preview ---
st.subheader("Preview (first 100 rows)")
with st.spinner("Loading preview…"):
    preview_data = get_history(
        start=start_str,
        end=end_str,
        node_id=selected_node_id,
        page=1,
        page_size=100,
    )
    items = preview_data.get("items", []) if isinstance(preview_data, dict) else []

if items:
    df_preview = pd.DataFrame(items)

    # Keep only selected pollutant columns + metadata
    meta_cols = ["node_id", "timestamp", "aqi", "aqi_category", "responsible_pollutant", "is_anomaly"]
    display_cols = meta_cols + [p for p in selected_pollutants if p in df_preview.columns]
    df_preview = df_preview[[c for c in display_cols if c in df_preview.columns]]

    st.dataframe(df_preview, use_container_width=True, height=400)
    st.caption(f"Showing {len(df_preview)} of {preview_data.get('total', '?')} total records")
else:
    st.info("No data found for the selected filters.")
    df_preview = pd.DataFrame()

# --- CSV Download ---
st.subheader("Download CSV")
col1, col2 = st.columns([1, 2])

with col1:
    if st.button("📥 Prepare CSV Download", use_container_width=True, type="primary"):
        with st.spinner("Fetching full dataset as CSV…"):
            csv_bytes = get_history(
                start=start_str,
                end=end_str,
                node_id=selected_node_id,
                fmt="csv",
            )

        if csv_bytes:
            st.download_button(
                label="⬇️ Download haqi_export.csv",
                data=csv_bytes,
                file_name=f"haqi_export_{start_date}_{end_date}.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.success("CSV ready for download!")
        else:
            st.error("Failed to fetch CSV from backend.")

with col2:
    total = preview_data.get("total", 0) if isinstance(preview_data, dict) else 0
    st.info(
        f"ℹ️ **Export Info**\n\n"
        f"- Date range: {start_date} → {end_date}\n"
        f"- Node: {selected_node_name}\n"
        f"- Pollutants: {', '.join(p.upper() for p in selected_pollutants)}\n"
        f"- Estimated rows: {total:,}"
    )
