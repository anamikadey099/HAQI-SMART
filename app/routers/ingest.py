"""
Ingest router — sensor data ingestion endpoint.

Handles ``POST /ingest`` with API key authentication, Pydantic
validation, CPCB AQI computation, async DB persistence, and
asynchronous anomaly detection trigger.

Rate limited to 100 requests/minute per node API key.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.api_key import verify_api_key
from app.database import get_session
from app.middleware.rate_limit import limiter
from app.models.node import Node
from app.models.sensor_reading import SensorReading
from app.schemas.aqi import APIResponse, AQIResponse, ErrorDetail
from app.schemas.ingest import IngestPayload
from app.services.aqi_engine import compute_aqi

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ingest"])


@router.post("/ingest", response_model=APIResponse[AQIResponse])
@limiter.limit("100/minute")
async def ingest_reading(
    request: Request,
    payload: IngestPayload,
    node: Node = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> APIResponse[AQIResponse]:
    """Ingest a sensor telemetry reading.

    Validates the payload, computes AQI using CPCB breakpoints (lead
    excluded), persists the reading with AQI metadata to the database,
    and triggers async anomaly detection if AQI > 150.

    Args:
        request: FastAPI request object (required by SlowAPI).
        payload: Validated sensor telemetry data.
        node: Authenticated sensor node (via API key).
        session: Async database session.

    Returns:
        APIResponse containing the computed AQI result.
    """
    try:
        # Build readings dict from payload (only non-None pollutants)
        readings: dict[str, float | None] = {
            "pm25": payload.pm25,
            "pm10": payload.pm10,
            "no2": payload.no2,
            "so2": payload.so2,
            "co": payload.co,  # mg/m³
            "o3": payload.o3,
            "nh3": payload.nh3,
        }

        # Compute AQI — include_lead=False (HARD RULE #4)
        aqi_result = compute_aqi(readings, include_lead=False)

        # Persist to database (async — HARD RULE #7)
        reading = SensorReading(
            node_id=node.id,
            timestamp=payload.timestamp,
            pm25=payload.pm25,
            pm10=payload.pm10,
            temperature=payload.temperature,
            humidity=payload.humidity,
            no2=payload.no2,
            so2=payload.so2,
            co=payload.co,
            o3=payload.o3,
            nh3=payload.nh3,
            aqi=aqi_result.aqi,
            aqi_category=aqi_result.category,
            responsible_pollutant=aqi_result.responsible_pollutant,
            sub_indices=aqi_result.sub_indices,
            is_anomaly=False,
            anomaly_score=None,
        )
        session.add(reading)
        await session.flush()

        # Trigger async anomaly detection if AQI > 150
        if aqi_result.aqi and aqi_result.aqi > 150:
            asyncio.create_task(_trigger_anomaly_check(node.id, readings, payload.timestamp))

        # Update Prometheus metrics (imported lazily to avoid circular deps)
        try:
            from app.middleware.metrics import haqi_aqi_value, haqi_ingest_total

            if aqi_result.aqi is not None:
                haqi_aqi_value.labels(
                    node_id=str(node.id),
                    category=aqi_result.category or "Unknown",
                ).set(aqi_result.aqi)
            haqi_ingest_total.labels(
                node_id=str(node.id), status="success"
            ).inc()
        except ImportError:
            pass

        response_data = AQIResponse(
            node_id=node.id,
            timestamp=payload.timestamp,
            aqi=aqi_result.aqi,
            category=aqi_result.category,
            responsible_pollutant=aqi_result.responsible_pollutant,
            sub_indices=aqi_result.sub_indices,
            health_statement=aqi_result.health_statement,
            is_anomaly=False,
            anomaly_score=None,
        )

        return APIResponse(
            success=True,
            data=response_data,
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.exception("Ingest error")
        try:
            from app.middleware.metrics import haqi_ingest_total

            haqi_ingest_total.labels(
                node_id=str(payload.node_id), status="error"
            ).inc()
        except ImportError:
            pass

        return APIResponse(
            success=False,
            error=ErrorDetail(code="INGEST_ERROR", message=str(e)),
            timestamp=datetime.now(timezone.utc),
        )


async def _trigger_anomaly_check(
    node_id: "object",
    readings: dict[str, float | None],
    timestamp: datetime,
) -> None:
    """Fire-and-forget anomaly detection via ML client.

    Args:
        node_id: UUID of the sensor node.
        readings: Pollutant concentration dict.
        timestamp: Reading timestamp.
    """
    try:
        from app.services.ml_client import detect_anomaly

        result = await detect_anomaly(
            node_id=str(node_id),
            readings={k: v for k, v in readings.items() if v is not None},
            timestamp=timestamp.isoformat(),
        )
        if result and result.get("is_anomaly"):
            logger.warning(
                "Anomaly detected for node %s: score=%s",
                node_id,
                result.get("anomaly_score"),
            )
            try:
                from app.middleware.metrics import haqi_anomaly_count

                haqi_anomaly_count.labels(node_id=str(node_id)).inc()
            except ImportError:
                pass
    except Exception:
        logger.exception("Anomaly check failed for node %s", node_id)
