"""
Feature:  All features — Integration Test Infrastructure
Layer:    Test / Integration
Module:   tests.integration.conftest
Purpose:  Shared fixtures for integration tests. Spins up a real test database
          (Postgres + pgvector), Redis, and MinIO using the Docker Compose
          test profile. Cleans state between tests via truncation (not drop).
          LLM is still mocked — integration tests own DB + Redis, not LLM.
Depends:  pytest, sqlalchemy, asyncpg, redis, app.infra.db
HITL:     None
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Async SQLAlchemy engine pointed at the test database."""
    import os

    from sqlalchemy.ext.asyncio import create_async_engine

    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://mawrid:password@localhost:5432/mawrid_test",
    )
    engine = create_async_engine(url, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator:
    """Transactional session. Rolls back after each test."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(db_engine, expire_on_commit=False) as session, session.begin():
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="session")
async def redis_client():
    """Real Redis client for integration tests."""
    import os

    import redis.asyncio as aioredis

    url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    client = aioredis.from_url(url)
    yield client
    await client.aclose()


@pytest.fixture
def tenant_id() -> str:
    return "tenant_test_001"


@pytest.fixture
def user_id() -> str:
    return "user_test_001"
