"""
AQI Engine — CPCB National Air Quality Index Calculator.

Implements the CPCB (Central Pollution Control Board) AQI calculation
methodology as per CUPS/82/2014-15. Uses linear interpolation sub-index
formula with max() aggregation across pollutants.

This module is pure Python with zero external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# CPCB Breakpoints (CUPS/82/2014-15)
# Each tuple: (C_LO, C_HI, I_LO, I_HI)
# Units: PM10/PM2.5/NO2/SO2/O3/NH3 in µg/m³; CO in mg/m³; Pb in µg/m³
# ---------------------------------------------------------------------------

BREAKPOINTS: dict[str, list[tuple[float, float, int, int]]] = {
    "pm10": [
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 250, 101, 200),
        (251, 350, 201, 300),
        (351, 430, 301, 400),
        (431, 9999, 401, 500),
    ],
    "pm25": [
        (0, 30, 0, 50),
        (31, 60, 51, 100),
        (61, 90, 101, 200),
        (91, 120, 201, 300),
        (121, 250, 301, 400),
        (251, 9999, 401, 500),
    ],
    "no2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 180, 101, 200),
        (181, 280, 201, 300),
        (281, 400, 301, 400),
        (401, 9999, 401, 500),
    ],
    "so2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 380, 101, 200),
        (381, 800, 201, 300),
        (801, 1600, 301, 400),
        (1601, 9999, 401, 500),
    ],
    "o3": [
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 168, 101, 200),
        (169, 208, 201, 300),
        (209, 748, 301, 400),
        (749, 9999, 401, 500),
    ],
    "co": [
        (0, 1.0, 0, 50),
        (1.1, 2.0, 51, 100),
        (2.1, 10, 101, 200),
        (10.1, 17, 201, 300),
        (17.1, 34, 301, 400),
        (34.1, 9999, 401, 500),
    ],
    "nh3": [
        (0, 200, 0, 50),
        (201, 400, 51, 100),
        (401, 800, 101, 200),
        (801, 1200, 201, 300),
        (1201, 1800, 301, 400),
        (1801, 9999, 401, 500),
    ],
    "pb": [
        (0, 0.5, 0, 50),
        (0.6, 1.0, 51, 100),
        (1.1, 2.0, 101, 200),
        (2.1, 3.0, 201, 300),
        (3.1, 3.5, 301, 400),
        (3.6, 9999, 401, 500),
    ],
}


# ---------------------------------------------------------------------------
# AQI Category Bands
# ---------------------------------------------------------------------------

AQI_CATEGORIES: list[tuple[int, int, str, str]] = [
    (0, 50, "Good", "Minimal Impact"),
    (
        51,
        100,
        "Satisfactory",
        "May cause minor breathing discomfort to sensitive people",
    ),
    (
        101,
        200,
        "Moderate",
        "May cause breathing discomfort to people with lung/heart disease",
    ),
    (201, 300, "Poor", "May cause breathing discomfort on prolonged exposure"),
    (
        301,
        400,
        "Very Poor",
        "Respiratory illness on prolonged exposure; pronounced in lung/heart patients",
    ),
    (
        401,
        500,
        "Severe",
        "Respiratory effects even on healthy people; serious impacts on sensitive groups",
    ),
]


# ---------------------------------------------------------------------------
# AQI Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class AQIResult:
    """Result of an AQI computation for a set of pollutant readings.

    Attributes:
        aqi: The computed Air Quality Index value (0–500+), or None if invalid.
        category: CPCB category label (Good / Satisfactory / … / Severe).
        responsible_pollutant: The pollutant with the highest sub-index.
        sub_indices: Mapping of pollutant name → computed sub-index value.
        health_statement: CPCB health advisory for the computed category.
        is_valid: Whether the computation met minimum data requirements.
        reason: Human-readable reason when ``is_valid`` is False.
    """

    aqi: Optional[float] = None
    category: Optional[str] = None
    responsible_pollutant: Optional[str] = None
    sub_indices: dict[str, float] = field(default_factory=dict)
    health_statement: Optional[str] = None
    is_valid: bool = True
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_sub_index(pollutant: str, concentration: float) -> Optional[float]:
    """Calculate the sub-index for a single pollutant using CPCB linear interpolation.

    Formula (CPCB Chapter 3.5)::

        Ip = ((IHI - ILO) / (BHI - BLO)) * (Cp - BLO) + ILO

    When ILO > 50, ILO is decremented by 1 before applying the formula as per
    the CPCB specification.

    Args:
        pollutant: Pollutant key (e.g. ``'pm25'``, ``'co'``). Must exist in
            :data:`BREAKPOINTS`.
        concentration: Measured concentration value. Units must match the
            breakpoint table (µg/m³ for most; **mg/m³ for CO**).

    Returns:
        The computed sub-index as a float, or ``None`` if concentration is
        negative. Returns ``500.0`` if the concentration exceeds the highest
        breakpoint segment.

    Raises:
        KeyError: If *pollutant* is not present in :data:`BREAKPOINTS`.
    """
    if concentration < 0:
        return None

    segments = BREAKPOINTS[pollutant]

    for c_lo, c_hi, i_lo, i_hi in segments:
        if c_lo <= concentration <= c_hi:
            # CPCB Chapter 3.5: decrement ILO by 1 when ILO > 50
            adjusted_i_lo = i_lo - 1 if i_lo > 50 else i_lo
            sub_index = ((i_hi - adjusted_i_lo) / (c_hi - c_lo)) * (
                concentration - c_lo
            ) + adjusted_i_lo
            return round(sub_index, 2)

    # Concentration exceeds all breakpoint segments
    return 500.0


def get_category(aqi_value: float) -> tuple[str, str]:
    """Return the CPCB category label and health statement for an AQI value.

    Args:
        aqi_value: Numeric AQI value (typically 0–500).

    Returns:
        A tuple of ``(category_label, health_statement)``.
        Falls back to ``('Severe', <severe statement>)`` for values above 500.
    """
    for lo, hi, label, health in AQI_CATEGORIES:
        if lo <= aqi_value <= hi:
            return label, health
    # Above 500 → Severe
    return AQI_CATEGORIES[-1][2], AQI_CATEGORIES[-1][3]


def compute_aqi(
    readings: dict[str, Optional[float]],
    include_lead: bool = False,
) -> AQIResult:
    """Compute the overall AQI from a set of pollutant concentration readings.

    Implements the CPCB methodology:

    * At least **3 valid pollutant** readings are required.
    * At least one of ``pm10`` or ``pm25`` must be present.
    * Lead (``pb``) is **excluded by default** (set ``include_lead=True``
      to include it).
    * The overall AQI is the **maximum** sub-index across all pollutants
      (never mean or sum).
    * The pollutant with the highest sub-index becomes the
      ``responsible_pollutant``.

    Args:
        readings: Mapping of pollutant name → concentration value.
            ``None`` values are skipped.
        include_lead: If ``False`` (default), the ``pb`` key is excluded
            from computation even if present.

    Returns:
        An :class:`AQIResult` instance. Check ``is_valid`` to determine
        whether the result is usable.
    """
    # Filter out None values and optionally exclude lead
    valid_readings: dict[str, float] = {}
    for pollutant, value in readings.items():
        if value is None:
            continue
        if pollutant == "pb" and not include_lead:
            continue
        if pollutant not in BREAKPOINTS:
            continue
        valid_readings[pollutant] = value

    # Validation: need at least one PM metric
    has_pm = "pm10" in valid_readings or "pm25" in valid_readings
    if not has_pm:
        return AQIResult(
            is_valid=False,
            reason="At least one of pm10 or pm25 must be provided for valid AQI computation",
        )

    # Validation: need at least 3 pollutants
    if len(valid_readings) < 3:
        return AQIResult(
            is_valid=False,
            reason=(
                f"Insufficient pollutant data: got {len(valid_readings)}, "
                f"need at least 3 (including pm10 or pm25)"
            ),
        )

    # Calculate sub-indices
    sub_indices: dict[str, float] = {}
    for pollutant, concentration in valid_readings.items():
        si = calculate_sub_index(pollutant, concentration)
        if si is not None:
            sub_indices[pollutant] = si

    if not sub_indices:
        return AQIResult(
            is_valid=False,
            reason="No valid sub-indices could be computed from the provided readings",
        )

    # AQI = max across all sub-indices (CPCB rule — NEVER mean or sum)
    responsible_pollutant = max(sub_indices, key=lambda k: sub_indices[k])
    aqi_value = sub_indices[responsible_pollutant]

    category, health_statement = get_category(aqi_value)

    return AQIResult(
        aqi=round(aqi_value, 2),
        category=category,
        responsible_pollutant=responsible_pollutant,
        sub_indices=sub_indices,
        health_statement=health_statement,
        is_valid=True,
        reason=None,
    )
