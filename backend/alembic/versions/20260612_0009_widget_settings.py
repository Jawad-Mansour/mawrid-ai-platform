"""
Feature:  Embeddable Storefront Widget
Layer:    Infra / Migration
Module:   alembic.versions.20260612_0009_widget_settings
Purpose:  Add allowed_origins column to tenants for per-tenant widget embed
          domain whitelist. Nullable TEXT — null means widget embedding
          disabled for that tenant.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("allowed_origins", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "allowed_origins")
