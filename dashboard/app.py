"""
HAQI-SMART Streamlit dashboard entrypoint.

Provides the login form, JWT token management (stored in
``st.session_state``), and sidebar navigation to all 5 pages.
"""

from __future__ import annotations

import streamlit as st
from dashboard.utils import api

st.set_page_config(
    page_title="HAQI-SMART | Air Quality Monitor",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Custom CSS ----
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main {
        background: linear-gradient(135deg, #0a0a1a 0%, #0d1117 50%, #0a0a1a 100%);
    }

    .stApp {
        background: linear-gradient(135deg, #0a0a1a 0%, #0d1117 100%);
    }

    .metric-card {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 16px;
        backdrop-filter: blur(10px);
    }

    .aqi-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 14px;
    }

    h1, h2, h3 { color: #E8EAED; }
    p { color: #BDC1C6; }

    .stSidebar {
        background: rgba(13, 17, 23, 0.95) !important;
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    .login-container {
        max-width: 400px;
        margin: 80px auto;
        padding: 40px;
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        backdrop-filter: blur(20px);
    }
</style>
""", unsafe_allow_html=True)


def show_login() -> None:
    """Render the JWT login form and handle authentication."""
    st.markdown("""
    <div style="text-align:center; padding: 40px 0 20px;">
        <h1 style="font-size:2.5rem; background: linear-gradient(90deg, #00B050, #92D050);
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            🌫️ HAQI-SMART
        </h1>
        <p style="color:#BDC1C6; font-size:1.1rem;">Real-time Air Quality Intelligence</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.subheader("Sign In")
            username = st.text_input("Username", placeholder="admin or viewer")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                token = api.login(username, password)
                if token:
                    st.session_state["jwt_token"] = token
                    st.session_state["username"] = username
                    st.rerun()
                else:
                    st.error("Invalid credentials. Try admin/admin123 or viewer/viewer123")


def show_sidebar() -> None:
    """Render the authenticated sidebar with navigation and ML health."""
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding:20px 0 10px;">
            <span style="font-size:2rem;">🌫️</span><br/>
            <strong style="font-size:1.2rem; color:#E8EAED;">HAQI-SMART</strong>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # ML Health badge
        health = api.get_ml_health()
        ml_status = health.get("ml_server", "unknown")
        db_status = health.get("database", "unknown")
        sched_status = health.get("scheduler", "unknown")

        ml_dot = "🟢" if ml_status == "ok" else "🔴"
        db_dot = "🟢" if db_status == "ok" else "🔴"
        sched_dot = "🟢" if sched_status == "running" else "🟡"

        st.markdown(f"""
        **System Status**
        {db_dot} Database: `{db_status}`
        {ml_dot} ML Server: `{ml_status}`
        {sched_dot} Scheduler: `{sched_status}`
        """)
        st.markdown("---")

        user = st.session_state.get("username", "User")
        st.markdown(f"👤 Logged in as **{user}**")

        if st.button("🚪 Logout", use_container_width=True):
            for key in ["jwt_token", "username"]:
                st.session_state.pop(key, None)
            st.rerun()


# ---- Main entrypoint ----
if "jwt_token" not in st.session_state:
    show_login()
else:
    show_sidebar()
    st.markdown("""
    <div style="text-align:center; padding: 60px 0;">
        <h1>🌫️ HAQI-SMART Dashboard</h1>
        <p style="color:#BDC1C6; font-size:1.1rem;">
            Use the sidebar pages to navigate to Live Monitor, AQI Trends,
            Hotspot Map, ML Insights, or Data Export.
        </p>
    </div>
    """, unsafe_allow_html=True)
