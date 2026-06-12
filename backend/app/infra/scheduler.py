"""
Feature:  Dunning Engine (cross-cutting)
Layer:    Infra / Scheduler
Module:   app.infra.scheduler
Purpose:  APScheduler 3.x AsyncIOScheduler. Runs three daily dunning jobs:
            - Track 1 (payables advance)  at 07:00 UTC
            - Track 3 (B2B receivables)   at 07:05 UTC
            - Track 4 (B2C collections)   at 07:10 UTC
          Each job opens a new session for every active tenant and calls the
          corresponding dunning service trigger. Exceptions are caught per
          tenant so one failing tenant never blocks others.
          Started in app.main lifespan startup. Shutdown in lifespan teardown.
Depends:  apscheduler, app.core.dunning.services, app.infra.db.session,
          app.infra.db.repos.tenant_repo
HITL:     All downstream actions are HITL-gated in dunning services.
"""

from __future__ import annotations

import logging
from datetime import date

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = structlog.get_logger(__name__)
_log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _make_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler(timezone="UTC")


async def _run_track1() -> None:
    from app.core.dunning.services import trigger_track1  # noqa: PLC0415
    from app.infra.db.repos.tenant_repo import TenantRepo  # noqa: PLC0415
    from app.infra.db.session import get_session_factory  # noqa: PLC0415

    today = date.today()
    factory = get_session_factory()

    async with factory() as session:
        repo = TenantRepo(session)
        tenant_ids = await repo.list_active_tenant_ids()

    for tenant_id in tenant_ids:
        try:
            async with factory() as session, session.begin():
                created = await trigger_track1(session, tenant_id, today)
                _log.info(
                    "scheduler_track1_done",
                    extra={"tenant_id": tenant_id, "actions_created": len(created)},
                )
        except Exception as exc:
            _log.error(
                "scheduler_track1_error",
                extra={"tenant_id": tenant_id, "error": str(exc)},
            )


async def _run_track3() -> None:
    from app.core.dunning.services import trigger_track3  # noqa: PLC0415
    from app.infra.db.repos.tenant_repo import TenantRepo  # noqa: PLC0415
    from app.infra.db.session import get_session_factory  # noqa: PLC0415

    today = date.today()
    factory = get_session_factory()

    async with factory() as session:
        repo = TenantRepo(session)
        tenant_ids = await repo.list_active_tenant_ids()

    for tenant_id in tenant_ids:
        try:
            async with factory() as session, session.begin():
                created = await trigger_track3(session, tenant_id, today)
                _log.info(
                    "scheduler_track3_done",
                    extra={"tenant_id": tenant_id, "actions_created": len(created)},
                )
        except Exception as exc:
            _log.error(
                "scheduler_track3_error",
                extra={"tenant_id": tenant_id, "error": str(exc)},
            )


async def _run_track4() -> None:
    from app.core.dunning.services import trigger_track4  # noqa: PLC0415
    from app.infra.db.repos.tenant_repo import TenantRepo  # noqa: PLC0415
    from app.infra.db.session import get_session_factory  # noqa: PLC0415

    today = date.today()
    factory = get_session_factory()

    async with factory() as session:
        repo = TenantRepo(session)
        tenant_ids = await repo.list_active_tenant_ids()

    for tenant_id in tenant_ids:
        try:
            async with factory() as session, session.begin():
                created = await trigger_track4(session, tenant_id, today)
                _log.info(
                    "scheduler_track4_done",
                    extra={"tenant_id": tenant_id, "actions_created": len(created)},
                )
        except Exception as exc:
            _log.error(
                "scheduler_track4_error",
                extra={"tenant_id": tenant_id, "error": str(exc)},
            )


def start_scheduler() -> None:
    """Start the APScheduler. Called from app lifespan startup."""
    global _scheduler
    _scheduler = _make_scheduler()

    _scheduler.add_job(
        _run_track1,
        CronTrigger(hour=7, minute=0),
        id="dunning_track1_daily",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _run_track3,
        CronTrigger(hour=7, minute=5),
        id="dunning_track3_daily",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _run_track4,
        CronTrigger(hour=7, minute=10),
        id="dunning_track4_daily",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    logger.info("dunning_scheduler_started", jobs=3)


def stop_scheduler() -> None:
    """Graceful shutdown. Called from app lifespan teardown."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("dunning_scheduler_stopped")
    _scheduler = None
