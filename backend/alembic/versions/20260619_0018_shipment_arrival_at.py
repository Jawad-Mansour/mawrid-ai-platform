"""
Feature:  Inventory — exact shipment arrival time
Layer:    Infra / Migration
Module:   alembic.versions.20260619_0018_shipment_arrival_at
Purpose:  shipments.expected_arrival_at — an exact arrival datetime (Beirut wall-clock,
          stored as timestamptz) on top of the date-only expected_arrival_date used by
          the scheduler/calendar. Auto-filled from an agreed email date; editable.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shipments", sa.Column("expected_arrival_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("shipments", "expected_arrival_at")
