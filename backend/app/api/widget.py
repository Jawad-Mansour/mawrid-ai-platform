"""
Feature:  Embeddable Storefront Widget
Layer:    API / Router
Module:   app.api.widget
Purpose:  Signed widget token issuance, static widget.js delivery, and
          allowed-origins management.  The widget JWT scope is "widget"
          (vs "access" for regular auth tokens) so chat endpoints can
          enforce origin checks before routing to the RAG pipeline.
Depends:  app.api.deps, app.infra.db.repos.tenant_repo,
          app.infra.secrets.vault, pyjwt
HITL:     None.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.infra.db.repos.tenant_repo import TenantRepo
from app.infra.secrets.vault import get_secrets
from app.rag.pipeline import run_rag

router = APIRouter(prefix="/widget", tags=["widget"])

_WIDGET_TOKEN_TTL = timedelta(minutes=15)
_ALGORITHM = "RS256"

# ── Embedded widget.js ─────────────────────────────────────────────────────────

_WIDGET_JS = """\
/* Mawrid Storefront Widget — self-contained floating chatbot embed.
 * Usage: <script src="/api/v1/widget/widget.js" data-token="<widget_jwt>"></script>
 * The data-token attribute must contain a valid widget JWT obtained from
 * GET /api/v1/widget/token (15-minute expiry; auto-refreshed every 10 min).
 */
