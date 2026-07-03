"""
Node ORM model — represents a physical sensor node in the network.

Each node has a unique UUID, geographic coordinates, region label,
and a hashed API key used for authenticating ingest requests.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Node(Base):
    """Sensor node registry entry.

    Attributes:
        id: Unique node identifier (UUID v4).
        name: Human-readable node name.
        latitude: Geographic latitude (WGS-84).
        longitude: Geographic longitude (WGS-84).
        region: Optional regional grouping label.
        api_key_hash: SHA-256 hash of the node's API key.
        is_active: Whether the node is currently active.
        created_at: Timestamp when the node was registered.
    """

    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    api_key_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    readings: Mapped[list["SensorReading"]] = relationship(  # noqa: F821
        "SensorReading", back_populates="node", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Node(id={self.id!r}, name={self.name!r}, region={self.region!r})>"
