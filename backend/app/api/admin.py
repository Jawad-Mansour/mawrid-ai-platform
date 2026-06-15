"""
Feature:  Admin Operations Dashboard
Layer:    API / Router
Module:   app.api.admin
Purpose:  Operations dashboard endpoints: aggregate stats summary, AI model
          health (MLflow registry + eval thresholds), n8n workflow status,
          consumer order management, and enrichment DLQ inspection + retry.
          All endpoints are tenant-scoped via CurrentUser.
Depends:  app.infra.db.repos.*, app.api.deps, app.core.config, arq, httpx
HITL:     fulfillment_notification (consumer order fulfill endpoint)
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import structlog
import yaml
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.core.config import get_settings
from app.infra.db.repos.consumer_order_repo import ConsumerOrderRepository
from app.infra.db.repos.hitl_repo import HITLRepository
from app.infra.db.repos.invoice_repo import InvoiceRepository
from app.infra.db.repos.product_repo import ProductRepository
from app.infra.db.repos.shipment_repo import ShipmentRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_ACTIVE_SHIPMENT_STATUSES = {"shipped", "in_transit", "at_customs"}

_EVAL_THRESHOLDS_PATH = (
    Path(__file__).parent.parent.parent / "ml_config" / "eval_thresholds.yaml"
)

# ── Response models ────────────────────────────────────────────────────────────


class DashboardSummary(StrictModel):
    published_products: int
    enriched_products: int
    pending_enrichment: int
    failed_enrichment: int
    low_stock_count: int
    active_shipments: int
    total_invoices: int
    overdue_invoices: int
    outstanding_receivables: float
    pending_hitl_count: int
    consumer_orders_pending: int
    generated_at: str


class ModelHealth(StrictModel):
    name: str
    status: str
    latest_version: str | None = None
    stage: str | None = None


class AIHealthResponse(StrictModel):
    models: list[ModelHealth]
    eval_thresholds: dict[str, Any]
    drift_status: str
    checked_at: str


class WorkflowStatus(StrictModel):
    workflow_id: str
    name: str
    active: bool
    last_execution_status: str | None = None
    last_execution_at: str | None = None


class N8nStatusResponse(StrictModel):
    status: str
    workflows: list[WorkflowStatus]


class ConsumerOrderResponse(StrictModel):
    order_id: str
    customer_id: str
    status: str
    payment_gateway: str
    total_amount: float
    created_at: str


class FulfillResponse(StrictModel):
    hitl_action_id: str
    action_type: str
    status: str
    detail: str


class DLQProductResponse(StrictModel):
    product_id: str
    product_name: str
    enrichment_status: str


# ── Helpers ────────────────────────────────────────────────────────────────────


_LAST_DRIFT_CHECK_PATH = (
    Path(__file__).parent.parent.parent / "ml_config" / "last_drift_check.json"
)


def _load_eval_thresholds() -> dict[str, Any]:
    try:
        with open(_EVAL_THRESHOLDS_PATH) as f:
            return dict(yaml.safe_load(f))
    except Exception:
        return {}


def _run_drift_status() -> str:
    """
    Read the last drift check result written by nightly CI Gate 9.
    Returns "ok" if no check has been run yet or the check passed,
    "warning" / "severe" if the nightly check detected drift.
    File format: {"status": "ok"|"warning"|"severe", "checked_at": "..."}
    """
    import json  # noqa: PLC0415

    try:
        if _LAST_DRIFT_CHECK_PATH.exists():
            data = json.loads(_LAST_DRIFT_CHECK_PATH.read_text())
            return str(data.get("status", "ok"))
    except Exception:
        pass
    return "ok"


async def _query_mlflow_models(tracking_uri: str) -> list[ModelHealth]:
    known_models = ["tone_classifier", "supplier_scorer", "intent_tier1"]
    results: list[ModelHealth] = []

    try:
        import mlflow  # noqa: PLC0415

        mlflow.set_tracking_uri(tracking_uri)
        client = mlflow.MlflowClient()
        for model_name in known_models:
            try:
                reg = client.get_registered_model(model_name)
                latest = reg.latest_versions[0] if reg.latest_versions else None
                results.append(
                    ModelHealth(
                        name=model_name,
                        status="registered",
                        latest_version=latest.version if latest else None,
                        stage=latest.current_stage if latest else None,
                    )
                )
            except Exception:
                results.append(ModelHealth(name=model_name, status="not_registered"))
    except Exception:
        results = [
            ModelHealth(name=m, status="registry_unavailable") for m in known_models
        ]

    return results


async def _fetch_n8n_workflows(base_url: str, api_key: str) -> N8nStatusResponse:
    if not api_key:
        return N8nStatusResponse(status="api_key_not_configured", workflows=[])

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{base_url}/api/v1/workflows",
                headers={"X-N8N-API-KEY": api_key},
            )
        if resp.status_code != 200:
            return N8nStatusResponse(status="api_error", workflows=[])

        data = resp.json()
        workflows: list[WorkflowStatus] = []
        for wf in data.get("data", []):
            workflows.append(
                WorkflowStatus(
                    workflow_id=str(wf.get("id", "")),
                    name=wf.get("name", ""),
                    active=bool(wf.get("active", False)),
                )
            )
        return N8nStatusResponse(status="ok", workflows=workflows)
    except Exception as exc:
        logger.warning("n8n_api_unreachable", error=str(exc))
        return N8nStatusResponse(status="unavailable", workflows=[])


# ── Dashboard summary ──────────────────────────────────────────────────────────


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Operations dashboard — aggregate stats across all modules",
)
async def get_dashboard_summary(
    current_user: CurrentUser,
    session: SessionDep,
) -> DashboardSummary:
    tid = current_user.tenant_id
    product_repo = ProductRepository(session, tid)
    shipment_repo = ShipmentRepository(session, tid)
    invoice_repo = InvoiceRepository(session, tid)
    hitl_repo = HITLRepository(session, tid)
    order_repo = ConsumerOrderRepository(session, tid)

    products, shipments, invoices, pending_hitl, consumer_orders = await asyncio.gather(
        product_repo.list_all(limit=10000),
        shipment_repo.list_all(),
        invoice_repo.list_all(limit=10000),
        hitl_repo.list_pending(),
        order_repo.list_all(limit=10000),
    )

    today = date.today()
    outstanding = sum(
        float(i.amount_due)
        for i in invoices
        if i.direction == "receivable" and i.status != "paid"
    )

    return DashboardSummary(
        published_products=sum(1 for p in products if p.storefront_status == "published"),
        enriched_products=sum(1 for p in products if p.enrichment_status == "enriched"),
        pending_enrichment=sum(1 for p in products if p.enrichment_status == "pending"),
        failed_enrichment=sum(1 for p in products if p.enrichment_status == "failed"),
        low_stock_count=sum(
            1
            for p in products
            if p.reorder_threshold is not None and p.qty_in_stock <= p.reorder_threshold
        ),
        active_shipments=sum(1 for s in shipments if s.status in _ACTIVE_SHIPMENT_STATUSES),
        total_invoices=len(invoices),
        overdue_invoices=sum(
            1
            for i in invoices
            if i.status != "paid" and i.due_date < today
        ),
        outstanding_receivables=round(outstanding, 2),
        pending_hitl_count=len(pending_hitl),
        consumer_orders_pending=sum(
            1 for o in consumer_orders if o.status in {"pending", "processing"}
        ),
        generated_at=datetime.now(UTC).isoformat(),
    )


# ── AI model health ────────────────────────────────────────────────────────────


@router.get(
    "/ai-health",
    response_model=AIHealthResponse,
    summary="AI model registry health — MLflow model versions + eval thresholds",
)
async def get_ai_health(
    current_user: CurrentUser,
) -> AIHealthResponse:
    settings = get_settings()
    thresholds = _load_eval_thresholds()
    models = await _query_mlflow_models(settings.mlflow_tracking_uri)

    return AIHealthResponse(
        models=models,
        eval_thresholds=thresholds,
        drift_status=_run_drift_status(),
        checked_at=datetime.now(UTC).isoformat(),
    )


# ── n8n workflow status ────────────────────────────────────────────────────────


@router.get(
    "/workflows",
    response_model=N8nStatusResponse,
    summary="n8n workflow status — active workflows (best-effort, requires n8n_api_key)",
)
async def get_workflow_status(
    current_user: CurrentUser,
) -> N8nStatusResponse:
    settings = get_settings()
    return await _fetch_n8n_workflows(settings.n8n_base_url, settings.n8n_api_key)


# ── Consumer orders ────────────────────────────────────────────────────────────


@router.get(
    "/consumer-orders",
    response_model=list[ConsumerOrderResponse],
    summary="List consumer orders — all statuses, newest first",
)
async def list_consumer_orders(
    current_user: CurrentUser,
    session: SessionDep,
    status_filter: str | None = None,
) -> list[ConsumerOrderResponse]:
    repo = ConsumerOrderRepository(session, current_user.tenant_id)
    orders = await repo.list_all(limit=200, status=status_filter)
    return [
        ConsumerOrderResponse(
            order_id=o.order_id,
            customer_id=o.customer_id,
            status=o.status,
            payment_gateway=o.payment_gateway,
            total_amount=float(o.total_amount),
            created_at=str(o.created_at),
        )
        for o in orders
    ]


@router.post(
    "/consumer-orders/{order_id}/fulfill",
    response_model=FulfillResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create fulfillment_notification HITL action for a consumer order",
)
async def fulfill_consumer_order(
    order_id: str,
    current_user: CurrentUser,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> FulfillResponse:
    """
    Drafts a fulfillment_notification HITL action. The importer reviews
    (A/R/E keyboard shortcuts) before the confirmation email is sent.
    """
    order_repo = ConsumerOrderRepository(session, current_user.tenant_id)
    hitl_repo = HITLRepository(session, current_user.tenant_id)

    order = await order_repo.get_by_id(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consumer order {order_id} not found.",
        )

    if order.status not in {"pending", "processing", "paid"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot fulfill order with status '{order.status}'.",
        )

    action_id = uuid.uuid4().hex
    action = await hitl_repo.create(
        action_id=action_id,
        action_type="fulfillment_notification",
        payload={
            "order_id": order_id,
            "customer_id": order.customer_id,
            "total_amount": float(order.total_amount),
            "payment_gateway": order.payment_gateway,
            "tenant_id": current_user.tenant_id,
        },
    )
    await session.commit()

    logger.info(
        "fulfillment_hitl_created",
        action_id=action_id,
        order_id=order_id,
        tenant_id=current_user.tenant_id,
    )

    return FulfillResponse(
        hitl_action_id=action.action_id,
        action_type=action.action_type,
        status=action.status,
        detail=f"Fulfillment review created for order {order_id}. Approve to send confirmation.",
    )


# ── Enrichment DLQ ────────────────────────────────────────────────────────────


@router.get(
    "/enrichment/dlq",
    response_model=list[DLQProductResponse],
    summary="List products with enrichment_status='failed' (the enrichment DLQ)",
)
async def list_enrichment_dlq(
    current_user: CurrentUser,
    session: SessionDep,
) -> list[DLQProductResponse]:
    product_repo = ProductRepository(session, current_user.tenant_id)
    products = await product_repo.list_all(limit=10000)
    failed = [p for p in products if p.enrichment_status == "failed"]
    return [
        DLQProductResponse(
            product_id=p.product_id,
            product_name=p.product_name,
            enrichment_status=p.enrichment_status,
        )
        for p in failed
    ]


@router.post(
    "/enrichment/dlq/{product_id}/retry",
    summary="Reset enrichment_status to pending and re-queue ARQ enrichment job",
)
async def retry_enrichment_dlq(
    product_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    product_repo = ProductRepository(session, current_user.tenant_id)
    product = await product_repo.get_by_id(product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found.",
        )

    if product.enrichment_status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product enrichment_status is '{product.enrichment_status}', not 'failed'.",
        )

    await product_repo.set_enrichment_status(product_id, "pending")
    await session.commit()

    settings = get_settings()
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await pool.enqueue_job(
            "enrich_product",
            tenant_id=current_user.tenant_id,
            product_id=product_id,
        )
    finally:
        await pool.aclose()

    logger.info(
        "dlq_retry_queued",
        product_id=product_id,
        tenant_id=current_user.tenant_id,
    )

    return {
        "status": "queued",
        "product_id": product_id,
        "detail": "Enrichment job re-queued. Check enrichment_status in a few seconds.",
    }
