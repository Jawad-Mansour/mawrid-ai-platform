"""
Feature:  Connect Gmail — per-user OAuth flow
Layer:    API / Router
Module:   app.api.google_auth
Purpose:  Lets any user connect their own Gmail (no password). /start returns the Google
          consent URL (signed state carries the tenant); Google redirects back to /callback
          (mounted at ROOT to match the registered redirect URI) which exchanges the code,
          stores the refresh token per tenant, and bounces to the Settings page. /status and
          /disconnect manage the connection.
Depends:  app.infra.email.gmail, app.infra.secrets.vault, gmail_connections table
HITL:     None.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.core.config import get_settings
from app.infra.db.models.gmail import GmailConnection
from app.infra.email.gmail import (
    AUTH_URL,
    SCOPES,
    access_token_from_refresh,
    exchange_code,
    get_email_address,
    google_config,
    google_enabled,
)
from app.infra.secrets.vault import get_secrets

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth/google", tags=["google"])
callback_router = APIRouter(tags=["google"])  # mounted at root (no /api/v1 prefix)

_STATE_TTL = 600  # seconds


def _sign_state(tenant_id: str) -> str:
    secret = get_secrets().jwt_private_key.encode()
    payload = base64.urlsafe_b64encode(json.dumps({"t": tenant_id, "ts": int(time.time())}).encode()).decode()
    sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"


def _verify_state(state: str) -> str | None:
    try:
        payload, sig = state.rsplit(".", 1)
        secret = get_secrets().jwt_private_key.encode()
        expected = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload))
        if int(time.time()) - int(data["ts"]) > _STATE_TTL:
            return None
        return str(data["t"])
    except Exception:  # noqa: BLE001
        return None


class StartResponse(StrictModel):
    url: str


class StatusResponse(StrictModel):
    connected: bool
    email: str | None = None
    configured: bool


@router.get("/start", response_model=StartResponse, summary="Begin connecting the user's Gmail")
async def start(current_user: CurrentUser) -> StartResponse:
    if not google_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth is not configured on the server.")
    settings = get_settings()
    cfg = google_config()
    client_id = cfg[0] if cfg else ""
    params = {
        "client_id": client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": _sign_state(current_user.tenant_id),
    }
    return StartResponse(url=f"{AUTH_URL}?{urlencode(params)}")


@callback_router.get("/auth/google/callback", include_in_schema=False)
async def callback(code: str | None = None, state: str | None = None, error: str | None = None, *, session: SessionDep) -> RedirectResponse:
    settings = get_settings()
    fail = RedirectResponse(url=f"{settings.frontend_url}/settings?gmail=error")
    if error or not code or not state:
        return fail
    tenant_id = _verify_state(state)
    if not tenant_id:
        return fail

    tokens = await exchange_code(code, settings.google_redirect_uri)
    if not tokens:
        return fail
    access_token = str(tokens.get("access_token") or "")
    refresh_token = str(tokens.get("refresh_token") or "")
    email = (await get_email_address(access_token)) or "your Gmail"

    existing = await session.get(GmailConnection, tenant_id)
    if existing is not None:
        existing.email = email
        if refresh_token:  # Google omits it on re-consent without prompt=consent
            existing.refresh_token = refresh_token
    elif refresh_token:
        session.add(GmailConnection(tenant_id=tenant_id, email=email, refresh_token=refresh_token))
    else:
        return fail
    await session.commit()
    logger.info("gmail_connected", tenant_id=tenant_id, email=email)
    return RedirectResponse(url=f"{settings.frontend_url}/settings?gmail=connected")


@router.get("/status", response_model=StatusResponse, summary="Is the user's Gmail connected?")
async def gmail_status(current_user: CurrentUser, session: SessionDep) -> StatusResponse:
    conn = await session.get(GmailConnection, current_user.tenant_id)
    return StatusResponse(connected=conn is not None, email=conn.email if conn else None, configured=google_enabled())


@router.post("/test", summary="Verify the connection still works (refreshes a token)")
async def gmail_test(current_user: CurrentUser, session: SessionDep) -> dict[str, bool]:
    conn = await session.get(GmailConnection, current_user.tenant_id)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Gmail connected.")
    ok = bool(await access_token_from_refresh(conn.refresh_token))
    return {"ok": ok}


@router.delete("/disconnect", status_code=status.HTTP_204_NO_CONTENT, summary="Disconnect the user's Gmail")
async def disconnect(current_user: CurrentUser, session: SessionDep) -> None:
    conn = await session.get(GmailConnection, current_user.tenant_id)
    if conn is not None:
        await session.delete(conn)
        await session.commit()
