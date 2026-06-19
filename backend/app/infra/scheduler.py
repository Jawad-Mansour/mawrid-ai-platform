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
from apscheduler.triggers.interval import IntervalTrigger

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


async def _run_network_refresh() -> None:
    """Each morning, keep the Supplier Network map fresh: geocode any saved/discovered
    suppliers that still lack coordinates so they appear as real map pins. Best-effort
    per tenant — one failure never blocks others."""
    from sqlalchemy import select  # noqa: PLC0415

    from app.infra.db.models.supplier import Supplier  # noqa: PLC0415
    from app.infra.db.repos.tenant_repo import TenantRepo  # noqa: PLC0415
    from app.infra.db.session import get_session_factory  # noqa: PLC0415
    from app.infra.geo.geocode import geocode  # noqa: PLC0415

    factory = get_session_factory()
    async with factory() as session:
        tenant_ids = await TenantRepo(session).list_active_tenant_ids()

    for tenant_id in tenant_ids:
        try:
            async with factory() as session, session.begin():
                rows = (
                    await session.execute(
                        select(Supplier).where(
                            Supplier.tenant_id == tenant_id,
                            Supplier.latitude.is_(None),
                            Supplier.location.is_not(None),
                        )
                    )
                ).scalars().all()
                geocoded = 0
                for s in rows:
                    coords = await geocode(s.location)
                    if coords:
                        s.latitude, s.longitude = coords
                        s.region = s.region or "europe"
                        geocoded += 1
                # Logo agent: fill missing logos from websites (cheap, reliable).
                logo_rows = (
                    await session.execute(
                        select(Supplier).where(
                            Supplier.tenant_id == tenant_id,
                            Supplier.logo_url.is_(None),
                            Supplier.website.is_not(None),
                        )
                    )
                ).scalars().all()
                logos = 0
                for s in logo_rows:
                    dom = (s.website or "").replace("https://", "").replace("http://", "").split("/")[0]
                    if dom:
                        s.logo_url = f"https://logo.clearbit.com/{dom}"
                        logos += 1
                _log.info("scheduler_network_refresh", extra={"tenant_id": tenant_id, "geocoded": geocoded, "logos": logos})
        except Exception as exc:
            _log.error("scheduler_network_refresh_error", extra={"tenant_id": tenant_id, "error": str(exc)})


async def _run_arrival_check() -> None:
    """Each morning, notify on shipments arriving within the next 3 days so the importer
    can be ready to receive the container."""
    from datetime import timedelta  # noqa: PLC0415

    from sqlalchemy import select  # noqa: PLC0415

    from app.infra.db.models.order import Shipment  # noqa: PLC0415
    from app.infra.db.repos.notification_repo import record_event  # noqa: PLC0415
    from app.infra.db.repos.tenant_repo import TenantRepo  # noqa: PLC0415
    from app.infra.db.session import get_session_factory  # noqa: PLC0415

    today = date.today()
    soon = today + timedelta(days=3)
    factory = get_session_factory()
    async with factory() as session:
        tenant_ids = await TenantRepo(session).list_active_tenant_ids()
    for tenant_id in tenant_ids:
        try:
            async with factory() as session, session.begin():
                rows = (
                    await session.execute(
                        select(Shipment).where(
                            Shipment.tenant_id == tenant_id,
                            Shipment.expected_arrival_date.is_not(None),
                            Shipment.expected_arrival_date <= soon,
                            Shipment.status != "arrived",
                        )
                    )
                ).scalars().all()
                for s in rows:
                    await record_event(
                        session, tenant_id, kind="arrival_due",
                        title="Container arriving soon",
                        body=f"A shipment is due by {s.expected_arrival_date}. Get ready to receive it.",
                        link="/inventory/shipments",
                    )
        except Exception as exc:
            _log.error("scheduler_arrival_check_error", extra={"tenant_id": tenant_id, "error": str(exc)})


async def _run_inbound_poll() -> None:
    """Every few minutes, pull supplier replies from the operator mailbox (IMAP) and
    thread + comprehend them. Graceful no-op when IMAP creds are absent in Vault."""
    from app.infra.db.session import get_session_factory  # noqa: PLC0415
    from app.infra.email.inbound import poll_and_ingest  # noqa: PLC0415

    try:
        result = await poll_and_ingest(get_session_factory())
        if result.get("enabled"):
            _log.info("scheduler_inbound_poll", extra=result)
    except Exception as exc:  # noqa: BLE001
        _log.error("scheduler_inbound_poll_error", extra={"error": str(exc)})


async def _run_gmail_poll() -> None:
    """Every few minutes, pull supplier replies from each tenant's CONNECTED Gmail (OAuth)
    and thread + comprehend them. No-op when no tenant has connected Gmail."""
    from app.infra.db.session import get_session_factory  # noqa: PLC0415
    from app.infra.email.gmail import gmail_poll_and_ingest  # noqa: PLC0415

    try:
        result = await gmail_poll_and_ingest(get_session_factory())
        if result.get("enabled"):
            _log.info("scheduler_gmail_poll", extra=result)
    except Exception as exc:  # noqa: BLE001
        _log.error("scheduler_gmail_poll_error", extra={"error": str(exc)})


def start_scheduler() -> None:
    """Start the APScheduler. Called from app lifespan startup."""
    global _scheduler
    _scheduler = _make_scheduler()

    _scheduler.add_job(
        _run_inbound_poll,
        IntervalTrigger(minutes=2),
        id="inbound_email_poll",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=120,
    )
    _scheduler.add_job(
        _run_gmail_poll,
        IntervalTrigger(minutes=2),
        id="gmail_email_poll",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=120,
    )

    _scheduler.add_job(
        _run_network_refresh,
        CronTrigger(hour=6, minute=30),
        id="network_refresh_daily",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _run_arrival_check,
        CronTrigger(hour=6, minute=45),
        id="arrival_check_daily",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

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
    logger.info("scheduler_started", jobs=7)


def stop_scheduler() -> None:
    """Graceful shutdown. Called from app lifespan teardown."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("dunning_scheduler_stopped")
    _scheduler = None
