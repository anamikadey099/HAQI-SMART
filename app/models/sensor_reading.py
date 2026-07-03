"""
SensorReading ORM model — raw telemetry from sensor nodes.

Maps to the ``sensor_readings`` TimescaleDB hypertable. Stores pollutant
concentrations, computed AQI values, responsible pollutant, sub-indices,
and anomaly detection metadata.

Note: CO concentration is stored in **mg/m³** (not µg/m³).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SensorReading(Base):
    """A single sensor telemetry record from a node.

    Attributes:
        id: Auto-incrementing bigint identifier.
        node_id: Foreign key to the originating sensor node.
        timestamp: Reading timestamp (timezone-aware).
        pm25: PM2.5 concentration in µg/m³.
        pm10: PM10 concentration in µg/m³.
        temperature: Ambient temperature in °C (optional).
        humidity: Relative humidity in % (optional).
        no2: NO₂ concentration in µg/m³ (optional).
        so2: SO₂ concentration in µg/m³ (optional).
        co: CO concentration in **mg/m³** (optional).
        o3: O₃ concentration in µg/m³ (optional).
        nh3: NH₃ concentration in µg/m³ (optional).
        aqi: Computed AQI value.
        aqi_category: CPCB category label.
        responsible_pollutant: Pollutant with the highest sub-index.
        sub_indices: JSON dict of pollutant → sub-index value.
        is_anomaly: Whether ML flagged this reading as anomalous.
        anomaly_score: Anomaly confidence score from ML.
    """

    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    pm25: Mapped[float] = mapped_column(Float, nullable=False)
    pm10: Mapped[float] = mapped_column(Float, nullable=False)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    no2: Mapped[float | None] = mapped_column(Float, nullable=True)
    so2: Mapped[float | None] = mapped_column(Float, nullable=True)
    co: Mapped[float | None] = mapped_column(Float, nullable=True)  # mg/m³
    o3: Mapped[float | None] = mapped_column(Float, nullable=True)
    nh3: Mapped[float | None] = mapped_column(Float, nullable=True)
    aqi: Mapped[float | None] = mapped_column(Float, nullable=True)
    aqi_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    responsible_pollutant: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    sub_indices: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    node: Mapped["Node"] = relationship(  # noqa: F821
        "Node", back_populates="readings"
    )

    def __repr__(self) -> str:
        return (
            f"<SensorReading(id={self.id}, node_id={self.node_id!r}, "
            f"timestamp={self.timestamp!r}, aqi={self.aqi})>"
        )
