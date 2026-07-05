"""
Ingest schemas — Pydantic models for sensor data ingestion.

Validates incoming telemetry payloads with strict field constraints.
CO concentration is validated in **mg/m³** (not µg/m³).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class IngestPayload(BaseModel):
    """Sensor telemetry payload for the ``POST /ingest`` endpoint.

    Attributes:
        node_id: UUID of the originating sensor node.
        timestamp: ISO-8601 timestamp of the reading.
        pm25: PM2.5 concentration in µg/m³ (required, 0–500).
        pm10: PM10 concentration in µg/m³ (required, 0–600).
        temperature: Ambient temperature in °C (optional, -40–85).
        humidity: Relative humidity in % (optional, 0–100).
        no2: NO₂ concentration in µg/m³ (optional).
        so2: SO₂ concentration in µg/m³ (optional).
        co: CO concentration in **mg/m³** (optional).
        o3: O₃ concentration in µg/m³ (optional).
        nh3: NH₃ concentration in µg/m³ (optional).
    """

    node_id: uuid.UUID
    timestamp: datetime
    pm25: float = Field(ge=0, le=500)
    pm10: float = Field(ge=0, le=600)
    temperature: Optional[float] = Field(None, ge=-40, le=85)
    humidity: Optional[float] = Field(None, ge=0, le=100)
    no2: Optional[float] = Field(None, ge=0)
    so2: Optional[float] = Field(None, ge=0)
    co: Optional[float] = Field(None, ge=0)  # mg/m³ NOT µg/m³
    o3: Optional[float] = Field(None, ge=0)
    nh3: Optional[float] = Field(None, ge=0)

    @model_validator(mode="after")
    def validate_pm_present(self) -> "IngestPayload":
        """Ensure at least one PM metric is non-None.

        Raises:
            ValueError: If both ``pm25`` and ``pm10`` are None.
        """
        if self.pm25 is None and self.pm10 is None:
            raise ValueError("At least one of pm25 or pm10 must be provided")
        return self

    model_config = {"json_schema_extra": {
        "example": {
            "node_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-15T10:30:00+05:30",
            "pm25": 65.0,
            "pm10": 120.0,
            "temperature": 32.5,
            "humidity": 60.0,
            "no2": 45.0,
            "so2": 20.0,
            "co": 1.5,
            "o3": 30.0,
            "nh3": 150.0,
        }
    }}
