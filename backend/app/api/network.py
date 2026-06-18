"""
Feature:  Supplier & Factory Network
Layer:    API / Router
Module:   app.api.network
Purpose:  The supplier/factory intelligence hub: a real map of manufacturers
          (curated verified reference data + the tenant's geocoded suppliers +
          daily web-discovered candidates), category comparison, and HITL-gated
          AI outreach with reply tracking. Region = europe for now; others are
          surfaced as "coming soon".
Depends:  reference_factories + suppliers models, app.infra.geo.geocode,
          app.core.suppliers.services (score/discovery), app.infra.llm.openai
HITL:     supplier_outreach (AI-drafted intro/inquiry email).
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.infra.db.models.reference_factory import ReferenceFactory
from app.infra.db.models.supplier import Supplier
from app.infra.db.repos.hitl_repo import HITLRepository
from app.infra.db.repos.supplier_repo import SupplierRepository
from app.infra.geo.geocode import geocode
from app.infra.llm.openai import chat_completion

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/network", tags=["network"])

_REGIONS = [
    {"key": "europe", "label": "Europe", "available": True, "center": [50.0, 10.0], "zoom": 4,
     "bounds": [[33.0, -16.0], [72.0, 45.0]], "min_zoom": 4},
    {"key": "turkey", "label": "Turkey", "available": False, "center": [39.0, 35.0], "zoom": 5,
     "bounds": [[35.0, 25.0], [43.0, 45.0]], "min_zoom": 5},
    {"key": "gulf", "label": "Gulf", "available": False, "center": [25.0, 50.0], "zoom": 5,
     "bounds": [[12.0, 34.0], [33.0, 60.0]], "min_zoom": 5},
    {"key": "china", "label": "China", "available": False, "center": [35.0, 105.0], "zoom": 4,
     "bounds": [[18.0, 73.0], [54.0, 135.0]], "min_zoom": 4},
    {"key": "usa", "label": "USA", "available": False, "center": [39.0, -98.0], "zoom": 4,
     "bounds": [[24.0, -125.0], [50.0, -66.0]], "min_zoom": 4},
    {"key": "australia", "label": "Australia", "available": False, "center": [-25.0, 133.0], "zoom": 4,
     "bounds": [[-44.0, 112.0], [-10.0, 154.0]], "min_zoom": 4},
]


# ── Schemas ──────────────────────────────────────────────────────────────────


class FactoryPin(StrictModel):
    id: str
    source: str  # curated | saved | discovered
    name: str
    category: str
    subcategory: str | None = None
    latitude: float | None
    longitude: float | None
    country: str | None
    city: str | None
    website: str | None
    logo_url: str | None
    offering: str | None
    condition: str | None
    email: str | None
    score: float | None = None


class FactoriesResponse(StrictModel):
    region: str
    pins: list[FactoryPin]
    categories: list[str]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ref_to_pin(f: ReferenceFactory) -> FactoryPin:
    return FactoryPin(
        id=f.factory_id, source="curated", name=f.name, category=f.category,
        subcategory=f.subcategory, latitude=f.latitude, longitude=f.longitude,
        country=f.country, city=f.city, website=f.website, logo_url=f.logo_url,
        offering=f.offering, condition=f.condition, email=f.email,
    )


def _sup_to_pin(s: Supplier) -> FactoryPin:
    return FactoryPin(
        id=s.supplier_id, source=(s.source or "saved"), name=s.name,
        category=(s.category or "supplier"), subcategory=None,
        latitude=float(s.latitude) if s.latitude is not None else None,
        longitude=float(s.longitude) if s.longitude is not None else None,
        country=None, city=s.location, website=s.website, logo_url=s.logo_url,
        offering=s.offering or s.description, condition=s.condition, email=s.email,
        score=float(s.score) if s.score is not None else None,
    )


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/regions", summary="Map regions (only europe is active for now)")
async def list_regions(current_user: CurrentUser) -> list[dict[str, Any]]:
    return _REGIONS


@router.get("/factories", response_model=FactoriesResponse, summary="Map pins: curated + saved + discovered")
async def list_factories(
    current_user: CurrentUser,
    session: SessionDep,
    region: str = "europe",
) -> FactoriesResponse:
    # curated reference (global, verified)
    ref_rows = (
        await session.execute(select(ReferenceFactory).where(ReferenceFactory.region == region))
    ).scalars().all()
    pins = [_ref_to_pin(f) for f in ref_rows]
    # the tenant's own suppliers (saved + discovered)
    sup_rows = (
        await session.execute(select(Supplier).where(Supplier.tenant_id == current_user.tenant_id))
    ).scalars().all()
    for s in sup_rows:
        pins.append(_sup_to_pin(s))
    categories = sorted({p.category for p in pins})
    return FactoriesResponse(region=region, pins=pins, categories=categories)


def _logo_from_website(website: str | None) -> str | None:
    if not website:
        return None
    domain = website.replace("https://", "").replace("http://", "").split("/")[0]
    return f"https://logo.clearbit.com/{domain}" if domain else None


@router.post("/enrich-logos", summary="Logo agent — fill missing supplier logos from their website")
async def enrich_logos(current_user: CurrentUser, session: SessionDep) -> dict[str, int]:
    """The logo agent: for suppliers that have a website but no logo, derive a real logo
    URL. Runs on demand and every morning. Suppliers without a website are left for a
    manual upload."""
    rows = (
        await session.execute(select(Supplier).where(Supplier.tenant_id == current_user.tenant_id))
    ).scalars().all()
    filled = 0
    for s in rows:
        if not s.logo_url and s.website:
            logo = _logo_from_website(s.website)
            if logo:
                s.logo_url = logo
                filled += 1
    await session.commit()
    logger.info("logo_agent_run", tenant_id=current_user.tenant_id, filled=filled)
    return {"filled": filled}


@router.post("/discover", summary="Discovery agent — find new real suppliers for your business (best-effort)")
async def discover_prospects(
    current_user: CurrentUser, session: SessionDep, category: str = "home appliances"
) -> dict[str, int]:
    """The discovery agent: searches the web (SearXNG) for real manufacturers/suppliers in
    the tenant's business, extracts them with GPT, geocodes, and saves them as PROSPECTS on
    the map. Best-effort & bounded; also runs each morning. Never fabricates."""
    from app.core.config import get_settings  # noqa: PLC0415

    tenant_id = current_user.tenant_id
    added = 0
    try:
        from app.core.catalog.enrichment_pipeline import SearxngClient  # noqa: PLC0415
        from app.infra.geo.geocode import geocode_detailed  # noqa: PLC0415

        searx = SearxngClient(get_settings().searxng_base_url)
        urls = await searx.search(f"{category} manufacturer wholesale supplier Europe")
        import json as _json  # noqa: PLC0415
        from urllib.parse import urlparse  # noqa: PLC0415

        domains = []
        for u in urls[:8]:
            d = urlparse(u).netloc.replace("www.", "")
            if d and d not in domains:
                domains.append(d)
        extract = await chat_completion(
            messages=[
                {"role": "system", "content": (
                    "From these website domains, return a JSON array of up to 5 REAL manufacturer/"
                    "supplier companies for the given category. Each: {name, website, city, country, "
                    "offering}. Only well-known real companies — never invent. JSON only."
                )},
                {"role": "user", "content": f"Category: {category}\nDomains: {domains}"},
            ],
            temperature=0.0, max_tokens=700,
        )
        import re as _re  # noqa: PLC0415

        cleaned = _re.sub(r"^```(?:json)?\s*|\s*```$", "", extract.strip(), flags=_re.MULTILINE)
        items = _json.loads(cleaned)
        repo = SupplierRepository(session, tenant_id)
        for it in items[:5]:
            name = str(it.get("name") or "").strip()
            if not name or await repo.find_by_name_exact(name):
                continue
            website = str(it.get("website") or "")
            if website and not website.startswith("http"):
                website = "https://" + website
            place = ", ".join(str(it.get(k) or "") for k in ("city", "country")).strip(", ")
            coords = await geocode_detailed(place or name)
            s = Supplier(
                supplier_id=uuid.uuid4().hex, tenant_id=tenant_id, name=name, category=category,
                website=website or None, logo_url=_logo_from_website(website), offering=str(it.get("offering") or "") or None,
                location=place or None, kind="manufacturer", source="discovered", relationship="prospect",
                condition="new", region="europe",
                latitude=coords.get("latitude") if coords else None,
                longitude=coords.get("longitude") if coords else None,
            )
            session.add(s)
            added += 1
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("discovery_agent_failed", error=str(exc))
    logger.info("discovery_agent_run", tenant_id=tenant_id, added=added)
    return {"added": added}


@router.post("/refresh", summary="Geocode saved suppliers + discover new sources (daily job also runs this)")
async def refresh_network(
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, int]:
    tenant_id = current_user.tenant_id
    geocoded = 0
    sup_rows = (
        await session.execute(select(Supplier).where(Supplier.tenant_id == tenant_id))
    ).scalars().all()
    for s in sup_rows:
        if s.latitude is None and s.location:
            coords = await geocode(s.location)
            if coords:
                s.latitude, s.longitude = coords
                if not s.region:
                    s.region = "europe"
                geocoded += 1
    await session.commit()
    logger.info("network_refresh", tenant_id=tenant_id, geocoded=geocoded)
    return {"geocoded": geocoded}


class CompareRow(FactoryPin):
    relationship: str | None = None
    rating: float | None = None
    moq: int | None = None
    currency: str | None = None
    language: str | None = None
    phone: str | None = None
    # performance (saved suppliers): real numbers from history
    metrics: dict[str, float] | None = None
    po_count: int = 0
    total_spend: float = 0.0


class CompareRequest(StrictModel):
    ids: list[str]


def _ref_to_row(f: ReferenceFactory) -> CompareRow:
    p = _ref_to_pin(f)
    return CompareRow(**p.model_dump())


@router.post("/compare", response_model=list[CompareRow], summary="Rich side-by-side comparison rows")
async def compare(
    body: CompareRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> list[CompareRow]:
    from sqlalchemy import func  # noqa: PLC0415

    from app.infra.db.models.order import PurchaseOrder  # noqa: PLC0415

    tenant_id = current_user.tenant_id
    out: list[CompareRow] = []
    for fid in body.ids:
        if fid.startswith("ref_"):
            f = await session.get(ReferenceFactory, fid)
            if f:
                out.append(_ref_to_row(f))
            continue
        s = await SupplierRepository(session, tenant_id).get_by_id(fid)
        if s is None:
            continue
        row = CompareRow(**_sup_to_pin(s).model_dump())
        row.relationship = getattr(s, "relationship", None) or "active"
        row.rating = float(s.rating) if s.rating is not None else None
        row.moq = s.moq
        row.currency = s.currency
        row.language = s.language
        row.phone = s.phone
        # purchase-order history (real)
        po_stat = (
            await session.execute(
                select(func.count(), func.coalesce(func.sum(PurchaseOrder.total_amount), 0)).where(
                    PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.supplier_id == s.supplier_id
                )
            )
        ).one()
        row.po_count = int(po_stat[0])
        row.total_spend = float(po_stat[1] or 0)
        # score breakdown (real features) — best-effort
        try:
            from app.core.suppliers.services import get_supplier_score  # noqa: PLC0415

            sc = await get_supplier_score(session=session, tenant_id=tenant_id, supplier_id=s.supplier_id)
            f2 = sc.features
            row.score = sc.score
            row.metrics = {
                "on_time_delivery_rate": f2.on_time_delivery_rate,
                "damage_rate": f2.damage_rate,
                "avg_price_vs_market": f2.avg_price_vs_market,
                "response_time_hours": f2.response_time_hours,
                "discrepancy_rate": f2.discrepancy_rate,
                "catalog_completeness": f2.catalog_completeness,
            }
        except Exception:  # noqa: BLE001
            pass
        out.append(row)
    return out


# ── Outreach (HITL-gated) ────────────────────────────────────────────────────


class FindEmailRequest(StrictModel):
    target_id: str


class FindEmailResponse(StrictModel):
    email: str | None


@router.post("/find-email", response_model=FindEmailResponse, summary="Auto-find a supplier's public contact email (best-effort)")
async def find_email(
    body: FindEmailRequest, current_user: CurrentUser, session: SessionDep
) -> FindEmailResponse:
    """Best-effort web search for the company's public contact email. Returns null if
    nothing credible is found — never fabricates."""
    name = ""
    website = None
    if body.target_id.startswith("ref_"):
        f = await session.get(ReferenceFactory, body.target_id)
        if f:
            name, website = f.name, f.website
    else:
        s = await SupplierRepository(session, current_user.tenant_id).get_by_id(body.target_id)
        if s:
            name, website = s.name, s.website
    if not name:
        return FindEmailResponse(email=None)
    try:
        from app.core.catalog.enrichment_pipeline import SearxngClient, WebFetcher  # noqa: PLC0415
        from app.core.config import get_settings  # noqa: PLC0415

        searx = SearxngClient(get_settings().searxng_base_url)
        fetcher = WebFetcher()
        urls = await searx.search(f"{name} contact email wholesale {website or ''}")
        text = ""
        for u in urls[:3]:
            t, _ = await fetcher.fetch_page(u)
            if t:
                text += t[:3000] + "\n"
        import re as _re  # noqa: PLC0415

        emails = _re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        # prefer info@/sales@/contact@ on the company domain
        dom = (website or "").replace("https://", "").replace("http://", "").split("/")[0]
        best = None
        for e in emails:
            el = e.lower()
            if dom and dom.split(".")[-2:] == el.split("@")[-1].split(".")[-2:]:
                best = e
                if el.split("@")[0] in ("info", "sales", "contact", "export"):
                    break
        if not best and emails:
            best = emails[0]
        return FindEmailResponse(email=best)
    except Exception as exc:  # noqa: BLE001
        logger.warning("find_email_failed", error=str(exc))
        return FindEmailResponse(email=None)


class OutreachRequest(StrictModel):
    target_id: str  # ref_* (curated) or a supplier_id
    intent: str = "introduce"  # introduce | catalog | general
    to: str | None = None  # override / fill the email if missing
    notes: str | None = None


class OutreachResponse(StrictModel):
    supplier_id: str
    action_id: str
    to: str | None
    subject: str
    body: str


_INTENT_GUIDE = {
    "introduce": "Introduce our company as an importer/distributor and express interest in a partnership.",
    "catalog": "Politely request their current product catalogue, available models, quantities and price list.",
    "general": "Ask to learn more about the company, what they manufacture and their export terms.",
}


async def _ensure_supplier_from_factory(session: Any, tenant_id: str, target_id: str) -> Supplier:
    """Resolve an outreach target to a tenant Supplier. A curated factory becomes a
    tracked supplier (idempotent by name) so it has an id + a reply thread."""
    repo = SupplierRepository(session, tenant_id)
    if not target_id.startswith("ref_"):
        s = await repo.get_by_id(target_id)
        if s is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")
        return s
    f = await session.get(ReferenceFactory, target_id)
    if f is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factory not found.")
    existing = await repo.find_by_name_exact(f.name)
    if existing is not None:
        return existing
    s = Supplier(
        supplier_id=uuid.uuid4().hex, tenant_id=tenant_id, name=f.name, email=f.email,
        location=f"{f.city}, {f.country}" if f.city else f.country, category=f.category,
        website=f.website, logo_url=f.logo_url, offering=f.offering, condition=f.condition,
        latitude=f.latitude, longitude=f.longitude, kind="manufacturer", source="discovered",
        region=f.region, relationship="prospect",
    )
    session.add(s)
    await session.flush()
    return s


@router.post("/outreach", response_model=OutreachResponse, summary="AI-draft an outreach email and queue it for HITL approval")
async def create_outreach(
    body: OutreachRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> OutreachResponse:
    tenant_id = current_user.tenant_id
    supplier = await _ensure_supplier_from_factory(session, tenant_id, body.target_id)
    to_addr = (body.to or supplier.email or "").strip()
    # Remember the email on the supplier so replies can be sent later.
    if to_addr and not supplier.email:
        supplier.email = to_addr

    from app.infra.db.models.tenant import Tenant  # noqa: PLC0415

    tenant_row = await session.get(Tenant, tenant_id)
    our_name = tenant_row.name if tenant_row and tenant_row.name else "our company"
    guide = _INTENT_GUIDE.get(body.intent, _INTENT_GUIDE["introduce"])

    body_text = await chat_completion(
        messages=[
            {"role": "system", "content": (
                "You are a procurement officer writing a concise, professional first-contact "
                "business email to a manufacturer/supplier on behalf of an importer. Warm, "
                "credible, 3 short paragraphs max. Sign off with the importer's company name. "
                "Do NOT use bracketed placeholders like [Your Name], [Company] or [Position] — "
                "use the real company name provided and omit anything you don't know. "
                "Output only the email body."
            )},
            {"role": "user", "content": (
                f"Our company: {our_name}.\nSupplier/factory: {supplier.name} "
                f"({supplier.offering or supplier.category}).\nGoal: {guide}\n"
                f"Extra notes: {body.notes or '-'}\nStart with 'Dear {supplier.name} team,'."
            )},
        ],
        temperature=0.4, max_tokens=600,
    )
    import re as _re  # noqa: PLC0415

    body_text = _re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", body_text.strip()).strip()
    # Belt-and-braces: strip any leftover [placeholder] tokens the model slipped in.
    body_text = _re.sub(r"\s*\[[^\]]{0,40}\]", "", body_text)
    body_text = _re.sub(r"[ \t]{2,}", " ", body_text).strip()
    subject = {
        "introduce": f"Partnership enquiry — {our_name}",
        "catalog": f"Catalogue & pricing request — {our_name}",
        "general": f"Introduction & enquiry — {our_name}",
    }.get(body.intent, f"Enquiry — {our_name}")

    hitl_repo = HITLRepository(session, tenant_id)
    action_id = uuid.uuid4().hex
    await hitl_repo.create(
        action_id=action_id,
        action_type="supplier_outreach",
        payload={
            "supplier_id": supplier.supplier_id, "supplier_name": supplier.name,
            "to": to_addr, "subject": subject, "body": body_text, "intent": body.intent,
        },
    )
    await session.commit()
    return OutreachResponse(
        supplier_id=supplier.supplier_id, action_id=action_id, to=to_addr or None,
        subject=subject, body=body_text,
    )


class ConversationItem(StrictModel):
    supplier_id: str
    name: str
    email: str | None
    relationship: str
    message_count: int
    last_at: str | None
    last_direction: str | None


@router.get("/conversations", response_model=list[ConversationItem], summary="All outreach conversations (inbox)")
async def list_conversations(
    current_user: CurrentUser, session: SessionDep
) -> list[ConversationItem]:
    rows = (
        await session.execute(
            select(Supplier).where(
                Supplier.tenant_id == current_user.tenant_id,
                Supplier.outreach_messages.is_not(None),
            )
        )
    ).scalars().all()
    out: list[ConversationItem] = []
    for s in rows:
        msgs = s.outreach_messages or []
        if not msgs:
            continue
        last = msgs[-1]
        out.append(ConversationItem(
            supplier_id=s.supplier_id, name=s.name, email=s.email,
            relationship=getattr(s, "relationship", None) or "active",
            message_count=len(msgs), last_at=str(last.get("at")) if last.get("at") else None,
            last_direction=str(last.get("direction")) if last.get("direction") else None,
        ))
    out.sort(key=lambda c: c.last_at or "", reverse=True)
    return out


class OutreachThreadResponse(StrictModel):
    supplier_id: str
    name: str
    email: str | None
    messages: list[dict[str, Any]]


@router.get("/outreach/{supplier_id}", response_model=OutreachThreadResponse, summary="Outreach reply thread for a supplier")
async def get_outreach_thread(
    supplier_id: str, current_user: CurrentUser, session: SessionDep
) -> OutreachThreadResponse:
    s = await SupplierRepository(session, current_user.tenant_id).get_by_id(supplier_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")
    return OutreachThreadResponse(
        supplier_id=s.supplier_id, name=s.name, email=s.email, messages=s.outreach_messages or []
    )


class LogReplyRequest(StrictModel):
    body: str
    direction: str = "inbound"
    sender: str | None = None


@router.post("/outreach/{supplier_id}/messages", summary="Log a reply received from a supplier")
async def log_outreach_message(
    supplier_id: str, body: LogReplyRequest, current_user: CurrentUser, session: SessionDep
) -> dict[str, str]:
    from datetime import UTC, datetime  # noqa: PLC0415

    repo = SupplierRepository(session, current_user.tenant_id)
    s = await repo.get_by_id(supplier_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")
    s.outreach_messages = [
        *(s.outreach_messages or []),
        {"direction": body.direction, "sender": body.sender or s.name, "body": body.body,
         "at": datetime.now(UTC).isoformat()},
    ]
    if body.direction == "inbound":
        from app.infra.db.repos.notification_repo import record_event  # noqa: PLC0415

        await record_event(
            session, current_user.tenant_id, kind="supplier_reply",
            title="Supplier outreach reply", body=f"{s.name} replied to your outreach.",
            link="/suppliers/network",
        )
    await session.commit()
    return {"status": "logged"}


class SendReplyRequest(StrictModel):
    body: str
    subject: str | None = None


@router.post("/outreach/{supplier_id}/reply", summary="Send a reply to the supplier and log it")
async def send_outreach_reply(
    supplier_id: str, body: SendReplyRequest, current_user: CurrentUser, session: SessionDep
) -> dict[str, str]:
    from datetime import UTC, datetime  # noqa: PLC0415

    repo = SupplierRepository(session, current_user.tenant_id)
    s = await repo.get_by_id(supplier_id)
    if s is None or not s.email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Supplier has no email.")
    from app.infra.email.sender import send_email  # noqa: PLC0415

    await send_email(to=s.email, subject=body.subject or f"Re: enquiry — {s.name}", body=body.body)
    s.outreach_messages = [
        *(s.outreach_messages or []),
        {"direction": "outbound", "sender": "You", "body": body.body, "at": datetime.now(UTC).isoformat()},
    ]
    await session.commit()
    return {"status": "sent"}
