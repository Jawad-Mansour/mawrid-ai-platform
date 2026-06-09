"""
Feature:  HITL (Human-in-the-Loop)
Layer:    Test / Unit
Module:   tests.unit.test_hitl_service
Purpose:  Unit tests for the HITL action lifecycle. Verifies: approve/reject/edit
          transitions, keyboard shortcut acceptance criteria (A/R/E), no external
          write without approval, action stays in pending without decision.
Depends:  app.core.hitl.services, conftest fakes
HITL:     All 14 action_types
"""
from __future__ import annotations


class TestHITLLifecycle:
    def test_approve_triggers_external_write(self, fake_email_sender) -> None:
        """Approving a HITL action must allow the downstream write to execute."""
        from app.core.hitl.services import approve_action

        result = approve_action(
            action_id="hitl_001",
            action_type="po_draft_created",
            payload={"to": "supplier@example.com", "subject": "PO #42"},
            email_sender=fake_email_sender,
        )
        assert result.status == "approved"
        assert len(fake_email_sender.sent) == 1

    def test_reject_blocks_external_write(self, fake_email_sender) -> None:
        """Rejecting a HITL action must prevent any external write."""
        from app.core.hitl.services import reject_action

        result = reject_action(action_id="hitl_002", action_type="po_draft_created")
        assert result.status == "rejected"
        assert len(fake_email_sender.sent) == 0

    def test_pending_action_blocks_external_write(self, fake_email_sender) -> None:
        """A HITL action in pending state must not trigger any external write."""
        from app.core.hitl.services import get_action_status

        status = get_action_status(action_id="hitl_003")
        assert status == "pending"
        assert len(fake_email_sender.sent) == 0

    def test_edit_updates_payload(self) -> None:
        """Edit (E shortcut) must update the action payload before approval."""
        from app.core.hitl.services import edit_action

        result = edit_action(
            action_id="hitl_004",
            updates={"subject": "Revised PO #42"},
        )
        assert result.payload["subject"] == "Revised PO #42"
        assert result.status == "pending"
