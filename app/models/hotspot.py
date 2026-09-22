"""
Hotspot ORM model — detected pollution cluster events.

Stores geographic clusters of elevated AQI readings detected
by the ML hotspot detection pipeline, including severity,
centroid coordinates, and lifecycle timestamps.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Float, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Hotspot(Base):
    """A detected pollution hotspot cluster.

    Attributes:
        id: Auto-incrementing bigint primary key.
        node_ids: Array of node UUIDs involved in the hotspot.
        centroid_lat: Latitude of the cluster centroid.
        centroid_lon: Longitude of the cluster centroid.
        radius_km: Approximate radius of the hotspot in kilometres.
        severity: Severity label (e.g. 'Low', 'Medium', 'High', 'Critical').
        aqi_at_detection: AQI value at the time the hotspot was first detected.
        detected_at: Timestamp when the hotspot was first detected.
        resolved_at: Timestamp when the hotspot was resolved (``None`` if active).
    """

    __tablename__ = "hotspots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    node_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    centroid_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    centroid_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    radius_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aqi_at_detection: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<Hotspot(id={self.id}, severity={self.severity!r}, "
            f"aqi={self.aqi_at_detection}, resolved={'Yes' if self.resolved_at else 'No'})>"
        )
