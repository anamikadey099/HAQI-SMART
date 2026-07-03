"""
AggregatedAQI ORM model — 5-minute rollup statistics.

Stores windowed aggregation results including mean, median, and IQR
of AQI and key pollutant concentrations per node.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AggregatedAQI(Base):
    """5-minute aggregated AQI statistics for a single node.

    Attributes:
        id: Auto-incrementing bigint primary key.
        node_id: Foreign key to the source sensor node.
        window_start: Start of the 5-minute aggregation window.
        window_end: End of the 5-minute aggregation window.
        aqi_mean: Mean AQI value within the window.
        aqi_median: Median AQI value within the window.
        aqi_iqr: Interquartile range of AQI within the window.
        pm25_mean: Mean PM2.5 concentration within the window.
        pm10_mean: Mean PM10 concentration within the window.
        sample_count: Number of readings aggregated.
    """

    __tablename__ = "aggregated_aqi"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False
    )
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    aqi_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    aqi_median: Mapped[float | None] = mapped_column(Float, nullable=True)
    aqi_iqr: Mapped[float | None] = mapped_column(Float, nullable=True)
    pm25_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    pm10_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AggregatedAQI(node_id={self.node_id!r}, "
            f"window={self.window_start}..{self.window_end}, "
            f"aqi_mean={self.aqi_mean})>"
        )
