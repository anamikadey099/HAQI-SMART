"""
Chart utilities — CPCB colour mapping and reusable Plotly chart builders.

All AQI colours in this module use the official CPCB hex codes.
Use ``get_aqi_colour()`` everywhere — never hardcode colour strings.
"""

from __future__ import annotations

from typing import Optional

import plotly.graph_objects as go
import pandas as pd

# ---------------------------------------------------------------------------
# CPCB official AQI hex colour palette
# ---------------------------------------------------------------------------

_AQI_COLOUR_BANDS: list[tuple[int, int, str]] = [
    (0,   50,  "#00B050"),   # Good
    (51,  100, "#92D050"),   # Satisfactory
    (101, 200, "#FFFF00"),   # Moderate
    (201, 300, "#FF7E00"),   # Poor
    (301, 400, "#FF0000"),   # Very Poor
    (401, 500, "#7E0023"),   # Severe
]

_CATEGORY_COLOURS: dict[str, str] = {
    "Good":         "#00B050",
    "Satisfactory": "#92D050",
    "Moderate":     "#FFFF00",
    "Poor":         "#FF7E00",
    "Very Poor":    "#FF0000",
    "Severe":       "#7E0023",
}


def get_aqi_colour(aqi: float) -> str:
    """Return the CPCB hex colour for a given AQI value.

    Args:
        aqi: Numeric AQI value (0–500+).

    Returns:
        CPCB hex colour string (e.g. ``'#00B050'`` for Good).
    """
    for lo, hi, colour in _AQI_COLOUR_BANDS:
        if lo <= aqi <= hi:
            return colour
    return "#7E0023"  # Severe fallback for values above 500


def get_category_colour(category: str) -> str:
    """Return CPCB hex colour for a category label.

    Args:
        category: CPCB category name (e.g. ``'Good'``, ``'Severe'``).

    Returns:
        Hex colour string.
    """
    return _CATEGORY_COLOURS.get(category, "#7E0023")


def build_aqi_gauge(aqi: float, node_name: str) -> go.Figure:
    """Build a Plotly indicator gauge for a single node's AQI value.

    The gauge is coloured using CPCB hex codes for each band.

    Args:
        aqi: Current AQI value (0–500).
        node_name: Human-readable node name shown as the gauge title.

    Returns:
        A Plotly :class:`go.Figure` with an indicator gauge.
    """
    colour = get_aqi_colour(aqi)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=aqi,
            title={"text": node_name, "font": {"size": 16}},
            gauge={
                "axis": {"range": [0, 500], "tickwidth": 1},
                "bar": {"color": colour, "thickness": 0.3},
                "steps": [
                    {"range": [0,   50],  "color": "#00B050"},
                    {"range": [51,  100], "color": "#92D050"},
                    {"range": [101, 200], "color": "#FFFF00"},
                    {"range": [201, 300], "color": "#FF7E00"},
                    {"range": [301, 400], "color": "#FF0000"},
                    {"range": [401, 500], "color": "#7E0023"},
                ],
                "threshold": {
                    "line": {"color": "white", "width": 4},
                    "thickness": 0.75,
                    "value": aqi,
                },
            },
        )
    )
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
    )
    return fig


def build_sub_index_bar(
    sub_indices: dict[str, float],
    responsible_pollutant: Optional[str] = None,
) -> go.Figure:
    """Build a horizontal bar chart of pollutant sub-indices.

    The responsible (max) pollutant bar is highlighted in red.
    All other bars use the CPCB colour for their respective AQI band.

    Args:
        sub_indices: Dict of pollutant name → sub-index value.
        responsible_pollutant: Pollutant key with the highest sub-index.

    Returns:
        A Plotly :class:`go.Figure` horizontal bar chart.
    """
    pollutants = list(sub_indices.keys())
    values = list(sub_indices.values())
    colours = [
        "#FF0000" if p == responsible_pollutant else get_aqi_colour(v)
        for p, v in zip(pollutants, values)
    ]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=[p.upper() for p in pollutants],
            orientation="h",
            marker_color=colours,
            text=[f"{v:.1f}" for v in values],
            textposition="auto",
        )
    )
    fig.update_layout(
        title="Sub-Index Breakdown",
        xaxis=dict(title="AQI Sub-Index", range=[0, 500]),
        height=300,
        margin=dict(l=60, r=20, t=40, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
    )
    return fig


def build_aqi_timeseries(
    df: pd.DataFrame,
    node_ids: Optional[list[str]] = None,
) -> go.Figure:
    """Build a multi-node AQI time-series with CPCB category bands.

    Horizontal shaded bands show CPCB AQI categories in the background.

    Args:
        df: DataFrame with columns ``timestamp``, ``node_id``, ``aqi``.
        node_ids: Optional list of node IDs to include. All if ``None``.

    Returns:
        A Plotly :class:`go.Figure` with traces per node and category bands.
    """
    fig = go.Figure()

    # CPCB category background bands
    band_config = [
        (0,   50,  "#00B050", "Good"),
        (51,  100, "#92D050", "Satisfactory"),
        (101, 200, "#FFFF00", "Moderate"),
        (201, 300, "#FF7E00", "Poor"),
        (301, 400, "#FF0000", "Very Poor"),
        (401, 500, "#7E0023", "Severe"),
    ]
    for lo, hi, colour, label in band_config:
        fig.add_hrect(
            y0=lo, y1=hi,
            fillcolor=colour,
            opacity=0.08,
            line_width=0,
            annotation_text=label,
            annotation_position="right",
            annotation=dict(font_size=10, font_color=colour),
        )

    # One line trace per node
    if node_ids:
        df = df[df["node_id"].isin(node_ids)]

    for node_id, group in df.groupby("node_id"):
        node_colour = get_aqi_colour(group["aqi"].mean())
        fig.add_trace(
            go.Scatter(
                x=group["timestamp"],
                y=group["aqi"],
                mode="lines+markers",
                name=str(node_id)[:8],
                line=dict(color=node_colour, width=2),
                marker=dict(size=4),
            )
        )

    fig.update_layout(
        title="AQI Time Series",
        xaxis_title="Time",
        yaxis_title="AQI",
        yaxis=dict(range=[0, 500]),
        height=400,
        legend=dict(orientation="h"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16,16,32,0.5)",
        font={"color": "white"},
    )
    return fig
