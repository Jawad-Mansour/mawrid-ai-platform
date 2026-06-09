"""
Feature:  Database Migrations
Layer:    Infra / Alembic
Module:   alembic.env
Purpose:  Alembic async migration environment. Imports Base from
          app.infra.db.base (which pulls in all ORM models) to enable
          autogenerate. Runs migrations in async context with asyncpg driver.
          DATABASE_URL injected from env — no hardcoded credentials.
Depends:  sqlalchemy[asyncio], asyncpg, alembic, app.infra.db.base
HITL:     None.
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from app.infra.db.base import Base
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url") or "")
    async with connectable.connect() as connection:
        await connection.run_sync(lambda conn: context.configure(connection=conn, target_metadata=target_metadata))
        async with connection.begin():
            await connection.run_sync(lambda _: context.run_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
