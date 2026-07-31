"""
Page 3 — Hotspot Map.

Folium map with CPCB-coloured circle markers per node (radius
proportional to AQI) and hotspot polygon overlays. Sidebar table
of active hotspots with severity, detection time, and resolution status.
"""

from __future__ import annotations

import folium
import streamlit as st
from streamlit_folium import st_folium

from dashboard.utils.api import get_hotspots, get_latest
from dashboard.utils.charts import get_aqi_colour

st.set_page_config(page_title="Hotspot Map | HAQI-SMART", page_icon="🗺️", layout="wide")

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

st.title("🗺️ Hotspot Map")

col_map, col_table = st.columns([2, 1])

with st.spinner("Loading map data…"):
    nodes = get_latest()
    hotspots = get_hotspots()

# Default map centre (India)
default_lat, default_lon = 20.5937, 78.9629
if nodes:
    default_lat = sum(n.get("latitude", 0) for n in nodes) / len(nodes)
    default_lon = sum(n.get("longitude", 0) for n in nodes) / len(nodes)

m = folium.Map(
    location=[default_lat, default_lon],
    zoom_start=6,
    tiles="CartoDB dark_matter",
)

# --- Node circle markers ---
for node in nodes:
    lat = node.get("latitude", 0)
    lon = node.get("longitude", 0)
    latest = node.get("latest") or {}
    aqi_val = latest.get("aqi") or 0.0
    category = latest.get("category") or "Unknown"
    responsible = latest.get("responsible_pollutant") or "N/A"
    colour = get_aqi_colour(aqi_val)

    # Radius proportional to AQI (10–50km visual range)
    radius = max(10_000, min(50_000, int(aqi_val * 100)))

    popup_html = f"""
    <div style="font-family:Inter,sans-serif;min-width:180px;">
        <b>{node.get('node_name','Node')}</b><br/>
        AQI: <b style="color:{colour}">{aqi_val:.0f}</b><br/>
        Category: {category}<br/>
        Responsible: {responsible.upper()}<br/>
        Region: {node.get('region','—')}
    </div>
    """

    folium.Circle(
        location=[lat, lon],
        radius=radius,
        color=colour,
        fill=True,
        fill_color=colour,
        fill_opacity=0.35,
        popup=folium.Popup(popup_html, max_width=220),
        tooltip=f"{node.get('node_name','Node')} — AQI {aqi_val:.0f}",
    ).add_to(m)

    folium.CircleMarker(
        location=[lat, lon],
        radius=8,
        color=colour,
        fill=True,
        fill_color=colour,
        fill_opacity=0.9,
    ).add_to(m)

# --- Hotspot polygons ---
for hs in hotspots:
    c_lat = hs.get("centroid_lat")
    c_lon = hs.get("centroid_lon")
    radius_km = hs.get("radius_km") or 5.0
    severity = hs.get("severity") or "Unknown"
    aqi_hs = hs.get("aqi_at_detection") or 250.0

    if c_lat and c_lon:
        folium.Circle(
            location=[c_lat, c_lon],
            radius=radius_km * 1000,
            color="#FF0000",
            fill=False,
            weight=3,
            dash_array="10",
            popup=folium.Popup(
                f"<b>HOTSPOT</b><br/>Severity: {severity}<br/>AQI: {aqi_hs:.0f}",
                max_width=160,
            ),
            tooltip=f"Hotspot ({severity})",
        ).add_to(m)

        folium.Marker(
            location=[c_lat, c_lon],
            icon=folium.DivIcon(
                html=f'<div style="font-size:12px;font-weight:700;color:#FF0000;'
                     f'background:rgba(0,0,0,0.7);padding:2px 6px;border-radius:4px;">'
                     f'🔴 {severity}</div>'
            ),
        ).add_to(m)

with col_map:
    st_folium(m, use_container_width=True, height=550)

with col_table:
    st.subheader("Active Hotspots")
    if hotspots:
        for hs in hotspots:
            severity = hs.get("severity") or "Unknown"
            aqi_hs = hs.get("aqi_at_detection") or 0
            detected = (hs.get("detected_at") or "")[:19].replace("T", " ")
            node_ids = hs.get("node_ids") or []
            colour = get_aqi_colour(aqi_hs)

            st.markdown(f"""
            <div style="background:rgba(255,0,0,0.1);border:1px solid #FF0000;
                        border-radius:8px;padding:12px;margin-bottom:10px;">
                <b style="color:#FF0000">⚠ {severity}</b><br/>
                AQI: <b style="color:{colour}">{aqi_hs:.0f}</b><br/>
                Detected: {detected}<br/>
                Nodes: {len(node_ids)}<br/>
                Resolved: {'Yes' if hs.get('resolved_at') else 'No'}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ No active hotspots detected.")

    # Node legend
    st.subheader("Node Status")
    for node in nodes:
        latest = node.get("latest") or {}
        aqi_val = latest.get("aqi") or 0
        colour = get_aqi_colour(aqi_val)
        st.markdown(
            f'<span style="display:inline-block;width:12px;height:12px;'
            f'border-radius:50%;background:{colour};margin-right:6px;"></span>'
            f'{node.get("node_name","Node")} — AQI {aqi_val:.0f}',
            unsafe_allow_html=True,
        )
