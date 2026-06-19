"""
Feature:  Procurement / Dunning — inbound email comprehension
Layer:    Infra / Email
Module:   app.infra.email.comprehend
Purpose:  Read a supplier's inbound email (a reply to a purchase order or a dunning
          message) and extract structured signals: did they ask to change the order,
          did they state a delivery/arrival date, did they promise a payment date,
          plus a one-line summary and overall intent. Uses GPT-4o; degrades to a
          regex/keyword heuristic if the LLM is unavailable so detection never fully
          fails.
Depends:  app.infra.llm.openai
HITL:     None — produces signals that drive notifications + HITL-gated actions.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Comprehension:
    intent: str  # confirm | request_change | reject | question | other
    wants_changes: bool
    change_summary: str
    arrival_date: str | None  # ISO yyyy-mm-dd
    promised_payment_date: str | None  # ISO yyyy-mm-dd
    min_order_qty: int | None  # MOQ stated by the supplier
    summary: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


_ISO = re.compile(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b")
_CHANGE_WORDS = (
    "change", "adjust", "modify", "instead", "cannot supply", "can't supply", "out of stock",
    "unavailable", "minimum order", "different", "substitute", "revise", "increase", "decrease",
    "price has", "updated price", "new price", "lead time", "not available", "back order", "backorder",
)
_REJECT_WORDS = ("decline", "cannot fulfil", "cannot fulfill", "we regret", "unable to", "must decline")


def _norm_date(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    m = _ISO.search(value)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


_MOQ_RE = re.compile(r"(?:minimum order(?:\s+quantity)?|min\.?\s*order|moq)\D{0,12}(\d{1,6})", re.IGNORECASE)


def _norm_moq(value: object) -> int | None:
    if isinstance(value, bool):  # guard: bool is an int subclass
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        m = re.search(r"\d{1,6}", value)
        return int(m.group(0)) if m else None
    return None


def _heuristic(text: str) -> Comprehension:
    low = text.lower()
    iso = _norm_date(text)
    wants = any(w in low for w in _CHANGE_WORDS)
    reject = any(w in low for w in _REJECT_WORDS)
    intent = "reject" if reject else "request_change" if wants else "confirm" if iso else "other"
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "(empty message)")
    moq_m = _MOQ_RE.search(text)
    return Comprehension(
        intent=intent,
        wants_changes=wants,
        change_summary="The supplier may be requesting changes — please review." if wants else "",
        arrival_date=iso,
        promised_payment_date=None,
        min_order_qty=int(moq_m.group(1)) if moq_m else None,
        summary=first_line[:160],
    )


def _parse_json(raw: str) -> dict[str, object] | None:
    s, e = raw.find("{"), raw.rfind("}")
    if s == -1 or e == -1 or e < s:
        return None
    try:
        obj = json.loads(raw[s : e + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


async def comprehend_reply(*, po_number: str | None, thread: str, latest_message: str) -> Comprehension:
    """Best-effort structured read of an inbound supplier email. Never raises."""
    if not latest_message.strip():
        return _heuristic("")
    try:
        from app.infra.llm.openai import chat_completion  # noqa: PLC0415

        today = date.today().isoformat()
        system = (
            "You are a procurement assistant. Read the supplier's latest email in an ongoing thread "
            "and return ONLY a JSON object with these keys: "
            "intent (one of: confirm, request_change, reject, question, other), "
            "wants_changes (boolean — true if they ask to change quantities, prices, items, lead time or "
            "anything about the order), "
            "change_summary (short text of what they want changed, else empty string), "
            "arrival_date (the delivery/arrival/ETA date they state, formatted YYYY-MM-DD, else null), "
            "promised_payment_date (a date they promise to pay by, YYYY-MM-DD, else null), "
            "min_order_qty (the minimum order quantity / MOQ they state, as an integer, else null), "
            "summary (one short sentence summarising their message). "
            f"Today is {today}; resolve relative dates (e.g. 'next Friday') to YYYY-MM-DD. "
            "Output JSON only, no prose, no code fences."
        )
        user = (
            f"Purchase order: {po_number or 'n/a'}\n\n"
            f"Thread so far:\n{thread[:4000] or '(none)'}\n\n"
            f"Supplier's latest email:\n{latest_message[:4000]}"
        )
        raw = await chat_completion(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=400,
        )
        data = _parse_json(raw)
        if not data:
            return _heuristic(latest_message)
        return Comprehension(
            intent=str(data.get("intent") or "other"),
            wants_changes=bool(data.get("wants_changes")),
            change_summary=str(data.get("change_summary") or ""),
            arrival_date=_norm_date(data.get("arrival_date")),
            promised_payment_date=_norm_date(data.get("promised_payment_date")),
            min_order_qty=_norm_moq(data.get("min_order_qty")),
            summary=str(data.get("summary") or "")[:200],
        )
    except Exception as exc:  # noqa: BLE001 — comprehension must degrade, never crash ingest
        logger.warning("comprehend_reply_fallback", error=str(exc))
        return _heuristic(latest_message)
