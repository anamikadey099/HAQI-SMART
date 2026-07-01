"""
Async database engine and session factory.

Uses SQLAlchemy 2.0 async API with asyncpg driver for PostgreSQL.
All DB operations throughout the application MUST use the async
session provided by ``get_session()``.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""

    pass


def _build_engine() -> AsyncEngine:
    """Create the async SQLAlchemy engine from application settings.

    Returns:
        An :class:`AsyncEngine` instance configured for asyncpg.
    """
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


engine: AsyncEngine = _build_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for dependency injection.

    Yields:
        An :class:`AsyncSession` that is automatically closed after use.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables defined via the ORM (development helper).

    In production, use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the async engine connection pool."""
    await engine.dispose()
