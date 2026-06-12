"""
Feature:  n8n Automation (cross-cutting)
Layer:    Infra / n8n
Module:   app.infra.n8n.client
Purpose:  Best-effort n8n webhook notifier. Fires event payloads to n8n
          webhook trigger URLs from backend code. Never raises — n8n is
          optional infrastructure; if it's down, operations continue normally.
          Backend calls fire_event() after key state transitions so n8n can
          orchestrate follow-on automation.
Depends:  httpx, app.core.config
HITL:     None — fires notifications only, no write actions.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = 5.0  # seconds — fast fail if n8n is down


async def fire_event(webhook_path: str, payload: dict[str, Any]) -> None:
    """
    POST payload to n8n webhook at {n8n_base_url}/webhook/{webhook_path}.

    Best-effort: logs on failure but never raises. Callers must not depend
    on this succeeding — it is a notification, not a required side-effect.
    """
    settings = get_settings()
    url = f"{settings.n8n_base_url}/webhook/{webhook_path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-N8N-Service-Token": settings.n8n_service_token,
                },
            )
            if resp.status_code >= 400:
                logger.warning(
                    "n8n_event_rejected",
                    extra={"path": webhook_path, "status": resp.status_code},
                )
            else:
                logger.debug("n8n_event_fired", extra={"path": webhook_path})
    except Exception as exc:
        logger.warning(
            "n8n_event_failed",
            extra={"path": webhook_path, "error": str(exc)},
        )
