"""
Health router — system health check endpoint (no auth required).

Checks database connectivity, ML server reachability, and
scheduler status. Returns 503 if any critical component is down.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.database import async_session_factory
from app.schemas.aqi import APIResponse, ErrorDetail

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(response: Response) -> APIResponse:
    """System health check endpoint.

    Verifies:
    - **Database**: Can execute a simple query.
    - **ML server**: Reachable at the configured URL.
    - **Scheduler**: APScheduler is running.

    Returns 200 on all healthy, 503 if any critical component is down.
    No authentication required.

    Args:
        response: FastAPI response object (for setting status code).

    Returns:
        APIResponse with component health status dict.
    """
    health_status: dict[str, str] = {}
    all_healthy = True

    # 1. Database ping
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        health_status["database"] = "ok"
    except Exception as e:
        health_status["database"] = f"error: {str(e)[:100]}"
        all_healthy = False

    # 2. ML server reachability
    try:
        from app.services.ml_client import check_health

        ml_result = await check_health()
        if ml_result and ml_result.get("status") == "ok":
            health_status["ml_server"] = "ok"
        else:
            health_status["ml_server"] = "unreachable"
            # ML server being down is non-critical (graceful degradation)
    except Exception:
        health_status["ml_server"] = "unreachable"

    # 3. Scheduler status
    try:
        from app.services.aggregator import scheduler

        if scheduler.running:
            health_status["scheduler"] = "running"
        else:
            health_status["scheduler"] = "stopped"
            all_healthy = False
    except Exception:
        health_status["scheduler"] = "unknown"

    if not all_healthy:
        response.status_code = 503

    return APIResponse(
        success=all_healthy,
        data=health_status,
        error=None if all_healthy else ErrorDetail(
            code="UNHEALTHY",
            message="One or more critical components are down",
        ),
        timestamp=datetime.now(timezone.utc),
    )
