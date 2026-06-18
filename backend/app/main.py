"""
Feature:  Platform Bootstrap
Layer:    API / App Factory
Module:   app.main
Purpose:  FastAPI application factory. Registers all routers, middleware,
          and lifespan hooks (Vault secrets, DB engine, Redis, MLflow,
          LangSmith). Entry point for uvicorn.
Depends:  All routers, all middleware, infra.db.session, infra.cache.redis_client,
          infra.secrets.vault, app.core.config
HITL:     None — bootstrap only.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import mlflow
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    assistant,
    auth,
    catalog,
    chat,
    customers,
    dunning,
    hitl,
    invoices,
    network,
    notifications,
    procurement,
    search,
    storefront,
    suppliers,
    webhooks,
    widget,
)
from app.core.config import get_settings
from app.infra.cache.redis_client import close_redis, init_redis
from app.infra.db.session import configure_engine
from app.infra.scheduler import start_scheduler, stop_scheduler
from app.infra.secrets.vault import load_secrets
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.tenant import TenantMiddleware, set_jwt_public_key

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    # 1. Load secrets from Vault (hard fail if unreachable)
    secrets = load_secrets(settings)
    set_jwt_public_key(secrets.jwt_public_key)
    logger.info("vault_secrets_loaded")

    # 2. Configure DB engine
    configure_engine(settings.database_url)
    logger.info("db_engine_configured", url=settings.database_url.split("@")[-1])

    # 3. Init Redis
    await init_redis(settings.redis_url)
    logger.info("redis_initialized")

    # 4. MLflow tracking URI
    mlflow.set_tracking_uri("http://mlflow:5000")
    logger.info("mlflow_configured")

    # 5. LangSmith tracing
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = secrets.langsmith_api_key
    logger.info("langsmith_configured")

    # 6. Start dunning scheduler (Tracks 1/3/4 daily cron jobs)
    start_scheduler()
    logger.info("dunning_scheduler_started")

    yield

    # Shutdown
    stop_scheduler()
    await close_redis()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Mawrid AI Platform", lifespan=lifespan)

    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in [
        auth.router,
        catalog.router,
        procurement.router,
        dunning.router,
        invoices.router,
        suppliers.router,
        customers.router,
        hitl.router,
        network.router,
        notifications.router,
        assistant.router,
        search.router,
        chat.router,
        storefront.router,
        webhooks.router,
        admin.router,
        widget.router,
    ]:
        app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
