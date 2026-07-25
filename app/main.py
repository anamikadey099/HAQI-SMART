"""
FastAPI application factory — HAQI-SMART backend.

Registers all routers, middleware, Prometheus metrics endpoint,
rate limiter, and the APScheduler aggregation worker via the
``lifespan`` context manager.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.auth.jwt import USERS_DB, TokenResponse, create_access_token
from app.database import close_db, init_db
from app.middleware.metrics import haqi_hotspot_active  # ensure metrics registered
from app.middleware.rate_limit import limiter
from app.routers import aqi, anomaly, health, hotspots, ingest, predict
from app.schemas.aqi import APIResponse, ErrorDetail
from app.services.aggregator import run_aggregation, scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Startup:
    - Initialises the database connection pool.
    - Starts the APScheduler aggregation worker (every 5 minutes).

    Shutdown:
    - Stops the scheduler gracefully.
    - Disposes of the database engine.
    """
    logger.info("HAQI-SMART backend starting up…")

    # Start aggregation scheduler
    scheduler.add_job(
        run_aggregation,
        trigger="interval",
        minutes=5,
        id="aggregation_worker",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler started — aggregation every 5 minutes")

    yield

    logger.info("HAQI-SMART backend shutting down…")
    scheduler.shutdown(wait=False)
    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Returns:
        Configured :class:`FastAPI` application.
    """
    app = FastAPI(
        title="HAQI-SMART API",
        description="Real-time Air Quality Index monitoring platform",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ---- Middleware ----
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Routers ----
    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(aqi.router)
    app.include_router(predict.router)
    app.include_router(anomaly.router)
    app.include_router(hotspots.router)

    # ---- Auth token endpoint ----
    @app.post("/auth/token", response_model=TokenResponse, tags=["Auth"])
    async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
        """Issue a JWT access token on successful login.

        Args:
            form_data: OAuth2 form request containing username and password.

        Returns:
            JWT ``TokenResponse`` on success.
        """
        username = form_data.username
        password = form_data.password
        user = USERS_DB.get(username)
        if not user or user["password"] != password:
            return JSONResponse(
                status_code=401,
                content=APIResponse(
                    success=False,
                    error=ErrorDetail(code="AUTH_FAILED", message="Invalid credentials"),
                    timestamp=datetime.now(timezone.utc),
                ).model_dump(mode="json"),
            )
        token = create_access_token({"sub": username, "role": user["role"]})
        return TokenResponse(access_token=token)

    # ---- Prometheus metrics endpoint ----
    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        """Expose Prometheus metrics at ``/metrics``.

        Returns:
            Plain-text Prometheus exposition format.
        """
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # ---- Global exception handler ----
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all handler that returns the APIResponse envelope instead of 500."""
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content=APIResponse(
                success=False,
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred",
                ),
                timestamp=datetime.now(timezone.utc),
            ).model_dump(mode="json"),
        )

    return app


app = create_app()
