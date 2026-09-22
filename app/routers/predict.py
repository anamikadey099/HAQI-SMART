"""
Predict router — ML prediction proxy endpoint.

Forwards prediction requests to the external ML server via
``ml_client.py``. Returns graceful error responses if the
ML server is unreachable (never propagates 500s).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.auth.jwt import get_current_user, TokenData
from app.schemas.aqi import APIResponse, ErrorDetail
from app.schemas.ml import PredictRequest, PredictResponse

router = APIRouter(tags=["ML Proxy"])


@router.post("/predict", response_model=APIResponse[PredictResponse])
async def predict_aqi(
    payload: PredictRequest,
    _user: TokenData = Depends(get_current_user),
) -> APIResponse[PredictResponse]:
    """Forward a prediction request to the ML server.

    Sends node context and current pollutant readings to the
    external ML predict endpoint and returns the predicted AQI.

    Args:
        payload: Prediction input data.
        _user: Authenticated user (JWT).

    Returns:
        APIResponse with predicted AQI, confidence, and category.
        On ML server failure, returns success=False with error details.
    """
    from app.services.ml_client import predict

    result = await predict(
        node_id=str(payload.node_id),
        pm25=payload.pm25,
        pm10=payload.pm10,
        temperature=payload.temperature,
        humidity=payload.humidity,
        no2=payload.no2,
        so2=payload.so2,
        co=payload.co,
        o3=payload.o3,
        nh3=payload.nh3,
    )

    if result is None:
        return APIResponse(
            success=False,
            error=ErrorDetail(
                code="ML_UNAVAILABLE",
                message="ML prediction server is unreachable. Please try again later.",
            ),
            timestamp=datetime.now(timezone.utc),
        )

    return APIResponse(
        success=True,
        data=PredictResponse(
            predicted_aqi=result["predicted_aqi"],
            confidence=result["confidence"],
            category=result["category"],
        ),
        timestamp=datetime.now(timezone.utc),
    )
