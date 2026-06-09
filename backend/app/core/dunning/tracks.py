"""
Feature:  Dunning Engine (4 Tracks)
Layer:    Core / Service
Module:   app.core.dunning.tracks
Purpose:  Track rules engine: defines trigger conditions, message types, and
          escalation sequences for all 4 tracks.
          Track 1 (Payables): due_date - 3 days, APScheduler daily check.
          Track 2 (Disputes): on-demand, Hybrid + Wholesale Only modes only.
          Track 3 (Receivables): Day 7/14/21 overdue from due_date.
          Track 4 (B2C): Day 3/7/14 from invoice_date, email + SMS.
          All tracks create HITL actions — nothing sent without approval.
Depends:  app.core.dunning.models, app.core.hitl.services
HITL:     dunning_payables_advance, dunning_disputes_on_demand,
          dunning_receivables_day7/14/21, dunning_b2c_day3/7/14
"""

from datetime import date

_TRACK3_STEPS = {7: "day7", 14: "day14", 21: "day21"}
_TRACK4_STEPS = {3: "day3", 7: "day7", 14: "day14"}
_STOP_STATUSES = frozenset({"paid", "reconciled"})


def should_trigger_track1(due_date: date, today: date) -> bool:
    return (due_date - today).days == 3


def get_track3_step(due_date: date, today: date) -> str | None:
    return _TRACK3_STEPS.get((today - due_date).days)


def get_track4_step(invoice_date: date, today: date) -> str | None:
    return _TRACK4_STEPS.get((today - invoice_date).days)


def should_stop_sequence(invoice_status: str) -> bool:
    return invoice_status in _STOP_STATUSES
