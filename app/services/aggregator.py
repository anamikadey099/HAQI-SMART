"""
Aggregation worker — APScheduler task for 5-minute AQI rollups.

Runs every 5 minutes, computing mean/median/IQR statistics for each
sensor node and persisting results to ``aggregated_aqi``. Triggers
hotspot detection on sustained high-AQI clusters and flags IQR spikes.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.aggregated_aqi import AggregatedAQI
from app.models.node import Node
from app.models.sensor_reading import SensorReading
from app.services.aqi_engine import compute_aqi

logger = logging.getLogger(__name__)

# APScheduler instance — registered in main.py lifespan
scheduler = AsyncIOScheduler(timezone="UTC")

# Track consecutive high-AQI windows per node for hotspot triggering
_consecutive_high_windows: dict[str, int] = {}
_HIGH_AQI_THRESHOLD = 200
_CONSECUTIVE_WINDOWS_FOR_HOTSPOT = 3
_IQR_SPIKE_MULTIPLIER = 1.5


def _compute_iqr(values: list[float]) -> float:
    """Compute the interquartile range of a list of values.

    Args:
        values: List of numeric values (must have >= 4 elements for accuracy).

    Returns:
        IQR as a float. Returns 0.0 for fewer than 2 values.
    """
    if len(values) < 2:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    return q3 - q1


async def run_aggregation() -> None:
    """Execute the 5-minute aggregation cycle.

    For each active node:
    1. Queries ``sensor_readings`` for the last 5 minutes.
    2. Computes mean, median, IQR of PM2.5, PM10, and AQI.
    3. Re-runs AQI computation on 5-min mean concentrations.
    4. Persists results to ``aggregated_aqi``.
    5. Triggers hotspot detection if AQI > 200 for 3+ consecutive windows.
    6. Flags IQR spike nodes for anomaly review.
    """
    logger.info("Running 5-minute aggregation cycle")
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=5)

    async with async_session_factory() as session:
        try:
            await _aggregate_all_nodes(session, window_start, now)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Aggregation cycle failed")


async def _aggregate_all_nodes(
    session: AsyncSession,
    window_start: datetime,
    window_end: datetime,
) -> None:
    """Aggregate readings for all active nodes in the given time window.

    Args:
        session: Async database session.
        window_start: Start of the aggregation window.
        window_end: End of the aggregation window.
    """
    nodes_result = await session.execute(
        select(Node).where(Node.is_active == True)  # noqa: E712
    )
    nodes = nodes_result.scalars().all()

    for node in nodes:
        await _aggregate_node(session, node, window_start, window_end)


async def _aggregate_node(
    session: AsyncSession,
    node: Node,
    window_start: datetime,
    window_end: datetime,
) -> None:
    """Compute and persist aggregation stats for a single node.

    Args:
        session: Async database session.
        node: The sensor node to aggregate.
        window_start: Start of the 5-minute window.
        window_end: End of the 5-minute window.
    """
    readings_result = await session.execute(
        select(SensorReading)
        .where(SensorReading.node_id == node.id)
        .where(SensorReading.timestamp >= window_start)
        .where(SensorReading.timestamp <= window_end)
    )
    readings = readings_result.scalars().all()

    if not readings:
        logger.debug("No readings for node %s in window", node.id)
        return

    # Collect numeric series
    aqi_vals = [r.aqi for r in readings if r.aqi is not None]
    pm25_vals = [r.pm25 for r in readings if r.pm25 is not None]
    pm10_vals = [r.pm10 for r in readings if r.pm10 is not None]

    aqi_mean = statistics.mean(aqi_vals) if aqi_vals else None
    aqi_median = statistics.median(aqi_vals) if aqi_vals else None
    aqi_iqr = _compute_iqr(aqi_vals) if len(aqi_vals) >= 2 else None
    pm25_mean = statistics.mean(pm25_vals) if pm25_vals else None
    pm10_mean = statistics.mean(pm10_vals) if pm10_vals else None

    # Re-run AQI on 5-min mean concentrations
    if pm25_mean is not None and pm10_mean is not None:
        mean_readings: dict[str, Optional[float]] = {
            "pm25": pm25_mean,
            "pm10": pm10_mean,
        }
        # Include other pollutant means if available
        for attr in ("no2", "so2", "co", "o3", "nh3"):
            vals = [getattr(r, attr) for r in readings if getattr(r, attr) is not None]
            mean_readings[attr] = statistics.mean(vals) if vals else None

        aqi_result = compute_aqi(mean_readings, include_lead=False)
        if aqi_result.is_valid and aqi_result.aqi is not None:
            aqi_mean = aqi_result.aqi  # Use recomputed AQI

    # Persist aggregation row
    agg = AggregatedAQI(
        node_id=node.id,
        window_start=window_start,
        window_end=window_end,
        aqi_mean=aqi_mean,
        aqi_median=aqi_median,
        aqi_iqr=aqi_iqr,
        pm25_mean=pm25_mean,
        pm10_mean=pm10_mean,
        sample_count=len(readings),
    )
    session.add(agg)

    # Check hotspot trigger
    node_key = str(node.id)
    if aqi_mean and aqi_mean > _HIGH_AQI_THRESHOLD:
        _consecutive_high_windows[node_key] = (
            _consecutive_high_windows.get(node_key, 0) + 1
        )
        if _consecutive_high_windows[node_key] >= _CONSECUTIVE_WINDOWS_FOR_HOTSPOT:
            logger.warning(
                "Node %s has %d consecutive high-AQI windows (AQI=%.1f). "
                "Triggering hotspot detection.",
                node.id,
                _consecutive_high_windows[node_key],
                aqi_mean,
            )
            await _trigger_hotspot(node, aqi_mean)
    else:
        _consecutive_high_windows[node_key] = 0

    # Flag IQR spike
    if aqi_iqr and aqi_mean and aqi_iqr > _IQR_SPIKE_MULTIPLIER * aqi_iqr:
        logger.info(
            "IQR spike detected for node %s: IQR=%.2f", node.id, aqi_iqr
        )


async def _trigger_hotspot(node: Node, current_aqi: float) -> None:
    """Call ML hotspot detection and persist result if confirmed.

    Args:
        node: The sensor node at the centre of the suspected hotspot.
        current_aqi: Current aggregated AQI value.
    """
    try:
        from app.services.ml_client import detect_hotspot

        result = await detect_hotspot(
            node_data=[
                {
                    "node_id": str(node.id),
                    "lat": node.latitude,
                    "lon": node.longitude,
                    "aqi": current_aqi,
                }
            ]
        )

        if result and result.get("is_hotspot"):
            async with async_session_factory() as session:
                from app.models.hotspot import Hotspot

                centroid = result.get("centroid", {})
                hotspot = Hotspot(
                    node_ids=[node.id],
                    centroid_lat=centroid.get("lat", node.latitude),
                    centroid_lon=centroid.get("lon", node.longitude),
                    radius_km=result.get("radius_km"),
                    severity=result.get("severity"),
                    aqi_at_detection=current_aqi,
                )
                session.add(hotspot)
                await session.commit()
                logger.info("Hotspot persisted for node %s", node.id)

                try:
                    from app.middleware.metrics import haqi_hotspot_active
                    # Approximate: increment by 1 (health endpoint gives exact count)
                    haqi_hotspot_active.inc()
                except ImportError:
                    pass
    except Exception:
        logger.exception("Hotspot trigger failed for node %s", node.id)
