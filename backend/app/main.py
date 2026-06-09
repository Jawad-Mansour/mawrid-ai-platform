"""
Feature:  Platform Bootstrap
Layer:    API / App Factory
Module:   app.main
Purpose:  FastAPI application factory. Registers all routers, middleware,
          and lifespan hooks (ML model loading, scheduler start, DB engine,
          Redis client). Entry point for uvicorn.
Depends:  All routers, all middleware, infra.scheduler, infra.db.session,
          infra.llm.openai, infra.llm.embedder, app.rag.reranking
HITL:     None — bootstrap only.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    auth,
    catalog,
    chat,
    customers,
    dunning,
    hitl,
    invoices,
    procurement,
    search,
    storefront,
    suppliers,
    webhooks,
)
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.tenant import TenantMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: load ML models, connect DB, start scheduler
    yield
    # Shutdown: close connections, stop scheduler


def create_app() -> FastAPI:
    app = FastAPI(title="Mawrid AI Platform", lifespan=lifespan)

    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
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
        search.router,
        chat.router,
        storefront.router,
        webhooks.router,
        admin.router,
    ]:
        app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
