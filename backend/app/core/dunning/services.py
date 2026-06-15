"""
Feature:  Dunning Engine (4 Tracks)
Layer:    Core / Service
Module:   app.core.dunning.services
Purpose:  Business logic for all 4 dunning tracks. All tracks:
            - Query invoices matching trigger conditions
            - Draft message via GPT-4o (from YAML prompt templates)
            - Create a HITL action (no external write without approval)
            - Create a dunning sequence (idempotent — skips existing sequences)
          Track 1 — B2B Payables: 3-day advance reminder (professional, fixed tone)
          Track 2 — B2B Disputes: on-demand formal complaint (Hybrid/Wholesale only)
          Track 3 — B2B Receivables: Day 7/14/21 (tone classifier)
          Track 4 — B2C Collections: Day 3/7/14 from invoice_date (tone classifier)
          Payment auto-stop: ONE atomic transaction — invoice paid + sequences stopped
          + all pending HITL actions for the invoice rejected.
Depends:  app.core.dunning.tracks, app.core.dunning.models,
          app.core.hitl.models, app.infra.db.repos.*,
          app.ml.tone.classifier, app.infra.llm.openai
HITL:     dunning_payables_advance, dunning_disputes_on_demand,
          dunning_receivables_day7/14/21, dunning_b2c_day3/7/14
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import structlog
import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dunning.models import ToneClass
from app.core.dunning.tracks import get_track3_step, get_track4_step
from app.core.hitl.models import HITLActionType
from app.infra.db.repos.customer_repo import CustomerRepository
from app.infra.db.repos.dunning_repo import DunningRepository
from app.infra.db.repos.hitl_repo import HITLRepository
from app.infra.db.repos.invoice_repo import InvoiceRepository
from app.infra.db.repos.supplier_repo import SupplierRepository
from app.infra.llm.openai import chat_completion
from app.ml.tone.classifier import classify

logger = structlog.get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts" / "communication"


def _load_prompt(name: str) -> dict[str, str]:
    path = _PROMPTS_DIR / f"{name}.yaml"
    with open(path) as f:
        data: dict[str, str] = yaml.safe_load(f)
    return data


# ── Track 1 — B2B Payables (advance reminder) ─────────────────────────────────


async def trigger_track1(
    session: AsyncSession,
    tenant_id: str,
    today: date,
) -> list[str]:
    """
    Daily job (07:00 UTC). For each unpaid payable invoice due in exactly 3 days,
    draft an advance reminder via GPT-4o and create a HITL action.
    Idempotent: skips invoices that already have an active 'payables' sequence.
    Returns list of created action_ids.
    """
    invoice_repo = InvoiceRepository(session, tenant_id)
    dunning_repo = DunningRepository(session, tenant_id)
    hitl_repo = HITLRepository(session, tenant_id)
    supplier_repo = SupplierRepository(session, tenant_id)

    target_date = today.__class__.fromordinal(today.toordinal() + 3)
    invoices = await invoice_repo.list_unpaid_payables_by_due_date(target_date)

    prompts = _load_prompt("dunning_payables")
    action_ids: list[str] = []

    for invoice in invoices:
        # Idempotency guard
        existing = await dunning_repo.get_active_sequence(invoice.invoice_id, "payables")
        if existing is not None:
            continue

        # Resolve supplier info
        supplier_name: str = invoice.contact_name or "Supplier"
        supplier_email: str = invoice.contact_email or ""
        language: str = invoice.contact_language or "en"
        currency: str = invoice.currency

        if invoice.supplier_id:
            supplier = await supplier_repo.get_by_id(invoice.supplier_id)
            if supplier:
                supplier_name = supplier.name
                supplier_email = supplier.email or supplier_email
                language = supplier.language
                currency = supplier.currency

        if not supplier_email:
            logger.warning(
                "track1_no_email",
                invoice_id=invoice.invoice_id,
                tenant_id=tenant_id,
            )
            continue

        # Draft message — professional tone always (no classifier for Track 1)
        system_text: str = prompts["system"].format(language=language)
        user_text: str = prompts["payables_advance"].format(
            supplier_name=supplier_name,
            invoice_id=invoice.invoice_id,
            amount=invoice.amount_due,
            currency=currency,
            due_date=invoice.due_date.isoformat(),
            days_until_due=3,
        )
        try:
            body = await chat_completion(
                [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": user_text},
                ]
            )
        except Exception as exc:
            logger.error("track1_draft_failed", invoice_id=invoice.invoice_id, error=str(exc))
            continue

        # HITL action
        action_id = uuid.uuid4().hex
        subject = (
            f"Payment Reminder — Invoice {invoice.invoice_id} (Due: {invoice.due_date.isoformat()})"
        )
        await hitl_repo.create(
            action_id=action_id,
            action_type=HITLActionType.DUNNING_PAYABLES_ADVANCE,
            payload={
                "invoice_id": invoice.invoice_id,
                "to": supplier_email,
                "subject": subject,
                "body": body,
                "track": "payables",
            },
        )

        # Dunning sequence (tracks that this invoice is being processed)
        await dunning_repo.create_sequence(
            sequence_id=uuid.uuid4().hex,
            invoice_id=invoice.invoice_id,
            track="payables",
        )

        action_ids.append(action_id)
        logger.info(
            "track1_hitl_created",
            action_id=action_id,
            invoice_id=invoice.invoice_id,
            tenant_id=tenant_id,
        )

    return action_ids


# ── Track 2 — B2B Disputes (on-demand) ────────────────────────────────────────


async def trigger_track2(
    session: AsyncSession,
    tenant_id: str,
    invoice_id: str,
    supplier_id: str,
    dispute_context: dict[str, Any],
) -> str:
    """
    On-demand dispute. Must be called only for Hybrid/Wholesale tenants (mode gate in API).
    Returns the created HITL action_id.
    dispute_context keys: po_reference, shipment_id, dispute_type,
    products_affected_json, damage_description, resolution_requested.
    """
    supplier_repo = SupplierRepository(session, tenant_id)
    hitl_repo = HITLRepository(session, tenant_id)
    dunning_repo = DunningRepository(session, tenant_id)

    supplier = await supplier_repo.get_by_id(supplier_id)
    supplier_name = supplier.name if supplier else "Supplier"
    supplier_email = (supplier.email if supplier else None) or ""
    language = supplier.language if supplier else "en"

    if not supplier_email:
        raise ValueError(f"Supplier {supplier_id} has no email address.")

    prompts = _load_prompt("dispute_letter")
    system_text = prompts["system"].format(language=language)
    user_text = prompts["dispute_letter"].format(
        supplier_name=supplier_name,
        language=language,
        po_reference=dispute_context.get("po_reference", "N/A"),
        shipment_id=dispute_context.get("shipment_id", "N/A"),
        dispute_type=dispute_context.get("dispute_type", "general"),
        products_affected_json=dispute_context.get("products_affected_json", "[]"),
        damage_description=dispute_context.get("damage_description", ""),
        resolution_requested=dispute_context.get("resolution_requested", ""),
    )

    body = await chat_completion(
        [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ]
    )

    action_id = uuid.uuid4().hex
    subject = f"Formal Dispute — Invoice {invoice_id}"
    await hitl_repo.create(
        action_id=action_id,
        action_type=HITLActionType.DUNNING_DISPUTES_ON_DEMAND,
        payload={
            "invoice_id": invoice_id,
            "supplier_id": supplier_id,
            "to": supplier_email,
            "subject": subject,
            "body": body,
            "track": "disputes",
            **dispute_context,
        },
    )

    await dunning_repo.create_sequence(
        sequence_id=uuid.uuid4().hex,
        invoice_id=invoice_id,
        track="disputes",
    )

    logger.info(
        "track2_hitl_created",
        action_id=action_id,
        invoice_id=invoice_id,
        tenant_id=tenant_id,
    )
    return action_id


# ── Track 3 — B2B Receivables (Day 7/14/21 from due_date) ─────────────────────


async def trigger_track3(
    session: AsyncSession,
    tenant_id: str,
    today: date,
) -> list[str]:
    """
    Daily job (07:05 UTC). For each overdue B2B receivable at Day 7, 14, or 21,
    classify tone and draft a reminder via GPT-4o. HITL action created per step.
    Idempotency: tracks the sequence step — won't re-send the same day.
    Returns list of created action_ids.
    """
    invoice_repo = InvoiceRepository(session, tenant_id)
    customer_repo = CustomerRepository(session, tenant_id)
    hitl_repo = HITLRepository(session, tenant_id)
    dunning_repo = DunningRepository(session, tenant_id)

    invoices = await invoice_repo.list_overdue_b2b_receivables(today)
    prompts = _load_prompt("dunning_receivables")
    action_ids: list[str] = []

    _step_to_action_type: dict[str, HITLActionType] = {
        "day7": HITLActionType.DUNNING_RECEIVABLES_DAY7,
        "day14": HITLActionType.DUNNING_RECEIVABLES_DAY14,
        "day21": HITLActionType.DUNNING_RECEIVABLES_DAY21,
    }
    _step_to_prompt_key: dict[str, str] = {
        "day7": "receivables_day7",
        "day14": "receivables_day14",
        "day21": "receivables_day21",
    }
    _step_to_days: dict[str, int] = {"day7": 7, "day14": 14, "day21": 21}

    for invoice in invoices:
        step = get_track3_step(due_date=invoice.due_date, today=today)
        if step is None:
            continue

        # Idempotency: check if HITL for this step already exists
        action_type = _step_to_action_type[step]
        existing_pending = await hitl_repo.list_pending(action_type=str(action_type))
        already_sent = any(
            a.payload.get("invoice_id") == invoice.invoice_id for a in existing_pending
        )
        if already_sent:
            continue

        # Resolve customer info
        customer_name: str = invoice.contact_name or "Customer"
        customer_email: str = invoice.contact_email or ""
        language: str = invoice.contact_language or "en"
        days_overdue = _step_to_days[step]

        # Tone classifier features
        days_overdue_int = days_overdue
        segment = "Regular"
        payment_score = 1.0
        dunning_count = 0

        if invoice.customer_id:
            customer = await customer_repo.get_by_id(invoice.customer_id)
            if customer:
                customer_name = customer.name
                customer_email = customer.email or customer_email
                language = customer.language
                segment = customer.segment
                payment_score = float(customer.payment_history_score)
                dunning_count = customer.previous_dunning_count

        if not customer_email:
            logger.warning(
                "track3_no_email",
                invoice_id=invoice.invoice_id,
                tenant_id=tenant_id,
            )
            continue

        tone_result = classify(
            days_overdue=days_overdue_int,
            customer_segment=segment,
            overdue_amount=float(invoice.amount_due),
            payment_history_score=payment_score,
            previous_dunning_count=dunning_count,
        )
        tone_str = str(tone_result.tone)

        # Draft message
        system_text = prompts["system"].format(language=language)
        prompt_key = _step_to_prompt_key[step]
        user_text = prompts[prompt_key].format(
            tone=tone_str,
            customer_name=customer_name,
            invoice_id=invoice.invoice_id,
            amount=invoice.amount_due,
            currency=invoice.currency,
            due_date=invoice.due_date.isoformat(),
        )
        try:
            body = await chat_completion(
                [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": user_text},
                ]
            )
        except Exception as exc:
            logger.error("track3_draft_failed", invoice_id=invoice.invoice_id, error=str(exc))
            continue

        action_id = uuid.uuid4().hex
        subject = f"Payment Reminder ({step.replace('day', 'Day ')}) — Invoice {invoice.invoice_id}"
        await hitl_repo.create(
            action_id=action_id,
            action_type=action_type,
            payload={
                "invoice_id": invoice.invoice_id,
                "to": customer_email,
                "subject": subject,
                "body": body,
                "track": "receivables",
                "step": step,
                "tone": tone_str,
            },
        )

        # Ensure sequence exists (create if first step, ignore if already exists)
        existing_seq = await dunning_repo.get_active_sequence(invoice.invoice_id, "receivables")
        if existing_seq is None:
            await dunning_repo.create_sequence(
                sequence_id=uuid.uuid4().hex,
                invoice_id=invoice.invoice_id,
                track="receivables",
            )

        # Increment dunning count on customer
        if invoice.customer_id:
            await customer_repo.increment_dunning_count(invoice.customer_id)

        action_ids.append(action_id)
        logger.info(
            "track3_hitl_created",
            action_id=action_id,
            invoice_id=invoice.invoice_id,
            step=step,
            tenant_id=tenant_id,
        )

    return action_ids


# ── Track 4 — B2C Collections (Day 3/7/14 from invoice_date) ──────────────────


async def trigger_track4(
    session: AsyncSession,
    tenant_id: str,
    today: date,
) -> list[str]:
    """
    Daily job (07:10 UTC). For each overdue B2C invoice at Day 3, 7, or 14
    from invoice_date, classify tone and draft reminder. HITL action per step.
    Returns list of created action_ids.
    """
    invoice_repo = InvoiceRepository(session, tenant_id)
    customer_repo = CustomerRepository(session, tenant_id)
    hitl_repo = HITLRepository(session, tenant_id)
    dunning_repo = DunningRepository(session, tenant_id)

    invoices = await invoice_repo.list_overdue_b2c(today)
    prompts = _load_prompt("dunning_b2c")
    action_ids: list[str] = []

    _step_to_action_type: dict[str, HITLActionType] = {
        "day3": HITLActionType.DUNNING_B2C_DAY3,
        "day7": HITLActionType.DUNNING_B2C_DAY7,
        "day14": HITLActionType.DUNNING_B2C_DAY14,
    }
    _step_to_prompt_key: dict[str, str] = {
        "day3": "b2c_day3",
        "day7": "b2c_day7",
        "day14": "b2c_day14",
    }
    _step_to_days: dict[str, int] = {"day3": 3, "day7": 7, "day14": 14}

    for invoice in invoices:
        step = get_track4_step(invoice_date=invoice.invoice_date, today=today)
        if step is None:
            continue

        action_type = _step_to_action_type[step]
        existing_pending = await hitl_repo.list_pending(action_type=str(action_type))
        already_sent = any(
            a.payload.get("invoice_id") == invoice.invoice_id for a in existing_pending
        )
        if already_sent:
            continue

        # Resolve customer info
        customer_name: str = invoice.contact_name or "Customer"
        customer_email: str = invoice.contact_email or ""
        language: str = invoice.contact_language or "en"
        days_since = _step_to_days[step]

        segment = "Regular"
        payment_score = 1.0
        dunning_count = 0

        if invoice.customer_id:
            customer = await customer_repo.get_by_id(invoice.customer_id)
            if customer:
                customer_name = customer.name
                customer_email = customer.email or customer_email
                language = customer.language
                segment = customer.segment
                payment_score = float(customer.payment_history_score)
                dunning_count = customer.previous_dunning_count

        if not customer_email:
            logger.warning(
                "track4_no_email",
                invoice_id=invoice.invoice_id,
                tenant_id=tenant_id,
            )
            continue

        tone_result = classify(
            days_overdue=days_since,
            customer_segment=segment,
            overdue_amount=float(invoice.amount_due),
            payment_history_score=payment_score,
            previous_dunning_count=dunning_count,
        )
        tone_str = str(tone_result.tone)

        # Payment link — Phase 11 Stripe integration provides real URL;
        # for Phase 6 we construct a placeholder that the importer can replace before approving.
        order_ref = invoice.order_id or invoice.invoice_id
        payment_link = f"https://pay.mawrid.app/{invoice.tenant_id}/{order_ref}"

        system_text = prompts["system"].format(language=language)
        prompt_key = _step_to_prompt_key[step]
        user_text = prompts[prompt_key].format(
            tone=tone_str,
            customer_name=customer_name,
            order_id=order_ref,
            amount=invoice.amount_due,
            currency=invoice.currency,
            invoice_date=invoice.invoice_date.isoformat(),
            payment_link=payment_link,
        )
        try:
            body = await chat_completion(
                [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": user_text},
                ]
            )
        except Exception as exc:
            logger.error("track4_draft_failed", invoice_id=invoice.invoice_id, error=str(exc))
            continue

        action_id = uuid.uuid4().hex
        subject = f"Payment Reminder ({step.replace('day', 'Day ')}) — Order {order_ref}"
        await hitl_repo.create(
            action_id=action_id,
            action_type=action_type,
            payload={
                "invoice_id": invoice.invoice_id,
                "to": customer_email,
                "subject": subject,
                "body": body,
                "track": "b2c",
                "step": step,
                "tone": tone_str,
                "payment_link": payment_link,
            },
        )

        existing_seq = await dunning_repo.get_active_sequence(invoice.invoice_id, "b2c")
        if existing_seq is None:
            await dunning_repo.create_sequence(
                sequence_id=uuid.uuid4().hex,
                invoice_id=invoice.invoice_id,
                track="b2c",
            )

        if invoice.customer_id:
            await customer_repo.increment_dunning_count(invoice.customer_id)

        action_ids.append(action_id)
        logger.info(
            "track4_hitl_created",
            action_id=action_id,
            invoice_id=invoice.invoice_id,
            step=step,
            tenant_id=tenant_id,
        )

    return action_ids


# ── Payment Auto-Stop ──────────────────────────────────────────────────────────


async def auto_stop_on_payment(
    session: AsyncSession,
    tenant_id: str,
    invoice_id: str,
    paid_at: datetime | None = None,
) -> dict[str, int]:
    """
    ATOMIC payment reconciliation:
    1. Mark invoice paid (idempotent — checks paid_at first)
    2. Stop all active dunning sequences for this invoice
    3. Reject all pending HITL dunning actions for this invoice
    All three writes in the same transaction (caller must commit).
    Returns counts: {"invoice_marked_paid": 0|1, "sequences_stopped": N, "hitl_cancelled": N}
    """
    invoice_repo = InvoiceRepository(session, tenant_id)
    dunning_repo = DunningRepository(session, tenant_id)
    hitl_repo = HITLRepository(session, tenant_id)
    customer_repo = CustomerRepository(session, tenant_id)

    now = paid_at or datetime.now(UTC)

    invoice = await invoice_repo.mark_paid(invoice_id, paid_at=now)
    invoice_marked = 0 if (invoice is None or invoice.paid_at != now) else 1

    sequences_stopped = await dunning_repo.stop_all_for_invoice(invoice_id, stopped_at=now)
    hitl_cancelled = await hitl_repo.bulk_cancel_by_invoice(invoice_id)

    # Reset customer dunning count on payment (so next cycle starts fresh)
    if invoice and invoice.customer_id:
        await customer_repo.reset_dunning_count(invoice.customer_id)

    logger.info(
        "auto_stop_complete",
        invoice_id=invoice_id,
        tenant_id=tenant_id,
        sequences_stopped=sequences_stopped,
        hitl_cancelled=hitl_cancelled,
    )
    return {
        "invoice_marked_paid": invoice_marked,
        "sequences_stopped": sequences_stopped,
        "hitl_cancelled": hitl_cancelled,
    }


# ── Tone Override (for HITL editing) ──────────────────────────────────────────


async def redraft_with_tone(
    invoice_id: str,
    step: str,
    tone: ToneClass,
    track: str,
    language: str,
    customer_name: str,
    amount: float,
    currency: str,
    due_date_str: str,
    invoice_date_str: str | None = None,
    payment_link: str | None = None,
    order_id: str | None = None,
) -> str:
    """Re-draft a dunning message with an explicitly chosen tone (for HITL edit shortcut)."""
    if track == "receivables":
        prompts = _load_prompt("dunning_receivables")
        prompt_key = f"receivables_{step}"
        system_text = prompts["system"].format(language=language)
        user_text = prompts[prompt_key].format(
            tone=str(tone),
            customer_name=customer_name,
            invoice_id=invoice_id,
            amount=amount,
            currency=currency,
            due_date=due_date_str,
        )
    elif track == "b2c":
        prompts = _load_prompt("dunning_b2c")
        prompt_key = f"b2c_{step}"
        system_text = prompts["system"].format(language=language)
        user_text = prompts[prompt_key].format(
            tone=str(tone),
            customer_name=customer_name,
            order_id=order_id or invoice_id,
            amount=amount,
            currency=currency,
            invoice_date=invoice_date_str or due_date_str,
            payment_link=payment_link or "",
        )
    else:
        raise ValueError(f"tone override not supported for track '{track}'")

    return await chat_completion(
        [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ]
    )
