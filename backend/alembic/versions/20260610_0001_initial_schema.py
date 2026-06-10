"""initial schema — all tables, RLS, pgvector HNSW index

Revision ID: 0001
Revises:
Create Date: 2026-06-10

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector extension — must exist before Vector columns
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── tenants ──────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("mode", sa.Text, nullable=False, server_default="hybrid"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False, server_default="admin"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_user_email"),
    )
    # ── products ──────────────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("product_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("product_hash", sa.Text, nullable=False),
        sa.Column("product_name", sa.Text, nullable=False),
        sa.Column("sku", sa.Text, nullable=True),
        sa.Column("enrichment_status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("inventory_status", sa.Text, nullable=False, server_default="not_ordered"),
        sa.Column("storefront_status", sa.Text, nullable=False, server_default="not_published"),
        sa.Column("qty_in_stock", sa.Integer, nullable=False, server_default="0"),
        sa.Column("storefront_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("price_history", postgresql.JSON, nullable=False, server_default="[]"),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.UniqueConstraint("tenant_id", "product_hash", name="uq_product_hash_per_tenant"),
    )
    # HNSW index for approximate nearest neighbour search (pgvector)
    op.execute(
        """
        CREATE INDEX ix_product_embedding_hnsw
        ON products
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # ── suppliers ─────────────────────────────────────────────────────────────
    op.create_table(
        "suppliers",
        sa.Column("supplier_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=True),
        sa.Column("phone", sa.Text, nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
    )

    # ── customers ─────────────────────────────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("customer_type", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=True),
        sa.Column("phone", sa.Text, nullable=True),
        sa.Column("payment_history_score", sa.Numeric(3, 2), nullable=False, server_default="1.0"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_customer_email_per_tenant"),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_customer_phone_per_tenant"),
    )

    # ── outbox ────────────────────────────────────────────────────────────────
    op.create_table(
        "outbox",
        sa.Column("event_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("payload", postgresql.JSON, nullable=False),
        sa.Column("processed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_unprocessed", "outbox", ["tenant_id", "processed"])

    # ── graph_edges ───────────────────────────────────────────────────────────
    op.create_table(
        "graph_edges",
        sa.Column("edge_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("target_id", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text, nullable=False),
        sa.Column("relation", sa.Text, nullable=False),
        sa.Column("weight", sa.Numeric(6, 4), nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── order_drafts ──────────────────────────────────────────────────────────
    op.create_table(
        "order_drafts",
        sa.Column("order_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("supplier_id", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
        sa.Column("line_items", postgresql.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── storefront_orders ─────────────────────────────────────────────────────
    op.create_table(
        "storefront_orders",
        sa.Column("order_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("customer_id", sa.Text, nullable=False),
        sa.Column("payment_gateway", sa.Text, nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("items", postgresql.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── consumer_orders ───────────────────────────────────────────────────────
    op.create_table(
        "consumer_orders",
        sa.Column("order_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("customer_id", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("payment_gateway", sa.Text, nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── consumer_order_items ──────────────────────────────────────────────────
    op.create_table(
        "consumer_order_items",
        sa.Column("item_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("order_id", sa.Text, sa.ForeignKey("consumer_orders.order_id"), nullable=False),
        sa.Column("product_id", sa.Text, nullable=False),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
    )

    # ── invoices ──────────────────────────────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("invoice_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("direction", sa.Text, nullable=False),
        sa.Column("invoice_type", sa.Text, nullable=False),
        sa.Column("amount_due", sa.Numeric(12, 2), nullable=False),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("payment_terms_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("status", sa.Text, nullable=False, server_default="unpaid"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pdf_key", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── dunning_sequences ─────────────────────────────────────────────────────
    op.create_table(
        "dunning_sequences",
        sa.Column("sequence_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("invoice_id", sa.Text, nullable=False),
        sa.Column("track", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── hitl_actions ──────────────────────────────────────────────────────────
    op.create_table(
        "hitl_actions",
        sa.Column("action_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("action_type", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("payload", postgresql.JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_user_id", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_hitl_actions_tenant_status",
        "hitl_actions",
        ["tenant_id", "status", "action_type"],
    )

    # ── Row-Level Security ─────────────────────────────────────────────────────
    # Enable RLS on every tenant-scoped table.
    # Policy: rows are visible only when app.current_tenant_id matches tenant_id.
    # Note: superuser (mawrid) bypasses RLS — only the app user is restricted.
    _rls_tables = [
        "users",
        "products",
        "suppliers",
        "customers",
        "outbox",
        "graph_edges",
        "order_drafts",
        "storefront_orders",
        "consumer_orders",
        "consumer_order_items",
        "invoices",
        "dunning_sequences",
        "hitl_actions",
    ]

    for table in _rls_tables:
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
    _tables = [
        "hitl_actions",
        "dunning_sequences",
        "invoices",
        "consumer_order_items",
        "consumer_orders",
        "storefront_orders",
        "order_drafts",
        "graph_edges",
        "outbox",
        "customers",
        "suppliers",
        "products",
        "users",
        "tenants",
    ]
    for table in _tables:
        op.drop_table(table)

    op.execute("DROP EXTENSION IF EXISTS vector")
