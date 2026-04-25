"""
app/main.py
-----------
Minimal FastAPI app — exposes the AQI engine for local testing.
Full routes / auth / DB will be added in the next session.

Endpoints
---------
GET  /health
POST /aqi/sub-index
POST /aqi/compute
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.services.aqi_engine import (
    AQIResult,
    calculate_sub_index,
    compute_aqi,
)

app = FastAPI(
    title="HAQI-SMART AQI Engine",
    description="CPCB CUPS/82/2014-15 compliant AQI computation — local test server",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class SubIndexRequest(BaseModel):
    """Single-pollutant sub-index request."""

    pollutant: str = Field(
        ...,
        examples=["pm25"],
        description="Pollutant key: pm10 | pm25 | no2 | so2 | o3 | co | nh3 | pb",
    )
    concentration: float = Field(
        ...,
        examples=[75.0],
        description="Measured concentration in µg/m³ (mg/m³ for CO).",
    )


class SubIndexResponse(BaseModel):
    pollutant: str
    concentration: float
    sub_index: Optional[float]
    note: Optional[str] = None


class ComputeAQIRequest(BaseModel):
    """Multi-pollutant AQI request."""

    readings: dict[str, Optional[float]] = Field(
        ...,
        examples=[{"pm10": 120, "pm25": 75, "no2": 50, "co": 1.5}],
        description="Map of pollutant key → concentration (None = missing sensor).",
    )
    include_lead: bool = Field(
        False,
        description="Set True to include lead (pb) in AQI computation (historical mode).",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok", "service": "haqi-smart-aqi-engine"}


@app.post("/aqi/sub-index", response_model=SubIndexResponse, tags=["aqi"])
def sub_index(req: SubIndexRequest) -> SubIndexResponse:
    """Compute the CPCB sub-index for a single pollutant + concentration."""
    try:
        si = calculate_sub_index(req.pollutant, req.concentration)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    note = "negative concentration — treated as missing" if si is None else None
    return SubIndexResponse(
        pollutant=req.pollutant,
        concentration=req.concentration,
        sub_index=si,
        note=note,
    )


@app.post("/aqi/compute", response_model=AQIResult, tags=["aqi"])
def compute(req: ComputeAQIRequest) -> AQIResult:
    """Compute composite AQI (max of sub-indices) from multiple pollutant readings."""
    return compute_aqi(req.readings, include_lead=req.include_lead)
