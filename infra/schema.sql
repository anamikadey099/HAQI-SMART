-- ============================================================
-- HAQI-SMART Database Schema
-- PostgreSQL 15 + TimescaleDB
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";     -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "timescaledb";  -- hypertables

-- -----------------------------------------------------------
-- nodes — sensor node registry
-- -----------------------------------------------------------
CREATE TABLE nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    region          VARCHAR(100),
    api_key_hash    VARCHAR(256) NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------
-- sensor_readings — raw telemetry (TimescaleDB hypertable)
-- -----------------------------------------------------------
CREATE TABLE sensor_readings (
    id                      BIGSERIAL,
    node_id                 UUID REFERENCES nodes(id),
    timestamp               TIMESTAMPTZ NOT NULL,
    pm25                    FLOAT NOT NULL,
    pm10                    FLOAT NOT NULL,
    temperature             FLOAT,
    humidity                FLOAT,
    no2                     FLOAT,
    so2                     FLOAT,
    co                      FLOAT,          -- mg/m³ (NOT µg/m³)
    o3                      FLOAT,
    nh3                     FLOAT,
    aqi                     FLOAT,
    aqi_category            VARCHAR(20),
    responsible_pollutant   VARCHAR(10),
    sub_indices             JSONB,
    is_anomaly              BOOLEAN DEFAULT FALSE,
    anomaly_score           FLOAT
);

-- Convert to TimescaleDB hypertable for efficient time-series queries
SELECT create_hypertable('sensor_readings', 'timestamp');

-- Composite index for fast per-node time-ordered lookups
CREATE INDEX ON sensor_readings (node_id, timestamp DESC);

-- -----------------------------------------------------------
-- aggregated_aqi — 5-minute rollup statistics
-- -----------------------------------------------------------
CREATE TABLE aggregated_aqi (
    id              BIGSERIAL PRIMARY KEY,
    node_id         UUID REFERENCES nodes(id),
    window_start    TIMESTAMPTZ NOT NULL,
    window_end      TIMESTAMPTZ NOT NULL,
    aqi_mean        FLOAT,
    aqi_median      FLOAT,
    aqi_iqr         FLOAT,
    pm25_mean       FLOAT,
    pm10_mean       FLOAT,
    sample_count    INT
);

-- -----------------------------------------------------------
-- hotspots — detected pollution clusters
-- -----------------------------------------------------------
CREATE TABLE hotspots (
    id                  BIGSERIAL PRIMARY KEY,
    node_ids            UUID[],
    centroid_lat        DOUBLE PRECISION,
    centroid_lon        DOUBLE PRECISION,
    radius_km           FLOAT,
    severity            VARCHAR(20),
    aqi_at_detection    FLOAT,
    detected_at         TIMESTAMPTZ DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ
);
