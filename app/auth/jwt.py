"""
JWT authentication and RBAC for dashboard / API consumers.

Supports two roles: ``admin`` and ``viewer``. Tokens are issued
via ``create_access_token()`` and verified with ``get_current_user()``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# ---- In-memory user store (replace with DB in production) ----

USERS_DB: dict[str, dict[str, str]] = {
    "admin": {"password": "admin123", "role": "admin"},
    "viewer": {"password": "viewer123", "role": "viewer"},
}


class TokenData(BaseModel):
    """Decoded JWT token payload.

    Attributes:
        username: Authenticated username.
        role: User role (``admin`` or ``viewer``).
    """

    username: str
    role: str


class TokenResponse(BaseModel):
    """Response from the ``/auth/token`` endpoint.

    Attributes:
        access_token: The JWT access token string.
        token_type: Token type (always ``bearer``).
    """

    access_token: str
    token_type: str = "bearer"


def create_access_token(
    data: dict[str, str],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Payload dict to encode (must include ``sub`` and ``role``).
        expires_delta: Optional custom expiry duration. Defaults to
            ``ACCESS_TOKEN_EXPIRE_MINUTES`` from settings.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> TokenData:
    """FastAPI dependency that decodes and validates a JWT token.

    Args:
        token: Bearer token from the ``Authorization`` header.

    Returns:
        :class:`TokenData` with the authenticated user's identity and role.

    Raises:
        HTTPException: 401 if the token is invalid or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: Optional[str] = payload.get("sub")
        role: Optional[str] = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        return TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception


def require_role(required_role: str):
    """Create a dependency that enforces a minimum RBAC role.

    Args:
        required_role: The role required to access the endpoint
            (``'admin'`` or ``'viewer'``).

    Returns:
        An async FastAPI dependency function.
    """

    async def role_checker(
        current_user: TokenData = Depends(get_current_user),
    ) -> TokenData:
        """Check that the current user has the required role.

        Raises:
            HTTPException: 403 if the user lacks the required role.
        """
        role_hierarchy = {"admin": 2, "viewer": 1}
        user_level = role_hierarchy.get(current_user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return current_user

    return role_checker