(function () {
  var script = document.currentScript;
  if (!script) { return; }
  var token = script.dataset.token || '';
  var apiBase = script.dataset.api || (window.location.origin);
  var PRIMARY = '#0070f3';
  var BTN_ID = 'mawrid-widget-btn';
  var PANEL_ID = 'mawrid-widget-panel';

  function css(el, styles) {
    Object.assign(el.style, styles);
  }

  /* ── Floating button ────────────────────────────────────────────── */
  var btn = document.createElement('button');
  btn.id = BTN_ID;
  btn.setAttribute('aria-label', 'Open chat');
  btn.textContent = '\\uD83D\\uDCAC';
  css(btn, {
    position: 'fixed', bottom: '20px', right: '20px',
    width: '56px', height: '56px', borderRadius: '50%',
    background: PRIMARY, color: '#fff', fontSize: '22px',
    border: 'none', cursor: 'pointer', zIndex: '2147483647',
    boxShadow: '0 4px 14px rgba(0,0,0,0.2)', transition: 'transform .15s',
    lineHeight: '1', display: 'flex', alignItems: 'center', justifyContent: 'center',
  });

  /* ── Chat panel ─────────────────────────────────────────────────── */
  var panel = document.createElement('div');
  panel.id = PANEL_ID;
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'Product assistant');
  css(panel, {
    display: 'none', position: 'fixed', bottom: '90px', right: '20px',
    width: '360px', height: '520px', background: '#fff', borderRadius: '12px',
    boxShadow: '0 8px 32px rgba(0,0,0,0.18)', zIndex: '2147483646',
    flexDirection: 'column', overflow: 'hidden', fontFamily: 'system-ui, sans-serif',
  });

  /* header */
  var header = document.createElement('div');
  css(header, {
    background: PRIMARY, color: '#fff', padding: '12px 16px',
    fontWeight: '600', fontSize: '15px', display: 'flex',
    justifyContent: 'space-between', alignItems: 'center',
  });
  header.textContent = 'Product assistant';
  var closeBtn = document.createElement('button');
  closeBtn.textContent = '\\u00D7';
  css(closeBtn, {
    background: 'none', border: 'none', color: '#fff',
    fontSize: '20px', cursor: 'pointer', lineHeight: '1',
  });
  header.appendChild(closeBtn);

  /* message list */
  var msgList = document.createElement('div');
  css(msgList, {
    flex: '1', overflowY: 'auto', padding: '12px 16px', display: 'flex',
    flexDirection: 'column', gap: '8px',
  });

  /* input row */
  var inputRow = document.createElement('form');
  css(inputRow, { display: 'flex', padding: '8px', borderTop: '1px solid #eee', gap: '6px' });
  var input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'Ask about a product…';
  css(input, {
    flex: '1', padding: '8px 12px', borderRadius: '20px',
    border: '1px solid #ddd', fontSize: '14px', outline: 'none',
  });
  var sendBtn = document.createElement('button');
  sendBtn.type = 'submit';
  sendBtn.textContent = 'Send';
  css(sendBtn, {
    background: PRIMARY, color: '#fff', border: 'none',
    borderRadius: '20px', padding: '8px 16px', cursor: 'pointer', fontSize: '14px',
  });
  inputRow.appendChild(input);
  inputRow.appendChild(sendBtn);

  panel.appendChild(header);
  panel.appendChild(msgList);
  panel.appendChild(inputRow);

  /* ── Helpers ─────────────────────────────────────────────────────── */
  function addMsg(text, role) {
    var m = document.createElement('div');
    m.textContent = text;
    css(m, {
      padding: '8px 12px', borderRadius: '12px', maxWidth: '85%', fontSize: '14px',
      background: role === 'user' ? PRIMARY : '#f0f0f0',
      color: role === 'user' ? '#fff' : '#111',
      alignSelf: role === 'user' ? 'flex-end' : 'flex-start',
    });
    msgList.appendChild(m);
    msgList.scrollTop = msgList.scrollHeight;
  }

  function showExpired() {
    addMsg('Session expired. Please refresh the page to continue.', 'bot');
    input.disabled = true;
    sendBtn.disabled = true;
  }

  /* ── Chat request ────────────────────────────────────────────────── */
  inputRow.addEventListener('submit', function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (!q) { return; }
    addMsg(q, 'user');
    input.value = '';
    input.disabled = true;
    sendBtn.disabled = true;

    fetch(apiBase + '/api/v1/widget/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + token,
      },
      body: JSON.stringify({ query: q }),
    })
      .then(function (r) {
        if (r.status === 401 || r.status === 403) { showExpired(); return null; }
        return r.json();
      })
      .then(function (data) {
        if (data) { addMsg(data.answer || 'No answer returned.', 'bot'); }
      })
      .catch(function () { addMsg('Error contacting assistant. Please try again.', 'bot'); })
      .finally(function () { input.disabled = false; sendBtn.disabled = false; });
  });

  /* ── Toggle ──────────────────────────────────────────────────────── */
  function toggle(open) {
    panel.style.display = open ? 'flex' : 'none';
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  btn.addEventListener('click', function () {
    toggle(panel.style.display === 'none');
  });
  closeBtn.addEventListener('click', function () { toggle(false); });

  /* ── Token auto-refresh every 10 min ─────────────────────────────── */
  setInterval(function () {
    fetch(apiBase + '/api/v1/widget/token', {
      headers: { 'Authorization': 'Bearer ' + token },
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d && d.token) { token = d.token; } });
  }, 600000);

  document.body.appendChild(btn);
  document.body.appendChild(panel);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      document.body.appendChild(btn);
      document.body.appendChild(panel);
    });
  }
})();
"""


# ── Response models ────────────────────────────────────────────────────────────


class WidgetTokenResponse(StrictModel):
    token: str
    expires_in: int  # seconds


class WidgetSettingsRequest(StrictModel):
    allowed_origins: str  # comma-separated, e.g. "https://shop.example.com"


class WidgetChatRequest(StrictModel):
    query: str


class WidgetChatResponse(StrictModel):
    answer: str
    query: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/token",
    response_model=WidgetTokenResponse,
    summary="Issue a short-lived widget JWT (scope=widget, 15-min expiry)",
)
async def get_widget_token(current_user: CurrentUser) -> WidgetTokenResponse:
    """
    Admin-only endpoint. Returns a signed RS256 JWT for embedding the
    storefront widget on third-party sites. The token is scoped to
    'widget' (not 'access') — consumer chat uses it anonymously.
    """
    secrets = get_secrets()
    now = datetime.now(UTC)
    payload = {
        "tenant_id": current_user.tenant_id,
        "scope": "widget",
        "iat": int(now.timestamp()),
        "exp": int((now + _WIDGET_TOKEN_TTL).timestamp()),
    }
    token = jwt.encode(payload, secrets.jwt_private_key, algorithm=_ALGORITHM)
    return WidgetTokenResponse(
        token=token,
        expires_in=int(_WIDGET_TOKEN_TTL.total_seconds()),
    )


@router.get(
    "/widget.js",
    summary="Embeddable widget script (public — no auth required)",
)
async def get_widget_js() -> Response:
    return Response(
        content=_WIDGET_JS,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.patch(
    "/settings",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update tenant's widget allowed_origins (comma-separated domain list)",
)
async def update_widget_settings(
    body: WidgetSettingsRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> None:
    repo = TenantRepo(session)
    await repo.update_allowed_origins(current_user.tenant_id, body.allowed_origins or None)
    await session.commit()


@router.post(
    "/chat",
    response_model=WidgetChatResponse,
    summary="Widget chat — origin-checked, published-scope RAG (widget JWT required)",
)
async def widget_chat(
    body: WidgetChatRequest,
    request: Request,
    session: SessionDep,
) -> WidgetChatResponse:
    """
    Chat endpoint for embedded widget. Requires a widget-scoped JWT in the
    Authorization header. Validates the request Origin against the tenant's
    allowed_origins before running RAG on the published catalog.
    """
    secrets = get_secrets()

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing widget token")

    token_str = auth_header[7:]
    try:
        payload = jwt.decode(token_str, secrets.jwt_public_key, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid widget token") from exc

    if payload.get("scope") != "widget":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token scope must be 'widget'")

    tenant_id: str = payload.get("tenant_id", "")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing tenant_id in token")

    # Origin check
    origin = request.headers.get("Origin", "")
    if origin:
        repo = TenantRepo(session)
        tenant = await repo.get_by_id(tenant_id)
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant not found")
        if not tenant.allowed_origins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Widget embedding not configured for this tenant",
            )
        allowed = {o.strip() for o in tenant.allowed_origins.split(",") if o.strip()}
        if origin not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Origin '{origin}' not in allowed_origins",
            )

    # Run RAG on published scope
    try:
        result = await run_rag(
            query=body.query,
            tenant_id=tenant_id,
            scope="consumer",
            session=session,
        )
        answer = result.answer
    except Exception:
        answer = "I'm sorry, I couldn't find an answer to that. Please try again."

    return WidgetChatResponse(answer=answer, query=body.query)
