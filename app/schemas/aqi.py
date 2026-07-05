"""
AQI schemas — response models for AQI endpoints.

All responses use the standard ``APIResponse`` envelope with
``{success, data, error, timestamp}``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Structured error information inside the API response envelope.

    Attributes:
        code: Machine-readable error code (e.g. ``'VALIDATION_ERROR'``).
        message: Human-readable error description.
    """

    code: str
    message: str


class APIResponse(BaseModel, Generic[T]):
    """Standard response envelope used by ALL endpoints.

    Attributes:
        success: Whether the request completed successfully.
        data: The response payload (``None`` on error).
        error: Error details (``None`` on success).
        timestamp: Server UTC timestamp of the response.
    """

    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())


class SubIndexInfo(BaseModel):
    """Sub-index value for a single pollutant.

    Attributes:
        pollutant: Pollutant identifier (e.g. ``'pm25'``).
        value: Computed sub-index value.
    """

    pollutant: str
    value: float


class AQIResponse(BaseModel):
    """AQI computation result for a single reading or node.

    Attributes:
        node_id: UUID of the source sensor node.
        timestamp: Timestamp of the reading.
        aqi: Computed AQI value (0–500+).
        category: CPCB category label.
        responsible_pollutant: Pollutant with the highest sub-index.
        sub_indices: Dict of pollutant → sub-index value.
        health_statement: CPCB health advisory text.
        is_anomaly: Whether the reading was flagged as anomalous.
        anomaly_score: Anomaly confidence score from ML.
    """

    node_id: uuid.UUID
    timestamp: datetime
    aqi: Optional[float] = None
    category: Optional[str] = None
    responsible_pollutant: Optional[str] = None
    sub_indices: dict[str, float] = Field(default_factory=dict)
    health_statement: Optional[str] = None
    is_anomaly: bool = False
    anomaly_score: Optional[float] = None


class NodeAQISummary(BaseModel):
    """Summary AQI information for a single node (used in ``GET /latest``).

    Attributes:
        node_id: UUID of the sensor node.
        node_name: Human-readable node name.
        region: Regional grouping label.
        latitude: Geographic latitude.
        longitude: Geographic longitude.
        latest: Most recent AQI response data.
    """

    node_id: uuid.UUID
    node_name: str
    region: Optional[str] = None
    latitude: float
    longitude: float
    latest: Optional[AQIResponse] = None


class AggregationResponse(BaseModel):
    """5-minute rollup aggregation statistics for a node.

    Attributes:
        node_id: UUID of the sensor node.
        window_start: Start of the aggregation window.
        window_end: End of the aggregation window.
        aqi_mean: Mean AQI within the window.
        aqi_median: Median AQI within the window.
        aqi_iqr: IQR of AQI within the window.
        pm25_mean: Mean PM2.5 within the window.
        pm10_mean: Mean PM10 within the window.
        sample_count: Number of readings in the window.
    """

    node_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    aqi_mean: Optional[float] = None
    aqi_median: Optional[float] = None
    aqi_iqr: Optional[float] = None
    pm25_mean: Optional[float] = None
    pm10_mean: Optional[float] = None
    sample_count: int = 0


class PaginatedResponse(BaseModel):
    """Wrapper for paginated query results.

    Attributes:
        items: List of result items for the current page.
        total: Total number of matching items across all pages.
        page: Current page number (1-indexed).
        page_size: Number of items per page.
    """

    items: list[AQIResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
