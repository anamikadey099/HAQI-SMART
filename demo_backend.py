"""
Demo Backend — Standalone FastAPI server with in-memory data.

Works WITHOUT PostgreSQL. Returns realistic mock data so the entire
Streamlit dashboard can be demonstrated locally.

Run with:
    .\\venv\\Scripts\\python.exe -m uvicorn demo_backend:app --port 8000 --reload

This is ONLY for demo purposes. Production uses the real backend (app/main.py)
with an actual TimescaleDB database.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
import io, csv

app = FastAPI(title="HAQI-SMART Demo Backend", version="demo-1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Simulated nodes ----
NODES = [
    {"id": "11111111-1111-1111-1111-111111111111", "name": "Delhi-Anand Vihar",   "lat": 28.6469, "lon": 77.3160, "region": "Delhi"},
    {"id": "22222222-2222-2222-2222-222222222222", "name": "Mumbai-Bandra",        "lat": 19.0596, "lon": 72.8295, "region": "Mumbai"},
    {"id": "33333333-3333-3333-3333-333333333333", "name": "Kolkata-Jadavpur",     "lat": 22.4996, "lon": 88.3712, "region": "Kolkata"},
    {"id": "44444444-4444-4444-4444-444444444444", "name": "Bangalore-Peenya",     "lat": 13.0289, "lon": 77.5189, "region": "Bangalore"},
    {"id": "55555555-5555-5555-5555-555555555555", "name": "Chennai-Manali",       "lat": 13.1588, "lon": 80.2613, "region": "Chennai"},
    {"id": "66666666-6666-6666-6666-666666666666", "name": "Hyderabad-Nacharam",   "lat": 17.4065, "lon": 78.5570, "region": "Hyderabad"},
]

# AQI categories via CPCB breakpoints
def _get_category(aqi: float) -> tuple[str, str]:
    if aqi <= 50:   return "Good",         "#00B050"
    if aqi <= 100:  return "Satisfactory", "#92D050"
    if aqi <= 200:  return "Moderate",     "#FFFF00"
    if aqi <= 300:  return "Poor",         "#FF7E00"
    if aqi <= 400:  return "Very Poor",    "#FF0000"
    return "Severe", "#7E0023"

def _make_reading(node: dict, ts: datetime | None = None, aqi_base: float | None = None) -> dict:
    """Generate a realistic sensor reading for a node."""
    if ts is None:
        ts = datetime.now(timezone.utc)
    if aqi_base is None:
        # Vary by city
        base = {"Delhi": 180, "Mumbai": 120, "Kolkata": 200, "Bangalore": 90, "Chennai": 110, "Hyderabad": 140}
        aqi_base = base.get(node["region"], 130) + random.uniform(-30, 30)

    aqi = max(10, min(490, aqi_base))
    category, _ = _get_category(aqi)

    pm25 = aqi * 0.35 + random.uniform(-5, 5)
    pm10 = aqi * 0.55 + random.uniform(-8, 8)
    no2  = aqi * 0.18 + random.uniform(-3, 3)
    so2  = aqi * 0.10 + random.uniform(-2, 2)
    co   = aqi * 0.005 + random.uniform(-0.1, 0.1)  # mg/m³
    o3   = aqi * 0.12 + random.uniform(-2, 2)
    nh3  = aqi * 0.08 + random.uniform(-1, 1)

    sub_indices = {
        "pm25": round(pm25 * 1.1, 1),
        "pm10": round(pm10 * 0.95, 1),
        "no2":  round(no2 * 1.0, 1),
        "so2":  round(so2 * 0.9, 1),
        "co":   round(co * 0.8, 1),
        "o3":   round(o3 * 0.85, 1),
    }
    responsible = max(sub_indices, key=lambda k: sub_indices[k])

    return {
        "node_id": node["id"],
        "timestamp": ts.isoformat(),
        "pm25": round(max(0, pm25), 2),
        "pm10": round(max(0, pm10), 2),
        "no2":  round(max(0, no2), 2),
        "so2":  round(max(0, so2), 2),
        "co":   round(max(0, co), 3),
        "o3":   round(max(0, o3), 2),
        "nh3":  round(max(0, nh3), 2),
        "aqi":  round(aqi, 1),
        "aqi_category": category,
        "responsible_pollutant": responsible,
        "sub_indices": sub_indices,
        "is_anomaly": aqi > 300 and random.random() > 0.7,
        "anomaly_score": round(random.uniform(0.0, 0.15), 4),
    }


def _envelope(data: Any, success: bool = True) -> dict:
    return {
        "success": success,
        "data": data,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---- Endpoints ----

@app.post("/auth/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:
    username = form_data.username
    password = form_data.password
    users = {"admin": "admin123", "viewer": "viewer123"}
    if users.get(username) == password:
        return {"access_token": "demo-jwt-token-valid", "token_type": "bearer"}
    return {"access_token": None}


@app.get("/health")
async def health() -> dict:
    return _envelope({"database": "ok (demo)", "ml_server": "ok", "scheduler": "running"})


@app.get("/latest")
async def get_latest() -> dict:
    summaries = []
    for node in NODES:
        reading = _make_reading(node)
        summaries.append({
            "node_id": node["id"],
            "node_name": node["name"],
            "region": node["region"],
            "latitude": node["lat"],
            "longitude": node["lon"],
            "latest": reading,
        })
    return _envelope(summaries)


@app.get("/node/{node_id}")
async def get_node(node_id: str) -> dict:
    node = next((n for n in NODES if n["id"] == node_id), NODES[0])
    return _envelope(_make_reading(node))


@app.get("/aggregation")
async def get_aggregation(node_id: str | None = None) -> dict:
    now = datetime.now(timezone.utc)
    result = []
    targets = [n for n in NODES if node_id is None or n["id"] == node_id]
    for node in targets:
        base = {"Delhi": 180, "Mumbai": 120, "Kolkata": 200, "Bangalore": 90, "Chennai": 110, "Hyderabad": 140}
        mean = base.get(node["region"], 130)
        result.append({
            "node_id": node["id"],
            "window_start": (now - timedelta(minutes=5)).isoformat(),
            "window_end": now.isoformat(),
            "aqi_mean": round(mean + random.uniform(-10, 10), 1),
            "aqi_median": round(mean + random.uniform(-5, 5), 1),
            "aqi_iqr": round(random.uniform(10, 40), 1),
            "pm25_mean": round(mean * 0.35, 1),
            "pm10_mean": round(mean * 0.55, 1),
            "sample_count": random.randint(8, 12),
        })
    return _envelope(result)


@app.get("/history")
async def get_history(
    start: str | None = None,
    end: str | None = None,
    node_id: str | None = None,
    format: str = "json",
    page: int = 1,
    page_size: int = 50,
):
    now = datetime.now(timezone.utc)
    targets = [n for n in NODES if node_id is None or n["id"] == node_id]
    items = []
    for i in range(min(page_size, 100)):
        ts = now - timedelta(minutes=i * 5)
        node = random.choice(targets)
        items.append(_make_reading(node, ts=ts))

    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["node_id", "timestamp", "pm25", "pm10",
                                                     "no2", "so2", "co", "o3", "nh3",
                                                     "aqi", "aqi_category", "responsible_pollutant", "is_anomaly"])
        writer.writeheader()
        for item in items:
            writer.writerow({k: item.get(k, "") for k in writer.fieldnames})
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=haqi_export.csv"},
        )

    return _envelope({"items": items, "total": 500, "page": page, "page_size": page_size})


@app.post("/predict")
async def predict(body: dict) -> dict:
    pm25 = body.get("pm25", 65)
    pm10 = body.get("pm10", 120)
    aqi = pm25 * 0.4 + pm10 * 0.3 + random.uniform(-5, 5)
    aqi = max(0, min(500, aqi))
    cat, _ = _get_category(aqi)
    return _envelope({"predicted_aqi": round(aqi, 1), "confidence": round(random.uniform(0.80, 0.97), 3), "category": cat})


@app.post("/detect-anomaly")
async def detect_anomaly(body: dict) -> dict:
    score = round(random.uniform(0.02, 0.18), 4)
    return _envelope({"is_anomaly": score > 0.15, "anomaly_score": score, "flagged_indices": []})


@app.post("/classify")
async def classify(body: dict) -> dict:
    cats = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
    raw = [random.random() for _ in cats]
    total = sum(raw)
    probs = {c: round(v / total, 4) for c, v in zip(cats, raw)}
    return _envelope({"category": max(probs, key=lambda k: probs[k]), "probabilities": probs})


@app.get("/hotspots")
async def get_hotspots() -> dict:
    now = datetime.now(timezone.utc)
    hotspots = [
        {
            "id": 1,
            "node_ids": ["11111111-1111-1111-1111-111111111111"],
            "centroid_lat": 28.6469,
            "centroid_lon": 77.3160,
            "radius_km": 8.5,
            "severity": "High",
            "aqi_at_detection": 245.0,
            "detected_at": (now - timedelta(hours=2)).isoformat(),
            "resolved_at": None,
        }
    ]
    return _envelope(hotspots)
