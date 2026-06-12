"""
Feature:  Database (cross-cutting)
Layer:    Infra / DB
Module:   app.infra.db.session
Purpose:  Async SQLAlchemy engine and session factory. Engine is lazily
          initialized via configure_engine() called from app lifespan.
          Importing all models here triggers Base.metadata population for Alembic.
Depends:  sqlalchemy[asyncio], asyncpg, pgvector, app.infra.db.base
HITL:     None — infrastructure only.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.infra.db.models.customer  # noqa: F401
import app.infra.db.models.document  # noqa: F401
import app.infra.db.models.dunning  # noqa: F401
import app.infra.db.models.graph  # noqa: F401
import app.infra.db.models.hitl  # noqa: F401
import app.infra.db.models.order  # noqa: F401
import app.infra.db.models.outbox  # noqa: F401
import app.infra.db.models.product  # noqa: F401
import app.infra.db.models.product_chunks  # noqa: F401
import app.infra.db.models.review_queue  # noqa: F401
import app.infra.db.models.storefront  # noqa: F401
import app.infra.db.models.supplier  # noqa: F401

# Import all models so Alembic autogenerate finds them
import app.infra.db.models.tenant  # noqa: F401
from app.infra.db.base import Base  # noqa: F401  triggers table registration

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_engine(url: str) -> None:
    global _engine, _session_factory
    _engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    _session_factory = async_sessionmaker(bind=_engine, expire_on_commit=False)


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call configure_engine() in lifespan.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call configure_engine() in lifespan.")
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call configure_engine() in lifespan.")
    async with _session_factory() as session:
        yield session
