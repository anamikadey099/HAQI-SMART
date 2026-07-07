"""
ML schemas — request/response models for ML proxy endpoints.

These schemas define the contract between the FastAPI backend and the
external ML microservices. No ML libraries are imported here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """Input payload for the ``POST /predict`` ML proxy endpoint.

    Attributes:
        node_id: UUID of the target sensor node.
        pm25: Current PM2.5 concentration in µg/m³.
        pm10: Current PM10 concentration in µg/m³.
        temperature: Ambient temperature in °C (optional).
        humidity: Relative humidity in % (optional).
        no2: NO₂ in µg/m³ (optional).
        so2: SO₂ in µg/m³ (optional).
        co: CO in **mg/m³** (optional).
        o3: O₃ in µg/m³ (optional).
        nh3: NH₃ in µg/m³ (optional).
    """

    node_id: uuid.UUID
    pm25: float = Field(ge=0)
    pm10: float = Field(ge=0)
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    no2: Optional[float] = None
    so2: Optional[float] = None
    co: Optional[float] = None  # mg/m³
    o3: Optional[float] = None
    nh3: Optional[float] = None


class PredictResponse(BaseModel):
    """Response from the ML prediction service.

    Attributes:
        predicted_aqi: Forecasted AQI value.
        confidence: Model confidence score (0–1).
        category: Predicted CPCB category label.
    """

    predicted_aqi: float
    confidence: float
    category: str


class AnomalyRequest(BaseModel):
    """Input payload for the ``POST /detect-anomaly`` ML proxy endpoint.

    Attributes:
        node_id: UUID of the sensor node.
        readings: Dict of pollutant → concentration values.
        timestamp: Timestamp of the reading.
    """

    node_id: uuid.UUID
    readings: dict[str, float]
    timestamp: datetime


class AnomalyResponse(BaseModel):
    """Response from the ML anomaly detection service.

    Attributes:
        is_anomaly: Whether the reading is anomalous.
        anomaly_score: Anomaly confidence score (0–1).
        flagged_indices: List of pollutant names that triggered the anomaly.
    """

    is_anomaly: bool
    anomaly_score: float
    flagged_indices: list[str] = Field(default_factory=list)


class ClassifyRequest(BaseModel):
    """Input payload for the ``POST /classify`` ML proxy endpoint.

    Attributes:
        node_id: UUID of the sensor node.
        readings: Dict of pollutant → concentration values.
    """

    node_id: uuid.UUID
    readings: dict[str, float]


class ClassifyResponse(BaseModel):
    """Response from the ML classification service.

    Attributes:
        category: Predicted CPCB category label.
        probabilities: Dict of category → probability.
    """

    category: str
    probabilities: dict[str, float]


class HotspotDetectRequest(BaseModel):
    """Input payload for the ``POST /detect-hotspot`` ML proxy endpoint.

    Attributes:
        node_data: List of dicts with node_id, lat, lon, aqi.
    """

    node_data: list[dict]


class HotspotDetectResponse(BaseModel):
    """Response from the ML hotspot detection service.

    Attributes:
        is_hotspot: Whether a hotspot was detected.
        severity: Hotspot severity label.
        centroid: Tuple of (lat, lon) for the cluster centre.
        radius_km: Approximate radius in kilometres.
    """

    is_hotspot: bool
    severity: Optional[str] = None
    centroid: Optional[dict[str, float]] = None
    radius_km: Optional[float] = None


class MLHealthResponse(BaseModel):
    """Response from the ML service health endpoint.

    Attributes:
        status: Service status string (e.g. ``'ok'``, ``'degraded'``).
        models_loaded: List of loaded model names.
        version: ML service version string.
    """

    status: str
    models_loaded: list[str] = Field(default_factory=list)
    version: str = "unknown"
