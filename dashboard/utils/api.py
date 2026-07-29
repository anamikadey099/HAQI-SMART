"""
Backend API client for the Streamlit dashboard.

ALL backend communication goes through this module via HTTP only.
Direct imports of ``app/`` modules are strictly prohibited (Hard Rule #8).

Functions are wrapped with ``st.cache_data(ttl=30)`` for performance.
``BACKEND_URL`` is read from the ``BACKEND_URL`` environment variable.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

import requests
import streamlit as st

BACKEND_URL: str = os.environ.get("BACKEND_URL", "http://localhost:8000")


def _get_token() -> Optional[str]:
    """Retrieve the JWT token from Streamlit session state.

    Returns:
        JWT token string, or ``None`` if not logged in.
    """
    return st.session_state.get("jwt_token")


def _auth_headers() -> dict[str, str]:
    """Build Authorization headers for JWT-protected endpoints.

    Returns:
        Headers dict with Bearer token.
    """
    token = _get_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


@st.cache_data(ttl=30)
def get_latest() -> list[dict[str, Any]]:
    """Fetch the latest AQI for all active nodes.

    Returns:
        List of node AQI summary dicts, or empty list on error.
    """
    try:
        resp = requests.get(
            f"{BACKEND_URL}/latest",
            headers=_auth_headers(),
            timeout=10,
        )
        if resp.ok:
            envelope = resp.json()
            return envelope.get("data", []) or []
    except Exception:
        pass
    return []


@st.cache_data(ttl=30)
def get_node(node_id: str) -> Optional[dict[str, Any]]:
    """Fetch the latest AQI breakdown for a specific node.

    Args:
        node_id: UUID string of the sensor node.

    Returns:
        AQI response dict, or ``None`` on error.
    """
    try:
        resp = requests.get(
            f"{BACKEND_URL}/node/{node_id}",
            headers=_auth_headers(),
            timeout=10,
        )
        if resp.ok:
            return resp.json().get("data")
    except Exception:
        pass
    return None


@st.cache_data(ttl=30)
def get_aggregation(
    node_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Fetch 5-minute aggregation statistics.

    Args:
        node_id: Optional node UUID filter.

    Returns:
        List of aggregation dicts.
    """
    params: dict[str, str] = {}
    if node_id:
        params["node_id"] = node_id
    try:
        resp = requests.get(
            f"{BACKEND_URL}/aggregation",
            headers=_auth_headers(),
            params=params,
            timeout=10,
        )
        if resp.ok:
            return resp.json().get("data", []) or []
    except Exception:
        pass
    return []


@st.cache_data(ttl=30)
def get_history(
    start: Optional[str] = None,
    end: Optional[str] = None,
    node_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
    fmt: str = "json",
) -> Any:
    """Fetch historical AQI readings.

    Args:
        start: ISO-8601 start datetime string.
        end: ISO-8601 end datetime string.
        node_id: Optional node UUID filter.
        page: Page number.
        page_size: Items per page.
        fmt: ``'json'`` or ``'csv'``.

    Returns:
        Paginated result dict (JSON) or raw CSV bytes.
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size, "format": fmt}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    if node_id:
        params["node_id"] = node_id

    try:
        resp = requests.get(
            f"{BACKEND_URL}/history",
            headers=_auth_headers(),
            params=params,
            timeout=30,
        )
        if resp.ok:
            if fmt == "csv":
                return resp.content
            return resp.json().get("data", {})
    except Exception:
        pass
    return {} if fmt == "json" else b""


def post_predict(
    node_id: str,
    pm25: float,
    pm10: float,
    temperature: Optional[float] = None,
    humidity: Optional[float] = None,
    no2: Optional[float] = None,
    so2: Optional[float] = None,
    co: Optional[float] = None,
    o3: Optional[float] = None,
    nh3: Optional[float] = None,
) -> Optional[dict[str, Any]]:
    """Request an AQI prediction from the ML server.

    Args:
        node_id: UUID string of the sensor node.
        pm25: PM2.5 in µg/m³.
        pm10: PM10 in µg/m³.
        temperature: Temperature in °C (optional).
        humidity: Humidity in % (optional).
        no2: NO₂ in µg/m³ (optional).
        so2: SO₂ in µg/m³ (optional).
        co: CO in mg/m³ (optional).
        o3: O₃ in µg/m³ (optional).
        nh3: NH₃ in µg/m³ (optional).

    Returns:
        Prediction result dict, or ``None`` on error.
    """
    try:
        resp = requests.post(
            f"{BACKEND_URL}/predict",
            headers=_auth_headers(),
            json={
                "node_id": node_id,
                "pm25": pm25, "pm10": pm10,
                "temperature": temperature, "humidity": humidity,
                "no2": no2, "so2": so2, "co": co, "o3": o3, "nh3": nh3,
            },
            timeout=15,
        )
        if resp.ok:
            return resp.json().get("data")
    except Exception:
        pass
    return None


@st.cache_data(ttl=30)
def get_hotspots() -> list[dict[str, Any]]:
    """Fetch active pollution hotspots.

    Returns:
        List of active hotspot dicts.
    """
    try:
        resp = requests.get(
            f"{BACKEND_URL}/hotspots",
            headers=_auth_headers(),
            timeout=10,
        )
        if resp.ok:
            return resp.json().get("data", []) or []
    except Exception:
        pass
    return []


@st.cache_data(ttl=60)
def get_ml_health() -> dict[str, Any]:
    """Check ML server health via the backend health endpoint.

    Returns:
        Health status dict with keys ``database``, ``ml_server``, ``scheduler``.
    """
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if resp.ok:
            return resp.json().get("data", {})
    except Exception:
        pass
    return {"database": "unknown", "ml_server": "unknown", "scheduler": "unknown"}


def post_classify(
    node_id: str,
    readings: dict[str, float],
) -> Optional[dict[str, Any]]:
    """Request AQI category classification from the ML server.

    Args:
        node_id: UUID string of the sensor node.
        readings: Dict of pollutant → concentration.

    Returns:
        Classification result with ``category`` and ``probabilities``, or ``None``.
    """
    try:
        resp = requests.post(
            f"{BACKEND_URL}/classify",
            headers=_auth_headers(),
            json={"node_id": node_id, "readings": readings},
            timeout=15,
        )
        if resp.ok:
            return resp.json().get("data")
    except Exception:
        pass
    return None


def login(username: str, password: str) -> Optional[str]:
    """Authenticate and obtain a JWT token.

    Args:
        username: Dashboard username.
        password: Plaintext password.

    Returns:
        JWT token string on success, or ``None`` on failure.
    """
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/token",
            params={"username": username, "password": password},
            timeout=10,
        )
        if resp.ok:
            return resp.json().get("access_token")
    except Exception:
        pass
    return None
