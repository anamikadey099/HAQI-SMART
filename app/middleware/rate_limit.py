"""
Rate limiting middleware using SlowAPI.

Applies per-node API key rate limiting on the ingest endpoint
(100 requests/minute per key). Uses the ``X-API-Key`` header
as the rate limit identity.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import settings


def _get_api_key_or_ip(request: Request) -> str:
    """Extract the rate-limit identity from the request.

    Uses the API key header if present, otherwise falls back to
    the client's IP address.

    Args:
        request: The incoming Starlette/FastAPI request.

    Returns:
        A string identifier for rate limiting.
    """
    api_key = request.headers.get(settings.API_KEY_HEADER)
    if api_key:
        return api_key
    return get_remote_address(request)


limiter = Limiter(key_func=_get_api_key_or_ip)
