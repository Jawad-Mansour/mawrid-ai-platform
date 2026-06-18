"""
Feature:  Activity/Notifications + Supplier & Factory Network
Layer:    Infra / Migration
Module:   alembic.versions.20260618_0015_supplier_network
Purpose:  - notifications: per-tenant real event log (Activity page).
          - reference_factories: global verified manufacturer dataset (real coords).
          - suppliers: add geo + network columns (lat/lon, category, website, logo,
            offering, condition, kind, source, region, outreach_messages).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False, index=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_notifications_tenant_created", "notifications", ["tenant_id", "created_at"])

    op.create_table(
        "reference_factories",
        sa.Column("factory_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("subcategory", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("offering", sa.Text(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=False, server_default="new"),
        sa.Column("region", sa.Text(), nullable=False, server_default="europe"),
        sa.Column("email", sa.Text(), nullable=True),
    )
    op.create_index("ix_reference_factories_region_cat", "reference_factories", ["region", "category"])

    for col, type_, default in [
        ("latitude", sa.Float(), None),
        ("longitude", sa.Float(), None),
        ("category", sa.Text(), None),
        ("website", sa.Text(), None),
        ("logo_url", sa.Text(), None),
        ("offering", sa.Text(), None),
        ("condition", sa.Text(), None),
        ("kind", sa.Text(), "supplier"),
        ("source", sa.Text(), "saved"),
        ("region", sa.Text(), None),
        ("outreach_messages", sa.JSON(), None),
    ]:
        op.add_column(
            "suppliers",
            sa.Column(col, type_, nullable=True, server_default=default),
        )


def downgrade() -> None:
    for col in [
        "latitude", "longitude", "category", "website", "logo_url", "offering",
        "condition", "kind", "source", "region", "outreach_messages",
    ]:
        op.drop_column("suppliers", col)
    op.drop_index("ix_reference_factories_region_cat", table_name="reference_factories")
    op.drop_table("reference_factories")
    op.drop_index("ix_notifications_tenant_created", table_name="notifications")
    op.drop_table("notifications")
