"""
Prometheus metrics definitions — 5 HAQI-SMART metrics.

All metrics are defined at module import time. They are updated
by the routes and services throughout the application.

Exposes a ``/metrics`` endpoint via the ``prometheus_client`` library.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# 1. Current AQI value per node and category
haqi_aqi_value = Gauge(
    "haqi_aqi_value",
    "Current AQI value for a sensor node",
    labelnames=["node_id", "category"],
)

# 2. Total ingest requests per node and status
haqi_ingest_total = Counter(
    "haqi_ingest_total",
    "Total number of ingest requests",
    labelnames=["node_id", "status"],
)

# 3. ML call duration histogram per endpoint
haqi_ml_call_duration_seconds = Histogram(
    "haqi_ml_call_duration_seconds",
    "Duration of ML server HTTP calls in seconds",
    labelnames=["endpoint"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# 4. Total anomaly detection hits per node
haqi_anomaly_count = Counter(
    "haqi_anomaly_count",
    "Total number of anomalies detected per node",
    labelnames=["node_id"],
)

# 5. Current count of active (unresolved) hotspots
haqi_hotspot_active = Gauge(
    "haqi_hotspot_active",
    "Current number of active unresolved pollution hotspots",
)
