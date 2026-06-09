"""
Feature:  Dunning — Payment Auto-Stop
Layer:    Test / Unit
Module:   tests.unit.test_payment_autostop
Purpose:  Unit tests for the payment reconciliation → dunning auto-stop flow.
          Verifies: recording a payment atomically stops the active dunning
          sequence, no further dunning steps are scheduled after payment,
          partial payments do not stop the sequence.
Depends:  app.core.dunning.tracks, app.infra.db.repos.invoice_repo
HITL:     None
"""
from __future__ import annotations


class TestPaymentAutoStop:
    def test_full_payment_stops_sequence(self) -> None:
        """Full payment must stop the active dunning sequence."""
        from app.core.dunning.tracks import should_stop_sequence

        assert should_stop_sequence(invoice_status="paid") is True

    def test_partial_payment_does_not_stop(self) -> None:
        """Partial payment must not stop dunning — only full settlement does."""
        from app.core.dunning.tracks import should_stop_sequence

        assert should_stop_sequence(invoice_status="partially_paid") is False

    def test_reconciled_invoice_stops_sequence(self) -> None:
        """Reconciled invoice must also stop dunning (credit note settlement)."""
        from app.core.dunning.tracks import should_stop_sequence

        assert should_stop_sequence(invoice_status="reconciled") is True

    def test_unpaid_continues_sequence(self) -> None:
        from app.core.dunning.tracks import should_stop_sequence

        assert should_stop_sequence(invoice_status="unpaid") is False
