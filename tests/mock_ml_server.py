"""
Mock ML Server — for development and testing.

Returns dummy responses with correct shapes for all ML endpoints.
Run with: uvicorn tests.mock_ml_server:app --port 9000

This is ONLY for development/testing. Production uses real ML microservices.
"""

from __future__ import annotations

import random
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock ML Server", version="0.1.0-mock")


class PredictPayload(BaseModel):
    node_id: str
    pm25: float
    pm10: float
    temperature: float | None = None
    humidity: float | None = None
    no2: float | None = None
    so2: float | None = None
    co: float | None = None
    o3: float | None = None
    nh3: float | None = None


class AnomalyPayload(BaseModel):
    node_id: str
    readings: dict[str, float]
    timestamp: str


class ClassifyPayload(BaseModel):
    node_id: str
    readings: dict[str, float]


class HotspotPayload(BaseModel):
    node_data: list[dict]


@app.post("/ml/predict")
async def predict(payload: PredictPayload) -> dict:
    """Return a mock AQI prediction."""
    aqi = (payload.pm25 * 0.4 + payload.pm10 * 0.3) + random.uniform(-5, 5)
    aqi = max(0, min(500, aqi))
    category = _get_category(aqi)
    return {
        "predicted_aqi": round(aqi, 2),
        "confidence": round(random.uniform(0.75, 0.98), 3),
        "category": category,
    }


@app.post("/ml/detect-anomaly")
async def detect_anomaly(payload: AnomalyPayload) -> dict:
    """Return a mock anomaly detection result."""
    score = random.uniform(0.0, 0.3)
    is_anomaly = score > 0.25
    return {
        "is_anomaly": is_anomaly,
        "anomaly_score": round(score, 4),
        "flagged_indices": ["pm25"] if is_anomaly else [],
    }


@app.post("/ml/classify")
async def classify(payload: ClassifyPayload) -> dict:
    """Return mock classification probabilities."""
    categories = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
    raw = [random.random() for _ in categories]
    total = sum(raw)
    probs = {c: round(v / total, 4) for c, v in zip(categories, raw)}
    top = max(probs, key=lambda k: probs[k])
    return {"category": top, "probabilities": probs}


@app.post("/ml/detect-hotspot")
async def detect_hotspot(payload: HotspotPayload) -> dict:
    """Return a mock hotspot detection result."""
    return {
        "is_hotspot": False,
        "severity": None,
        "centroid": None,
        "radius_km": None,
    }


@app.get("/ml/health")
async def health() -> dict:
    """Return mock ML health status."""
    return {
        "status": "ok",
        "models_loaded": ["random_forest", "isolation_forest", "logistic_regression", "clustering"],
        "version": "mock-0.1.0",
    }


def _get_category(aqi: float) -> str:
    if aqi <= 50:   return "Good"
    if aqi <= 100:  return "Satisfactory"
    if aqi <= 200:  return "Moderate"
    if aqi <= 300:  return "Poor"
    if aqi <= 400:  return "Very Poor"
    return "Severe"
