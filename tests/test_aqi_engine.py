"""
tests/test_aqi_engine.py
------------------------
Full pytest test suite for the CPCB AQI engine.

All tests exercise the real implementation — no mocking.
Run with:  pytest tests/test_aqi_engine.py -v
"""

import pytest

from app.services.aqi_engine import calculate_sub_index, compute_aqi


# ===========================================================================
# calculate_sub_index — boundary & formula tests
# ===========================================================================


def test_pm10_boundary_good_upper() -> None:
    """PM10=50 is the upper boundary of Good; sub-index must be exactly 50.0."""
    assert calculate_sub_index("pm10", 50) == 50.0


def test_pm10_boundary_satisfactory_lower() -> None:
    """PM10=51 is the lower boundary of Satisfactory."""
    si = calculate_sub_index("pm10", 51)
    assert si is not None
    assert 50 <= si <= 55  # just above 50


def test_pm25_moderate_midpoint() -> None:
    """PM2.5=75 is in Moderate (61–90 → AQI 101–200); expect ~150."""
    si = calculate_sub_index("pm25", 75)
    assert si is not None
    assert 140 <= si <= 160


def test_co_unit_is_mg_not_ug() -> None:
    """CO=1.5 mg/m³ = Satisfactory (1.1–2.0); must NOT be treated as µg/m³."""
    si = calculate_sub_index("co", 1.5)
    assert si is not None
    assert 51 <= si <= 100


def test_negative_concentration_returns_none() -> None:
    """Negative concentrations are invalid — must return None."""
    assert calculate_sub_index("pm25", -1.0) is None


def test_unknown_pollutant_raises() -> None:
    """Querying an unknown pollutant key must raise ValueError."""
    with pytest.raises(ValueError):
        calculate_sub_index("xyz", 50.0)


def test_ilo_decrement_rule() -> None:
    """ILO > 50 must be decremented by 1 before formula (CPCB Ch 3.5).

    PM10=101 starts the Moderate band (ILO=101, BLO=101).
    With ILO decremented to 100:
      Ip = ((200 - 100) / (250 - 101)) * (101 - 101) + 100 = 100.0
    """
    si = calculate_sub_index("pm10", 101)
    assert si == 100.0


# ===========================================================================
# compute_aqi — aggregation & validation tests
# ===========================================================================


def test_max_operator_picks_worst_pollutant() -> None:
    """PM2.5=75 gives ~150 SI; should beat PM10=80 (~80 SI) and NO2=50 (~63 SI)."""
    result = compute_aqi({"pm25": 75, "pm10": 80, "no2": 50})
    assert result.is_valid is True
    assert result.responsible_pollutant == "pm25"
    assert result.aqi is not None
    assert result.aqi >= 140


def test_insufficient_data_too_few_pollutants() -> None:
    """Only 2 pollutants — must return invalid (need >= 3)."""
    result = compute_aqi({"pm25": 50, "pm10": 60})
    assert result.is_valid is False


def test_insufficient_data_no_pm() -> None:
    """3 pollutants but no PM — must return invalid."""
    result = compute_aqi({"no2": 50, "so2": 30, "co": 1.0})
    assert result.is_valid is False
    assert result.reason is not None
    assert "pm" in result.reason


def test_lead_excluded_from_live_aqi() -> None:
    """include_lead=False (default) — pb must NOT appear in sub_indices."""
    result = compute_aqi(
        {"pm10": 80, "pm25": 50, "no2": 60, "pb": 5.0},
        include_lead=False,
    )
    assert "pb" not in result.sub_indices


def test_lead_included_in_historical_aqi() -> None:
    """include_lead=True — pb must appear in sub_indices."""
    result = compute_aqi(
        {"pm10": 80, "pm25": 50, "no2": 60, "pb": 2.5},
        include_lead=True,
    )
    assert "pb" in result.sub_indices


def test_severe_aqi_category_and_health_statement() -> None:
    """Very high concentrations should yield Severe category."""
    result = compute_aqi({"pm10": 500, "pm25": 300, "no2": 500})
    assert result.is_valid is True
    assert result.category == "Severe"
    assert result.health_statement is not None
    assert "healthy" in result.health_statement.lower()


def test_good_aqi_category() -> None:
    """Low concentrations should yield Good category with AQI <= 50."""
    result = compute_aqi({"pm10": 30, "pm25": 20, "no2": 20})
    assert result.is_valid is True
    assert result.category == "Good"
    assert result.aqi is not None
    assert result.aqi <= 50


def test_responsible_pollutant_stored() -> None:
    """responsible_pollutant must never be None on a valid result
    and must exist as a key in sub_indices."""
    result = compute_aqi({"pm10": 100, "pm25": 80, "no2": 60})
    assert result.is_valid is True
    assert result.responsible_pollutant is not None
    assert result.responsible_pollutant in result.sub_indices
