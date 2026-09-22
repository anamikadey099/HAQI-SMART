"""
API Key authentication for sensor nodes.

Sensor nodes authenticate via a hashed API key sent in the
``X-API-Key`` HTTP header. The key is compared against the
SHA-256 hash stored in the ``nodes`` table.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.node import Node

api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


def hash_api_key(raw_key: str) -> str:
    """Hash a raw API key using SHA-256.

    Args:
        raw_key: The plaintext API key.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
    session: AsyncSession = Depends(get_session),
) -> Node:
    """FastAPI dependency that validates an API key against the database.

    Args:
        api_key: Raw API key from the request header.
        session: Async database session (injected).

    Returns:
        The :class:`Node` ORM instance matching the API key.

    Raises:
        HTTPException: 401 if the key is missing or not found.
        HTTPException: 403 if the node is inactive.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key in header",
        )

    key_hash = hash_api_key(api_key)
    result = await session.execute(
        select(Node).where(Node.api_key_hash == key_hash)
    )
    node = result.scalar_one_or_none()

    if node is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not node.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Node is deactivated",
        )

    return node
