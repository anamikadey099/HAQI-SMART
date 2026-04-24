"""
app/services/aqi_engine.py
--------------------------
Pure-Python AQI computation engine.

Standard  : CPCB CUPS/82/2014-15
Dependency: stdlib only (dataclasses, typing) — zero third-party imports.

Public API
~~~~~~~~~~
  calculate_sub_index(pollutant, concentration) -> float | None
  compute_aqi(readings, include_lead)           -> AQIResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Breakpoint table
# ---------------------------------------------------------------------------
# Each row: (BLO, BHI, ILO, IHI)
#   BLO/BHI  — pollutant concentration low/high for this segment
#   ILO/IHI  — corresponding AQI sub-index low/high
#
# Units
#   pm10, pm25, no2, so2, o3, nh3, pb  →  µg/m³
#   co                                  →  mg/m³  (NOT µg/m³)
# ---------------------------------------------------------------------------
BREAKPOINTS: dict[str, list[tuple[float, float, int, int]]] = {
    "pm10": [
        (0,    50,   0,   50),
        (51,   100,  51,  100),
        (101,  250,  101, 200),
        (251,  350,  201, 300),
        (351,  430,  301, 400),
        (431,  9999, 401, 500),
    ],
    "pm25": [
        (0,    30,   0,   50),
        (31,   60,   51,  100),
        (61,   90,   101, 200),
        (91,   120,  201, 300),
        (121,  250,  301, 400),
        (251,  9999, 401, 500),
    ],
    "no2": [
        (0,   40,   0,   50),
        (41,  80,   51,  100),
        (81,  180,  101, 200),
        (181, 280,  201, 300),
        (281, 400,  301, 400),
        (401, 9999, 401, 500),
    ],
    "so2": [
        (0,    40,   0,   50),
        (41,   80,   51,  100),
        (81,   380,  101, 200),
        (381,  800,  201, 300),
        (801,  1600, 301, 400),
        (1601, 9999, 401, 500),
    ],
    "o3": [
        (0,   50,   0,   50),
        (51,  100,  51,  100),
        (101, 168,  101, 200),
        (169, 208,  201, 300),
        (209, 748,  301, 400),
        (749, 9999, 401, 500),
    ],
    "co": [
        # CO in mg/m³  — do NOT convert to µg/m³ before passing here
        (0,    1.0,  0,   50),
        (1.1,  2.0,  51,  100),
        (2.1,  10,   101, 200),
        (10.1, 17,   201, 300),
        (17.1, 34,   301, 400),
        (34.1, 9999, 401, 500),
    ],
    "nh3": [
        (0,    200,  0,   50),
        (201,  400,  51,  100),
        (401,  800,  101, 200),
        (801,  1200, 201, 300),
        (1201, 1800, 301, 400),
        (1801, 9999, 401, 500),
    ],
    "pb": [
        # Lead — for historical queries only (never included in live AQI by default)
        (0,   0.5,  0,   50),
        (0.6, 1.0,  51,  100),
        (1.1, 2.0,  101, 200),
        (2.1, 3.0,  201, 300),
        (3.1, 3.5,  301, 400),
        (3.6, 9999, 401, 500),
    ],
}

# ---------------------------------------------------------------------------
# AQI category lookup
# ---------------------------------------------------------------------------
# Each row: (ILO, IHI, category_label, health_statement)
AQI_CATEGORIES: list[tuple[int, int, str, str]] = [
    (0,   50,  "Good",         "Minimal Impact"),
    (51,  100, "Satisfactory", "May cause minor breathing discomfort to sensitive people"),
    (101, 200, "Moderate",     "May cause breathing discomfort to people with lung/heart disease"),
    (201, 300, "Poor",         "May cause breathing discomfort on prolonged exposure"),
    (301, 400, "Very Poor",    "Respiratory illness on prolonged exposure; pronounced in lung/heart patients"),
    (401, 500, "Severe",       "Respiratory effects even on healthy people; serious impacts on sensitive groups"),
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class AQIResult:
    """Fully described AQI computation outcome."""

    aqi: Optional[float]
    """Computed AQI value (max of all valid sub-indices), or None when invalid."""

    category: Optional[str]
    """Human-readable category label (Good / Satisfactory / … / Severe)."""

    responsible_pollutant: Optional[str]
    """Key of the pollutant that drove the final AQI (highest sub-index)."""

    sub_indices: dict[str, float] = field(default_factory=dict)
    """All computed sub-indices keyed by pollutant name."""

    health_statement: Optional[str] = None
    """Guidance text associated with the AQI category."""

    is_valid: bool = False
    """True only when enough data was present to compute a meaningful AQI."""

    reason: Optional[str] = None
    """Why the result is invalid (populated when is_valid=False)."""


# ---------------------------------------------------------------------------
# Core formula helpers
# ---------------------------------------------------------------------------

def _find_segment(
    pollutant: str,
    concentration: float,
) -> Optional[tuple[float, float, int, int]]:
    """Return the breakpoint row whose [BLO, BHI] bracket covers *concentration*.

    Returns None if the concentration falls below all defined segments
    (negative values are rejected upstream).  If it exceeds all segments the
    caller handles the overflow case.
    """
    for segment in BREAKPOINTS[pollutant]:
        blo, bhi, _ilo, _ihi = segment
        if blo <= concentration <= bhi:
            return segment
    return None


def calculate_sub_index(pollutant: str, concentration: float) -> Optional[float]:
    """Compute the CPCB sub-index for *pollutant* at *concentration*.

    Parameters
    ----------
    pollutant     : One of the keys in BREAKPOINTS (case-sensitive).
    concentration : Measured value in the units expected by BREAKPOINTS.
                    CO must be in mg/m³; all others in µg/m³.

    Returns
    -------
    float         : Rounded sub-index (2 decimal places).
    None          : When concentration is negative (sensor error / missing).

    Raises
    ------
    ValueError    : Unknown pollutant key.

    Notes
    -----
    CPCB Chapter 3.5 ILO-decrement rule:
      When the looked-up ILO > 50, subtract 1 before applying the linear
      interpolation formula.  This ensures the sub-index boundary at the
      first point of each band above Good equals the lower bound exactly.

    Formula:
      Ip = ((IHI - ILO) / (BHI - BLO)) * (Cp - BLO) + ILO
    """
    if pollutant not in BREAKPOINTS:
        raise ValueError(
            f"Unknown pollutant '{pollutant}'. "
            f"Valid keys: {sorted(BREAKPOINTS.keys())}"
        )

    # Negative concentrations are physically impossible; treat as missing data.
    if concentration < 0:
        return None

    segment = _find_segment(pollutant, concentration)

    # Concentration exceeds every defined segment — clamp at 500.
    if segment is None:
        return 500.0

    blo, bhi, ilo, ihi = segment

    # CPCB Ch 3.5 ILO-decrement: bands above Good use ILO - 1 in the formula.
    effective_ilo: float = float(ilo - 1) if ilo > 50 else float(ilo)

    # Guard against zero-width segment (shouldn't happen with valid table).
    if bhi == blo:
        return float(effective_ilo)

    sub_index: float = ((ihi - effective_ilo) / (bhi - blo)) * (concentration - blo) + effective_ilo

    return round(sub_index, 2)


# ---------------------------------------------------------------------------
# Composite AQI
# ---------------------------------------------------------------------------

def _lookup_category(aqi_value: float) -> tuple[str, str]:
    """Return (category_label, health_statement) for *aqi_value*."""
    for lo, hi, label, statement in AQI_CATEGORIES:
        if lo <= aqi_value <= hi:
            return label, statement
    # Clamp: anything above 500 treated as Severe
    return AQI_CATEGORIES[-1][2], AQI_CATEGORIES[-1][3]


def compute_aqi(
    readings: dict[str, Optional[float]],
    include_lead: bool = False,
) -> AQIResult:
    """Compute the composite AQI from a set of pollutant readings.

    Parameters
    ----------
    readings     : Mapping of pollutant key → concentration (None = missing).
    include_lead : If True, lead (pb) participates in the composite AQI.
                   Set True only for historical analysis queries.

    Returns
    -------
    AQIResult with is_valid=True when data are sufficient, else is_valid=False
    with a human-readable reason string.

    Validation rules (both must be satisfied for is_valid=True)
    -----------------------------------------------------------
    1. At least 3 non-None pollutant readings.
    2. At least one of pm10 or pm25 must be present.

    Aggregation
    -----------
    AQI = max(sub_indices.values())   ← NEVER mean() or sum()
    The pollutant with the highest sub-index is the responsible_pollutant.
    """
    # --- filter out pb unless explicitly requested -------------------------
    candidate_readings: dict[str, float] = {
        key: val
        for key, val in readings.items()
        if val is not None
        and (key != "pb" or include_lead)
    }

    # --- validation rule 1: at least 3 pollutants -------------------------
    has_pm = "pm10" in candidate_readings or "pm25" in candidate_readings

    if len(candidate_readings) < 3 or not has_pm:
        reason = (
            "insufficient_data: need >=3 pollutants including pm10 or pm25"
        )
        return AQIResult(
            aqi=None,
            category=None,
            responsible_pollutant=None,
            is_valid=False,
            reason=reason,
        )

    # --- compute sub-indices ----------------------------------------------
    sub_indices: dict[str, float] = {}
    for key, val in candidate_readings.items():
        si = calculate_sub_index(key, val)
        if si is not None:
            sub_indices[key] = si

    # After computing, re-check we still have >=3 valid sub-indices
    valid_pm = any(k in sub_indices for k in ("pm10", "pm25"))
    if len(sub_indices) < 3 or not valid_pm:
        return AQIResult(
            aqi=None,
            category=None,
            responsible_pollutant=None,
            sub_indices=sub_indices,
            is_valid=False,
            reason="insufficient_data: need >=3 pollutants including pm10 or pm25",
        )

    # --- aggregation: max -------------------------------------------------
    responsible_pollutant: str = max(sub_indices, key=lambda k: sub_indices[k])
    aqi_value: float = sub_indices[responsible_pollutant]

    # --- category lookup --------------------------------------------------
    category, health_statement = _lookup_category(aqi_value)

    return AQIResult(
        aqi=aqi_value,
        category=category,
        responsible_pollutant=responsible_pollutant,
        sub_indices=sub_indices,
        health_statement=health_statement,
        is_valid=True,
        reason=None,
    )
