"""
ML HTTP client — HAQI-SMART's only interface to ML microservices.

Implements retry logic with exponential backoff for all ML endpoints.
Returns ``None`` on failure (graceful degradation — never raises 500s).

CRITICAL: This file MUST NOT import sklearn, joblib, torch, or any ML library.
All ML is performed by external services accessed via HTTP only.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_BACKOFF = 1.0  # seconds


async def _call_ml(
    endpoint: str,
    payload: dict[str, Any],
    method: str = "POST",
) -> Optional[dict[str, Any]]:
    """Core ML HTTP client with retry and exponential backoff.

    Retries up to 3 times with backoff of 1s, 2s, 4s. Returns ``None``
    on all failures — callers must handle ``None`` gracefully.

    Args:
        endpoint: Path relative to ``ML_SERVER_URL`` (e.g. ``'/ml/predict'``).
        payload: JSON-serialisable request body.
        method: HTTP method (``'POST'`` or ``'GET'``).

    Returns:
        Parsed JSON response dict, or ``None`` if all retries failed.
    """
    url = f"{settings.ML_SERVER_URL}{endpoint}"

    for attempt in range(_MAX_RETRIES):
        t_start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=3.0)
            ) as client:
                if method.upper() == "GET":
                    response = await client.get(url)
                else:
                    response = await client.post(url, json=payload)

                response.raise_for_status()
                elapsed = time.monotonic() - t_start

                # Record histogram metric
                try:
                    from app.middleware.metrics import haqi_ml_call_duration_seconds
                    haqi_ml_call_duration_seconds.labels(endpoint=endpoint).observe(elapsed)
                except ImportError:
                    pass

                return response.json()

        except httpx.HTTPError as exc:
            logger.warning(
                "ML request failed (attempt %d/%d) endpoint=%s error=%s",
                attempt + 1,
                _MAX_RETRIES,
                endpoint,
                exc,
            )
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_BASE_BACKOFF * (2 ** attempt))

    logger.error("ML server unreachable after %d retries: %s", _MAX_RETRIES, endpoint)
    return None


# ---------------------------------------------------------------------------
# Public wrapper functions — one per ML endpoint
# ---------------------------------------------------------------------------


async def predict(
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
    """Request an AQI forecast from the ML prediction service.

    Args:
        node_id: UUID string of the sensor node.
        pm25: PM2.5 concentration in µg/m³.
        pm10: PM10 concentration in µg/m³.
        temperature: Optional temperature in °C.
        humidity: Optional humidity in %.
        no2: Optional NO₂ in µg/m³.
        so2: Optional SO₂ in µg/m³.
        co: Optional CO in **mg/m³**.
        o3: Optional O₃ in µg/m³.
        nh3: Optional NH₃ in µg/m³.

    Returns:
        Dict with keys ``predicted_aqi``, ``confidence``, ``category``,
        or ``None`` if the ML server is unreachable.
    """
    return await _call_ml(
        "/ml/predict",
        {
            "node_id": node_id,
            "pm25": pm25,
            "pm10": pm10,
            "temperature": temperature,
            "humidity": humidity,
            "no2": no2,
            "so2": so2,
            "co": co,
            "o3": o3,
            "nh3": nh3,
        },
    )


async def detect_anomaly(
    node_id: str,
    readings: dict[str, float],
    timestamp: str,
) -> Optional[dict[str, Any]]:
    """Request anomaly detection from the ML isolation forest service.

    Args:
        node_id: UUID string of the sensor node.
        readings: Dict of pollutant → concentration value.
        timestamp: ISO-8601 timestamp string.

    Returns:
        Dict with keys ``is_anomaly``, ``anomaly_score``, ``flagged_indices``,
        or ``None`` if the ML server is unreachable.
    """
    return await _call_ml(
        "/ml/detect-anomaly",
        {"node_id": node_id, "readings": readings, "timestamp": timestamp},
    )


async def classify(
    node_id: str,
    readings: dict[str, float],
) -> Optional[dict[str, Any]]:
    """Request AQI category classification from the ML logistic regression service.

    Args:
        node_id: UUID string of the sensor node.
        readings: Dict of pollutant → concentration value.

    Returns:
        Dict with keys ``category`` and ``probabilities`` (dict of category → float),
        or ``None`` if the ML server is unreachable.
    """
    return await _call_ml(
        "/ml/classify",
        {"node_id": node_id, "readings": readings},
    )


async def detect_hotspot(
    node_data: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Request hotspot detection from the ML clustering service.

    Args:
        node_data: List of dicts each containing ``node_id``, ``readings``,
            and optionally ``lat`` / ``lon``.

    Returns:
        Dict with keys ``is_hotspot``, ``severity``, ``centroid``, ``radius_km``,
        or ``None`` if the ML server is unreachable.
    """
    return await _call_ml(
        "/ml/detect-hotspot",
        {"node_data": node_data},
    )


async def check_health() -> Optional[dict[str, Any]]:
    """Check the health of the ML server.

    Returns:
        Dict with keys ``status``, ``models_loaded``, ``version``,
        or ``None`` if the ML server is unreachable.
    """
    return await _call_ml("/ml/health", {}, method="GET")
