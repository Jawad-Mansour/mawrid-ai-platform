"""
Feature:  Database Migrations
Layer:    Infra / Alembic
Module:   alembic.env
Purpose:  Alembic async migration environment. Imports Base from
          app.infra.db.base (which pulls in all ORM models via session.py)
          to enable autogenerate. Reads DATABASE_URL from environment
          (set by Docker Compose or CI); falls back to alembic.ini.
Depends:  sqlalchemy[asyncio], asyncpg, alembic, app.infra.db.session
HITL:     None.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from app.infra.db import session as _session_module  # noqa: F401 — registers all models
from app.infra.db.base import Base
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Prefer DATABASE_URL env var; fall back to alembic.ini sqlalchemy.url
_url: str = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url") or ""


def run_migrations_offline() -> None:
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(_url)
    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda conn: context.configure(connection=conn, target_metadata=target_metadata)
        )
        async with connection.begin():
            await connection.run_sync(lambda _: context.run_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
