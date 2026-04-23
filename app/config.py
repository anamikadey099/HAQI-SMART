"""
app/config.py
-------------
Central configuration for HAQI-SMART.

All values can be overridden via environment variables or a .env file at the
project root.  Pydantic-Settings v2 is used so that:
  - Missing required fields raise a clear ValidationError on startup.
  - Type coercion (e.g. string → int) is handled automatically.
  - Secrets are never hard-coded in source control.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/haqi_smart"

    # ------------------------------------------------------------------
    # ML microservice  (external — never part of Docker Compose)
    # ------------------------------------------------------------------
    ML_SERVER_URL: str = "http://localhost:8001"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    APP_ENV: str = "development"   # development | production
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


# Module-level singleton — import this everywhere:
#   from app.config import settings
settings = Settings()
