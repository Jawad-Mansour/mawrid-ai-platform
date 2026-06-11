"""procurement — purchase_orders, shipments, goods_received + supplier language/currency

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-11

Adds:
  - suppliers: language (ar/fr/en), currency columns
  - products: retail_price, reorder_threshold columns
  - order_drafts: notes, desired_delivery_date, submitted_at columns
  - New table: purchase_orders
  - New table: shipments
  - New table: goods_received
  - RLS on new tables
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── suppliers: language + currency ────────────────────────────────────────
    op.add_column(
        "suppliers",
        sa.Column("language", sa.Text, nullable=False, server_default="en"),
    )
    op.add_column(
        "suppliers",
        sa.Column("currency", sa.Text, nullable=False, server_default="USD"),
    )

    # ── products: retail_price + reorder_threshold ────────────────────────────
    op.add_column("products", sa.Column("retail_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("products", sa.Column("reorder_threshold", sa.Integer, nullable=True))

    # ── order_drafts: extra columns ───────────────────────────────────────────
    op.add_column("order_drafts", sa.Column("notes", sa.Text, nullable=True))
    op.add_column("order_drafts", sa.Column("desired_delivery_date", sa.Date, nullable=True))
    op.add_column(
        "order_drafts",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── purchase_orders ───────────────────────────────────────────────────────
    op.create_table(
        "purchase_orders",
        sa.Column("po_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("order_draft_id", sa.Text, nullable=False),
        sa.Column("supplier_id", sa.Text, nullable=False),
        sa.Column("po_number", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending_hitl"),
        sa.Column("line_items", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.Text, nullable=False, server_default="USD"),
        sa.Column("requested_delivery_date", sa.Date, nullable=True),
        sa.Column("po_text", sa.Text, nullable=True),
        sa.Column("hitl_action_id", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── shipments ─────────────────────────────────────────────────────────────
    op.create_table(
        "shipments",
        sa.Column("shipment_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("po_id", sa.Text, nullable=False),
        sa.Column("carrier", sa.Text, nullable=True),
        sa.Column("tracking_number", sa.Text, nullable=True),
        sa.Column("expected_arrival_date", sa.Date, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="pending_shipment"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── goods_received ────────────────────────────────────────────────────────
    op.create_table(
        "goods_received",
        sa.Column("receiving_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("shipment_id", sa.Text, nullable=False, unique=True),
        sa.Column("line_items", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("received_by", sa.Text, nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── RLS on new tables ─────────────────────────────────────────────────────
    for table in ("purchase_orders", "shipments", "goods_received"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.current_tenant_id', true))
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true))
            """
        )


def downgrade() -> None:
    op.drop_table("goods_received")
    op.drop_table("shipments")
    op.drop_table("purchase_orders")

    op.drop_column("order_drafts", "submitted_at")
    op.drop_column("order_drafts", "desired_delivery_date")
    op.drop_column("order_drafts", "notes")

    op.drop_column("products", "reorder_threshold")
    op.drop_column("products", "retail_price")

    op.drop_column("suppliers", "currency")
    op.drop_column("suppliers", "language")
