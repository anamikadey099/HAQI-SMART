"""
Hotspots router — active hotspot query endpoint.

Returns currently active (unresolved) pollution hotspots with
severity, node IDs, centroid coordinates, and detection timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user, TokenData
from app.database import get_session
from app.models.hotspot import Hotspot
from app.schemas.aqi import APIResponse, ErrorDetail

router = APIRouter(tags=["Hotspots"])


@router.get("/hotspots")
async def get_hotspots(
    session: AsyncSession = Depends(get_session),
    _user: TokenData = Depends(get_current_user),
) -> APIResponse:
    """Return all currently active (unresolved) hotspots.

    Args:
        session: Async database session.
        _user: Authenticated user (JWT).

    Returns:
        APIResponse with a list of active hotspot records.
    """
    try:
        result = await session.execute(
            select(Hotspot)
            .where(Hotspot.resolved_at == None)  # noqa: E711
            .order_by(Hotspot.detected_at.desc())
        )
        hotspots = result.scalars().all()

        data = [
            {
                "id": h.id,
                "node_ids": [str(uid) for uid in (h.node_ids or [])],
                "centroid_lat": h.centroid_lat,
                "centroid_lon": h.centroid_lon,
                "radius_km": h.radius_km,
                "severity": h.severity,
                "aqi_at_detection": h.aqi_at_detection,
                "detected_at": h.detected_at.isoformat() if h.detected_at else None,
                "resolved_at": None,
            }
            for h in hotspots
        ]

        # Update Prometheus gauge
        try:
            from app.middleware.metrics import haqi_hotspot_active

            haqi_hotspot_active.set(len(data))
        except ImportError:
            pass

        return APIResponse(
            success=True,
            data=data,
            timestamp=datetime.now(timezone.utc),
        )
    except Exception as e:
        return APIResponse(
            success=False,
            error=ErrorDetail(code="QUERY_ERROR", message=str(e)),
            timestamp=datetime.now(timezone.utc),
        )
