"""
Unit tests for the CPCB AQI Engine.

Validates boundary conditions, unit correctness (CO in mg/m³),
max() aggregation, lead exclusion, insufficient-data handling,
and health-statement mapping.
"""

import sys
import os

# Ensure the project root is on sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.aqi_engine import calculate_sub_index, compute_aqi


def test_pm10_boundary_good_upper() -> None:
    """PM10 = 50 µg/m³ sits at the exact upper boundary of 'Good' (AQI 50)."""
    assert calculate_sub_index("pm10", 50) == 50.0


def test_pm25_moderate_midpoint() -> None:
    """PM2.5 = 75 µg/m³ falls in the Moderate band (61–90 → AQI 101–200).

    Expected sub-index should be approximately 148–151 depending on ILO
    decrement rule.
    """
    si = calculate_sub_index("pm25", 75)
    assert si is not None
    assert 140 <= si <= 160, f"PM2.5=75 sub-index was {si}, expected 140–160"


def test_co_unit_is_mg_not_ug() -> None:
    """CO breakpoints are in mg/m³. 1.5 mg/m³ → Satisfactory (AQI 51–100)."""
    si = calculate_sub_index("co", 1.5)
    assert si is not None
    assert 51 <= si <= 100, f"CO=1.5 mg/m³ sub-index was {si}, expected 51–100"


def test_max_operator_picks_worst_pollutant() -> None:
    """AQI = max() across sub-indices. PM2.5=75 should dominate over PM10=80 and NO2=50."""
    result = compute_aqi({"pm25": 75, "pm10": 80, "no2": 50})
    assert result.is_valid is True
    assert result.responsible_pollutant == "pm25"
    assert result.aqi is not None
    assert result.aqi >= 140, f"AQI was {result.aqi}, expected >= 140"


def test_insufficient_data_no_pm() -> None:
    """Without any PM reading, AQI is invalid regardless of other pollutants."""
    result = compute_aqi({"no2": 50, "so2": 30, "co": 1.0})
    assert result.is_valid is False
    assert result.reason is not None
    assert "pm" in result.reason.lower()


def test_lead_excluded_from_live_aqi() -> None:
    """Lead (Pb) must be excluded from live AQI when include_lead=False."""
    result = compute_aqi(
        {"pm10": 80, "pm25": 50, "pb": 5.0, "no2": 40},
        include_lead=False,
    )
    assert result.is_valid is True
    assert "pb" not in result.sub_indices


def test_severe_aqi_returns_correct_health_statement() -> None:
    """Extreme readings should yield Severe category with 'healthy' in the health statement."""
    result = compute_aqi({"pm10": 500, "pm25": 300, "no2": 500})
    assert result.is_valid is True
    assert result.category == "Severe"
    assert result.health_statement is not None
    assert "healthy" in result.health_statement.lower()


# ---- Additional edge-case tests ----


def test_negative_concentration_returns_none() -> None:
    """Negative concentration should return None sub-index."""
    assert calculate_sub_index("pm10", -5) is None


def test_concentration_beyond_max_returns_500() -> None:
    """Concentration far exceeding breakpoints should return 500.0."""
    assert calculate_sub_index("pm10", 99999) == 500.0


def test_lead_included_when_flag_set() -> None:
    """When include_lead=True, Pb should appear in sub_indices."""
    result = compute_aqi(
        {"pm10": 80, "pm25": 50, "pb": 2.5, "no2": 40},
        include_lead=True,
    )
    assert result.is_valid is True
    assert "pb" in result.sub_indices
