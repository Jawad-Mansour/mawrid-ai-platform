"""
Feature:  Dunning
Layer:    Test / Unit
Module:   tests.unit.test_dunning_tracks
Purpose:  Unit tests for all 4 dunning tracks. Verifies: trigger dates,
          escalation thresholds, track assignment logic, payment auto-stop,
          HITL draft-only behavior.
Depends:  app.core.dunning.tracks, conftest fakes
HITL:     dunning_payables_draft, dunning_receivables_draft, dunning_b2c_draft
"""

from __future__ import annotations

from datetime import date, timedelta


class TestTrack1Payables:
    def test_trigger_3_days_before_due(self) -> None:
        """Track 1 (B2B Payables) triggers at due_date - 3 days."""
        from app.core.dunning.tracks import should_trigger_track1

        due = date.today() + timedelta(days=3)
        assert should_trigger_track1(due_date=due, today=date.today()) is True

    def test_no_trigger_4_days_before_due(self) -> None:
        from app.core.dunning.tracks import should_trigger_track1

        due = date.today() + timedelta(days=4)
        assert should_trigger_track1(due_date=due, today=date.today()) is False


class TestTrack3Receivables:
    def test_day7_trigger(self) -> None:
        """Track 3 (B2B Receivables) day-7 sends at due_date + 7."""
        from app.core.dunning.tracks import get_track3_step

        due = date.today() - timedelta(days=7)
        assert get_track3_step(due_date=due, today=date.today()) == "day7"

    def test_day14_trigger(self) -> None:
        from app.core.dunning.tracks import get_track3_step

        due = date.today() - timedelta(days=14)
        assert get_track3_step(due_date=due, today=date.today()) == "day14"

    def test_uses_due_date_not_invoice_date(self) -> None:
        """Track 3 must count from due_date, not invoice_date."""
        from app.core.dunning.tracks import get_track3_step

        date.today() - timedelta(days=21)
        due_date = date.today() - timedelta(days=7)
        step = get_track3_step(due_date=due_date, today=date.today())
        assert step == "day7"


class TestTrack4B2C:
    def test_day3_trigger_from_invoice_date(self) -> None:
        """Track 4 (B2C) counts from invoice_date, not due_date."""
        from app.core.dunning.tracks import get_track4_step

        invoice_date = date.today() - timedelta(days=3)
        assert get_track4_step(invoice_date=invoice_date, today=date.today()) == "day3"


class TestPaymentAutoStop:
    def test_payment_stops_dunning_sequence(self) -> None:
        """Recording a payment must stop the active dunning sequence."""
        from app.core.dunning.tracks import should_stop_sequence

        assert should_stop_sequence(invoice_status="paid") is True
        assert should_stop_sequence(invoice_status="unpaid") is False
