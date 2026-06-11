"""
Feature:  Catalog Enrichment Pipeline
Layer:    Infra / Workers
Module:   app.infra.workers.enrichment_worker
Purpose:  ARQ worker for async enrichment. Jobs keyed on product_id —
          idempotent: already-enriched products are skipped. On success,
          product update and outbox embedding event are written in ONE transaction.
          Runs as a separate Docker process (not part of the FastAPI app).
Depends:  arq, app.core.catalog.enrichment_pipeline, app.infra.db.repos.*,
          app.infra.secrets.vault
HITL:     None — enrichment is internal.
"""

from __future__ import annotations

import os

import structlog
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.catalog.enrichment_pipeline import EnrichmentInput, build_pipeline
from app.core.config import get_settings
from app.infra.db.repos.outbox_repo import OutboxRepository
from app.infra.db.repos.product_repo import ProductRepository
from app.infra.secrets.vault import get_secrets, load_secrets

logger = structlog.get_logger(__name__)


async def enrich_product(
    ctx: dict[str, object],
    *,
    tenant_id: str,
    product_id: str,
) -> dict[str, object]:
    """
    ARQ job: run 5-step enrichment for a single product.
    Idempotent — skips products with enrichment_status == 'enriched'.
    Writes outbox event atomically with product update.
    """
    session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]  # type: ignore[assignment]

    async with session_factory() as session, session.begin():
        product_repo = ProductRepository(session, tenant_id)
        outbox_repo = OutboxRepository(session, tenant_id)

        product = await product_repo.get_by_id(product_id)
        if product is None:
            logger.warning("enrich_job_not_found", product_id=product_id)
            return {"status": "skipped", "reason": "product_not_found"}

        if product.enrichment_status == "enriched":
            logger.info("enrich_job_already_done", product_id=product_id)
            return {"status": "skipped", "reason": "already_enriched"}

        secrets = get_secrets()
        settings = get_settings()
        pipeline = build_pipeline(
            icecat_api_key=secrets.icecat_api_key,
            searxng_base_url=settings.searxng_base_url,
        )

        existing_specs: dict[str, str] = {}
        if isinstance(product.specifications, dict):
            existing_specs = {str(k): str(v) for k, v in product.specifications.items()}

        enriched = await pipeline.run(
            EnrichmentInput(
                product_name=product.product_name,
                sku=product.sku,
                barcode=product.barcode,
                specifications=existing_specs,
            )
        )

        product.description = enriched.description or None
        product.specifications = enriched.specifications or None
        product.enrichment_source = enriched.enrichment_source
        product.enrichment_confidence = enriched.enrichment_confidence
        product.currency = enriched.currency
        product.enrichment_status = "enriched"

        # Atomic: outbox event written in the same transaction as product update
        await outbox_repo.create(
            event_type="embedding_requested",
            payload={"product_id": product_id, "tenant_id": tenant_id},
        )

        await session.flush()

    logger.info("enrich_job_complete", product_id=product_id)
    return {"status": "success"}


# ── Lifecycle hooks ───────────────────────────────────────────────────────────


async def startup(ctx: dict[str, object]) -> None:
    """Load Vault secrets and create DB session factory once per worker process."""
    settings = get_settings()
    load_secrets(settings)
    engine: AsyncEngine = create_async_engine(
        settings.database_url, echo=False, pool_pre_ping=True
    )
    ctx["engine"] = engine
    ctx["session_factory"] = async_sessionmaker(bind=engine, expire_on_commit=False)
    logger.info("enrichment_worker_started")


async def shutdown(ctx: dict[str, object]) -> None:
    engine = ctx.get("engine")
    if isinstance(engine, AsyncEngine):
        await engine.dispose()
    logger.info("enrichment_worker_stopped")


# ── WorkerSettings ────────────────────────────────────────────────────────────


class WorkerSettings:
    functions = [enrich_product]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    )
    job_timeout = 300
    max_jobs = 10
