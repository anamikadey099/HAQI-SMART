import streamlit as st
import pandas as pd

st.title("AQI & Smoke Detection Frontend")

# -------------------
# Login Section
# -------------------
st.header("Login Page")
username = st.text_input("Enter Username")
password = st.text_input("Enter Password", type="password")

# Flag to check login
login_success = False

if st.button("Login"):
    if username == "admin" and password == "1234":
        st.success("Login Successful ✅")
        login_success = True
    else:
        st.error("Invalid Username or Password ❌")

# -------------------
# Dashboard Section (only after login)
# -------------------
if login_success:
    st.header("📊 Dashboard")

    # Current AQI
    aqi = 120
    st.metric("Current AQI", aqi)

    # Smoke Status
    smoke = True
    if smoke:
        st.warning("🚨 Smoke Detected!")
    else:
        st.success("✅ No Smoke")

    # Accuracy
    accuracy = 0.92
    st.metric("Model Accuracy", f"{accuracy*100:.2f}%")

    # Reports Table
    data = {
        "Date": ["2026-06-27", "2026-06-26"],
        "Time": ["21:30", "18:10"],
        "Status": ["Smoke detected", "Normal"]
    }
    df = pd.DataFrame(data)
    st.table(df)
