"""
Anomaly router — ML anomaly detection proxy endpoint.

Forwards anomaly detection requests to the external ML server,
persists confirmed anomalies to the database, and triggers
hotspot checks when anomalies are confirmed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user, TokenData
from app.database import get_session
from app.models.sensor_reading import SensorReading
from app.schemas.aqi import APIResponse, ErrorDetail
from app.schemas.ml import AnomalyRequest, AnomalyResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ML Proxy"])


@router.post("/detect-anomaly", response_model=APIResponse[AnomalyResponse])
async def detect_anomaly(
    payload: AnomalyRequest,
    session: AsyncSession = Depends(get_session),
    _user: TokenData = Depends(get_current_user),
) -> APIResponse[AnomalyResponse]:
    """Forward an anomaly detection request to the ML server.

    On confirmed anomaly, persists the result to the database and
    triggers a hotspot geography check.

    Args:
        payload: Anomaly detection input data.
        session: Async database session.
        _user: Authenticated user (JWT).

    Returns:
        APIResponse with anomaly detection results.
    """
    from app.services.ml_client import detect_anomaly as ml_detect

    result = await ml_detect(
        node_id=str(payload.node_id),
        readings=payload.readings,
        timestamp=payload.timestamp.isoformat(),
    )

    if result is None:
        return APIResponse(
            success=False,
            error=ErrorDetail(
                code="ML_UNAVAILABLE",
                message="Anomaly detection server is unreachable.",
            ),
            timestamp=datetime.now(timezone.utc),
        )

    response_data = AnomalyResponse(
        is_anomaly=result["is_anomaly"],
        anomaly_score=result["anomaly_score"],
        flagged_indices=result.get("flagged_indices", []),
    )

    # Persist anomaly result to DB (async)
    if result["is_anomaly"]:
        await session.execute(
            update(SensorReading)
            .where(SensorReading.node_id == payload.node_id)
            .where(SensorReading.timestamp == payload.timestamp)
            .values(
                is_anomaly=True,
                anomaly_score=result["anomaly_score"],
            )
        )
        logger.info(
            "Anomaly persisted for node %s at %s",
            payload.node_id,
            payload.timestamp,
        )

        # Trigger hotspot check
        try:
            from app.services.ml_client import detect_hotspot

            await detect_hotspot(
                node_data=[
                    {
                        "node_id": str(payload.node_id),
                        "readings": payload.readings,
                    }
                ]
            )
        except Exception:
            logger.exception("Hotspot check failed after anomaly detection")

        try:
            from app.middleware.metrics import haqi_anomaly_count

            haqi_anomaly_count.labels(node_id=str(payload.node_id)).inc()
        except ImportError:
            pass

    return APIResponse(
        success=True,
        data=response_data,
        timestamp=datetime.now(timezone.utc),
    )
