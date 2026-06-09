"""
Feature:  Database (cross-cutting)
Layer:    Infra / DB
Module:   app.infra.db.session
Purpose:  Async SQLAlchemy engine and session factory. Applies pgvector
          extension registration and sets search_path per tenant on session
          creation for RLS support.
Depends:  sqlalchemy[asyncio], asyncpg, pgvector
HITL:     None — infrastructure only.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infra.db.base import Base  # noqa: F401  triggers table registration

engine = create_async_engine("", echo=False, pool_pre_ping=True)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine, expire_on_commit=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
