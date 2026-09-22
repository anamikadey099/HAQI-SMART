"""
AQI router — endpoints for querying AQI data.

Provides latest AQI for all nodes, per-node details, 5-minute
aggregations, and historical data with CSV export.

All endpoints are JWT-protected and return the standard
``APIResponse`` envelope.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user, TokenData
from app.database import get_session
from app.models.node import Node
from app.models.sensor_reading import SensorReading
from app.models.aggregated_aqi import AggregatedAQI
from app.schemas.aqi import (
    APIResponse,
    AQIResponse,
    AggregationResponse,
    ErrorDetail,
    NodeAQISummary,
    PaginatedResponse,
)

router = APIRouter(tags=["AQI"])


@router.get("/latest", response_model=APIResponse[list[NodeAQISummary]])
async def get_latest_aqi(
    session: AsyncSession = Depends(get_session),
    _user: TokenData = Depends(get_current_user),
) -> APIResponse[list[NodeAQISummary]]:
    """Get the latest AQI reading for every active sensor node.

    Returns a list of node summaries with their most recent AQI value,
    category, responsible pollutant, and sub-indices.

    Args:
        session: Async database session.
        _user: Authenticated user (JWT).

    Returns:
        APIResponse containing a list of :class:`NodeAQISummary`.
    """
    try:
        # Fetch all active nodes
        nodes_result = await session.execute(
            select(Node).where(Node.is_active == True)  # noqa: E712
        )
        nodes = nodes_result.scalars().all()

        summaries: list[NodeAQISummary] = []
        for node in nodes:
            # Get latest reading for this node
            reading_result = await session.execute(
                select(SensorReading)
                .where(SensorReading.node_id == node.id)
                .order_by(desc(SensorReading.timestamp))
                .limit(1)
            )
            reading = reading_result.scalar_one_or_none()

            latest = None
            if reading:
                latest = AQIResponse(
                    node_id=node.id,
                    timestamp=reading.timestamp,
                    aqi=reading.aqi,
                    category=reading.aqi_category,
                    responsible_pollutant=reading.responsible_pollutant,
                    sub_indices=reading.sub_indices or {},
                    is_anomaly=reading.is_anomaly,
                    anomaly_score=reading.anomaly_score,
                )

            summaries.append(
                NodeAQISummary(
                    node_id=node.id,
                    node_name=node.name,
                    region=node.region,
                    latitude=node.latitude,
                    longitude=node.longitude,
                    latest=latest,
                )
            )

        return APIResponse(
            success=True, data=summaries, timestamp=datetime.now(timezone.utc)
        )
    except Exception as e:
        return APIResponse(
            success=False,
            error=ErrorDetail(code="QUERY_ERROR", message=str(e)),
            timestamp=datetime.now(timezone.utc),
        )


@router.get("/node/{node_id}", response_model=APIResponse[AQIResponse])
async def get_node_aqi(
    node_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user: TokenData = Depends(get_current_user),
) -> APIResponse[AQIResponse]:
    """Get the latest AQI breakdown for a specific node.

    Args:
        node_id: UUID of the sensor node.
        session: Async database session.
        _user: Authenticated user (JWT).

    Returns:
        APIResponse with full AQI breakdown including sub_indices
        and responsible_pollutant.
    """
    try:
        result = await session.execute(
            select(SensorReading)
            .where(SensorReading.node_id == node_id)
            .order_by(desc(SensorReading.timestamp))
            .limit(1)
        )
        reading = result.scalar_one_or_none()

        if not reading:
            return APIResponse(
                success=False,
                error=ErrorDetail(code="NOT_FOUND", message="No readings for this node"),
                timestamp=datetime.now(timezone.utc),
            )

        data = AQIResponse(
            node_id=reading.node_id,
            timestamp=reading.timestamp,
            aqi=reading.aqi,
            category=reading.aqi_category,
            responsible_pollutant=reading.responsible_pollutant,
            sub_indices=reading.sub_indices or {},
            is_anomaly=reading.is_anomaly,
            anomaly_score=reading.anomaly_score,
        )

        return APIResponse(
            success=True, data=data, timestamp=datetime.now(timezone.utc)
        )
    except Exception as e:
        return APIResponse(
            success=False,
            error=ErrorDetail(code="QUERY_ERROR", message=str(e)),
            timestamp=datetime.now(timezone.utc),
        )


@router.get("/aggregation", response_model=APIResponse[list[AggregationResponse]])
async def get_aggregation(
    node_id: Optional[uuid.UUID] = Query(None),
    region: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
    _user: TokenData = Depends(get_current_user),
) -> APIResponse[list[AggregationResponse]]:
    """Get 5-minute rollup aggregations per node and/or region.

    Args:
        node_id: Optional filter by node UUID.
        region: Optional filter by region name.
        session: Async database session.
        _user: Authenticated user (JWT).

    Returns:
        APIResponse with aggregation statistics.
    """
    try:
        query = select(AggregatedAQI).order_by(desc(AggregatedAQI.window_end)).limit(100)

        if node_id:
            query = query.where(AggregatedAQI.node_id == node_id)

        result = await session.execute(query)
        rows = result.scalars().all()

        data = [
            AggregationResponse(
                node_id=row.node_id,
                window_start=row.window_start,
                window_end=row.window_end,
                aqi_mean=row.aqi_mean,
                aqi_median=row.aqi_median,
                aqi_iqr=row.aqi_iqr,
                pm25_mean=row.pm25_mean,
                pm10_mean=row.pm10_mean,
                sample_count=row.sample_count or 0,
            )
            for row in rows
        ]

        return APIResponse(
            success=True, data=data, timestamp=datetime.now(timezone.utc)
        )
    except Exception as e:
        return APIResponse(
            success=False,
            error=ErrorDetail(code="QUERY_ERROR", message=str(e)),
            timestamp=datetime.now(timezone.utc),
        )


@router.get("/history")
async def get_history(
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    node_id: Optional[uuid.UUID] = Query(None),
    format: str = Query("json"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
    _user: TokenData = Depends(get_current_user),
):
    """Get historical AQI data with optional CSV export.

    Args:
        start: Start datetime filter (optional).
        end: End datetime filter (optional).
        node_id: Filter by specific node UUID (optional).
        format: Response format — ``'json'`` or ``'csv'``.
        page: Page number (1-indexed).
        page_size: Number of items per page (max 1000).
        session: Async database session.
        _user: Authenticated user (JWT).

    Returns:
        APIResponse with paginated results, or streaming CSV.
    """
    try:
        # Default time range: last 24 hours
        if not end:
            end = datetime.now(timezone.utc)
        if not start:
            start = end - timedelta(hours=24)

        query = (
            select(SensorReading)
            .where(SensorReading.timestamp >= start)
            .where(SensorReading.timestamp <= end)
            .order_by(desc(SensorReading.timestamp))
        )

        if node_id:
            query = query.where(SensorReading.node_id == node_id)

        # Count total
        count_query = (
            select(func.count())
            .select_from(SensorReading)
            .where(SensorReading.timestamp >= start)
            .where(SensorReading.timestamp <= end)
        )
        if node_id:
            count_query = count_query.where(SensorReading.node_id == node_id)

        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # CSV streaming format
        if format.lower() == "csv":
            all_result = await session.execute(query.limit(10000))
            all_rows = all_result.scalars().all()
            return _stream_csv(all_rows)

        # Paginated JSON
        offset = (page - 1) * page_size
        paginated = query.offset(offset).limit(page_size)
        result = await session.execute(paginated)
        rows = result.scalars().all()

        items = [
            AQIResponse(
                node_id=r.node_id,
                timestamp=r.timestamp,
                aqi=r.aqi,
                category=r.aqi_category,
                responsible_pollutant=r.responsible_pollutant,
                sub_indices=r.sub_indices or {},
                is_anomaly=r.is_anomaly,
                anomaly_score=r.anomaly_score,
            )
            for r in rows
        ]

        return APIResponse(
            success=True,
            data=PaginatedResponse(
                items=items, total=total, page=page, page_size=page_size
            ),
            timestamp=datetime.now(timezone.utc),
        )
    except Exception as e:
        return APIResponse(
            success=False,
            error=ErrorDetail(code="QUERY_ERROR", message=str(e)),
            timestamp=datetime.now(timezone.utc),
        )


def _stream_csv(rows: list) -> StreamingResponse:
    """Stream sensor readings as a CSV response.

    Args:
        rows: List of SensorReading ORM objects.

    Returns:
        StreamingResponse with ``text/csv`` content type.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "node_id", "timestamp", "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
        "aqi", "aqi_category", "responsible_pollutant", "is_anomaly",
    ])
    for r in rows:
        writer.writerow([
            str(r.node_id), r.timestamp.isoformat(), r.pm25, r.pm10,
            r.no2, r.so2, r.co, r.o3, r.nh3,
            r.aqi, r.aqi_category, r.responsible_pollutant, r.is_anomaly,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=haqi_export.csv"},
    )
