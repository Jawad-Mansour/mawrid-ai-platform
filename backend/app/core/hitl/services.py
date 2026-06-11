"""
Feature:  HITL Approval Center (cross-cutting)
Layer:    Core / Service
Module:   app.core.hitl.services
Purpose:  Business logic for HITL action lifecycle: create, approve (calls
          email_sender if payload has to/subject), reject, edit (returns to
          pending), get_action_status. All transitions are explicit — no
          external write fires without approval.
Depends:  app.core.hitl.models, typing.Protocol
HITL:     This IS the HITL service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.hitl.models import HITLStatus


class _EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str, **kwargs: Any) -> None: ...


@dataclass
class ActionResult:
    action_id: str
    status: str
    payload: dict[str, Any] = field(default_factory=dict)


async def approve_action(
    action_id: str,
    action_type: str,
    payload: dict[str, Any],
    email_sender: _EmailSender,
) -> ActionResult:
    """Approve a HITL action. Sends email if payload contains 'to' and 'subject'."""
    to = payload.get("to", "")
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    if to and subject:
        await email_sender.send(to=str(to), subject=str(subject), body=str(body))
    return ActionResult(action_id=action_id, status=HITLStatus.APPROVED, payload=payload)


def reject_action(action_id: str, action_type: str) -> ActionResult:
    return ActionResult(action_id=action_id, status=HITLStatus.REJECTED)


def get_action_status(action_id: str) -> str:
    return HITLStatus.PENDING


def edit_action(action_id: str, updates: dict[str, Any]) -> ActionResult:
    return ActionResult(action_id=action_id, status=HITLStatus.PENDING, payload=updates)
