"""
Feature:  Procurement — PO response tracking (Screen 3)
Layer:    Infra / Migration
Module:   alembic.versions.20260617_0014_po_message_thread
Purpose:  purchase_orders.messages — JSON list of the email thread for a PO
          (outbound request + inbound supplier replies), so the importer can
          track the conversation against each order.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("messages", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("purchase_orders", "messages")
