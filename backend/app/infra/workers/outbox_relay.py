"""
Feature:  Catalog Enrichment Pipeline (Outbox Pattern)
Layer:    Infra / Workers
Module:   app.infra.workers.outbox_relay
Purpose:  Outbox relay. Drains pending outbox events, generates OpenAI
          text-embedding-3-small (1536-dim) vectors, writes to products.embedding.
          Crash-safe: FOR UPDATE SKIP LOCKED prevents duplicate processing;
          processed flag set atomically with the embedding write.
          process_pending_events() is public and used directly by integration tests.
Depends:  app.infra.db.repos.outbox_repo, app.infra.db.repos.product_repo,
          app.infra.vector.embedder, app.infra.db.session
HITL:     None — relay is internal.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy import update as sqla_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infra.db.models.outbox import OutboxEvent
from app.infra.db.models.product import Product
from app.infra.db.repos.outbox_repo import OutboxRepository
from app.infra.db.repos.product_repo import ProductRepository
from app.infra.vector.embedder import embed

logger = structlog.get_logger(__name__)

_POLL_INTERVAL = 5.0


def _build_embed_text(product: Product) -> str:
    parts: list[str] = [product.product_name]
    if product.description:
        parts.append(product.description)
    if isinstance(product.specifications, dict):
        for key, value in product.specifications.items():
            parts.append(f"{key}: {value}")
    return " | ".join(parts)


async def process_pending_events(session: AsyncSession, tenant_id: str) -> int:
    """
    Process one batch of pending outbox events for a specific tenant.
    Returns number of events processed. Public for integration tests.
    """
    outbox_repo = OutboxRepository(session, tenant_id)
    product_repo = ProductRepository(session, tenant_id)

    events = await outbox_repo.get_pending_batch()
    processed_count = 0

    for event in events:
        try:
            if event.event_type == "embedding_requested":
                product_id = str(event.payload.get("product_id", ""))
                if product_id:
                    product = await product_repo.get_by_id(product_id)
                    if product is not None:
                        vector = await embed(_build_embed_text(product))
                        await session.execute(
                            sqla_update(Product)
                            .where(Product.product_id == product_id)
                            .values(embedding=vector)
                        )

            await outbox_repo.mark_processed(event.event_id)
            await session.flush()
            processed_count += 1
            logger.info(
                "outbox_event_processed",
                event_id=event.event_id,
                event_type=event.event_type,
            )

        except Exception as exc:
            logger.error(
                "outbox_event_failed",
                event_id=event.event_id,
                error=str(exc),
            )

    return processed_count


async def run_relay(
    session_factory: async_sessionmaker[AsyncSession],
    poll_interval: float = _POLL_INTERVAL,
) -> None:
    """
    Main relay loop. Runs indefinitely; each round opens its own transaction
    so SKIP LOCKED leases are released between batches.
    Cross-tenant: processes events for all tenants (privileged background process).
    """
    logger.info("outbox_relay_started", poll_interval=poll_interval)

    while True:
        try:
            async with session_factory() as session, session.begin():
                result = await session.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.processed == False)  # noqa: E712
                    .order_by(OutboxEvent.created_at)
                    .limit(50)
                    .with_for_update(skip_locked=True)
                )
                events = list(result.scalars().all())

                for event in events:
                    try:
                        if event.event_type == "embedding_requested":
                            product_id = str(event.payload.get("product_id", ""))
                            if product_id:
                                prod_result = await session.execute(
                                    select(Product).where(
                                        Product.product_id == product_id
                                    )
                                )
                                product = prod_result.scalar_one_or_none()
                                if product is not None:
                                    vector = await embed(_build_embed_text(product))
                                    await session.execute(
                                        sqla_update(Product)
                                        .where(Product.product_id == product_id)
                                        .values(embedding=vector)
                                    )

                        await session.execute(
                            sqla_update(OutboxEvent)
                            .where(OutboxEvent.event_id == event.event_id)
                            .values(
                                processed=True,
                                processed_at=datetime.now(tz=UTC),
                            )
                        )
                        logger.info(
                            "relay_event_processed",
                            event_id=event.event_id,
                            event_type=event.event_type,
                        )

                    except Exception as exc:
                        logger.error(
                            "relay_event_failed",
                            event_id=event.event_id,
                            error=str(exc),
                        )

        except Exception as exc:
            logger.error("relay_round_failed", error=str(exc))

        await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import get_settings
    from app.infra.secrets.vault import load_secrets

    _settings = get_settings()
    load_secrets(_settings)
    _engine = create_async_engine(_settings.database_url, pool_pre_ping=True)
    _factory = async_sessionmaker(_engine, expire_on_commit=False)
    asyncio.run(run_relay(_factory))
