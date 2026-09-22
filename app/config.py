"""
Application configuration — Pydantic BaseSettings.

Reads all configuration from environment variables (or ``.env`` file).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central application configuration.

    All values are read from environment variables. A ``.env`` file in
    the project root is loaded automatically.

    Attributes:
        DATABASE_URL: Async PostgreSQL connection string (asyncpg driver).
        ML_SERVER_URL: Base URL of the external ML prediction server.
        SECRET_KEY: Secret key for JWT token signing.
        ALGORITHM: JWT signing algorithm (default: HS256).
        ACCESS_TOKEN_EXPIRE_MINUTES: JWT token lifetime in minutes.
        API_KEY_HEADER: HTTP header name for sensor node API key auth.
    """

    DATABASE_URL: str = "postgresql+asyncpg://haqi:haqi@localhost:5432/haqi"
    ML_SERVER_URL: str = "http://localhost:9000"
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    API_KEY_HEADER: str = "X-API-Key"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings: Settings = Settings()
