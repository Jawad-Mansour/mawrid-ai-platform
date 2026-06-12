"""supplier delivery events table for scorer feature extraction

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-12

Adds:
  - supplier_delivery_events  table (per-event performance data)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_delivery_events",
        sa.Column("delivery_event_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("supplier_id", sa.Text, nullable=False),
        sa.Column("order_id", sa.Text, nullable=True),
        sa.Column("promised_date", sa.Date, nullable=False),
        sa.Column("delivered_date", sa.Date, nullable=True),
        sa.Column("items_ordered", sa.Integer, nullable=False, server_default="1"),
        sa.Column("items_received", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_damaged", sa.Integer, nullable=False, server_default="0"),
        sa.Column("price_agreed", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("price_billed", sa.Numeric(12, 4), nullable=True),
        sa.Column("response_time_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_delivery_events_supplier",
        "supplier_delivery_events",
        ["tenant_id", "supplier_id"],
    )
    op.execute("ALTER TABLE supplier_delivery_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_delivery_events ON supplier_delivery_events
        USING (tenant_id = current_setting('app.tenant_id', TRUE))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delivery_events ON supplier_delivery_events")
    op.drop_index("ix_delivery_events_supplier", table_name="supplier_delivery_events")
    op.drop_table("supplier_delivery_events")
