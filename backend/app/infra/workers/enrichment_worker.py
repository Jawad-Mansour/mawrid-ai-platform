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
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job
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
        product.image_path = enriched.image_url or product.image_path
        product.source_urls = enriched.source_urls or product.source_urls
        product.enrichment_source = enriched.enrichment_source
        product.enrichment_confidence = enriched.enrichment_confidence
        product.currency = enriched.currency or product.currency

        # Human-in-the-loop gate: anything we couldn't confidently enrich goes to a
        # human instead of being shown as a confident catalog entry. We require a real
        # image, a substantial description, and enough specifications.
        desc = enriched.description or ""
        spec_count = len(enriched.specifications or {})
        is_uncertain = (
            enriched.image_url is None
            or len(desc) < 220  # noqa: PLR2004
            or spec_count < 5  # noqa: PLR2004
            or enriched.enrichment_confidence == "partial"
        )
        product.enrichment_status = "needs_review" if is_uncertain else "enriched"

        # Only enriched (confident) products get embedded for semantic search.
        if product.enrichment_status == "enriched":
            await outbox_repo.create(
                event_type="embedding_requested",
                payload={"product_id": product_id, "tenant_id": tenant_id},
            )

        await session.flush()

    logger.info(
        "enrich_job_complete",
        product_id=product_id,
        status=product.enrichment_status,
        has_image=enriched.image_url is not None,
    )
    return {"status": "success", "enrichment_status": product.enrichment_status}


# ── Idempotent enqueue ────────────────────────────────────────────────────────


async def enqueue_enrichment(
    redis: ArqRedis,
    *,
    tenant_id: str,
    product_hash: str,
    product_id: str | None = None,
    raw_text: str | None = None,
) -> Job:
    """
    Enqueue an enrichment job keyed on product_hash. ARQ dedups on _job_id, so
    submitting the same product_hash twice returns a handle to the SAME job
    (no duplicate enrichment). The worker is also idempotent at the DB level
    (skips already-enriched products). raw_text is accepted for call-site
    convenience; the worker loads the product from the DB by product_id.
    """
    job_id = f"enrich:{tenant_id}:{product_hash}"
    job = await redis.enqueue_job(
        "enrich_product",
        tenant_id=tenant_id,
        product_id=product_id or product_hash,
        _job_id=job_id,
    )
    # enqueue_job returns None if a job with this _job_id is already queued —
    # return a handle to the existing job so callers always get a stable id.
    return job if job is not None else Job(job_id, redis)


# ── Lifecycle hooks ───────────────────────────────────────────────────────────


async def startup(ctx: dict[str, object]) -> None:
    """Load Vault secrets and create DB session factory once per worker process."""
    settings = get_settings()
    load_secrets(settings)
    engine: AsyncEngine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    ctx["engine"] = engine
    ctx["session_factory"] = async_sessionmaker(engine, expire_on_commit=False)
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
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    job_timeout = 300
    # Enrich a couple at a time, not 10 — deep per-product web/image search would
    # otherwise hammer SearXNG and the image lookups fail under load (products end up
    # with no image). Low concurrency = the accurate, "one-by-one" behaviour we want.
    max_jobs = 2
    max_tries = 3
