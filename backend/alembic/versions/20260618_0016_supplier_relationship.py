"""
Feature:  Supplier lifecycle — prospect vs active
Layer:    Infra / Migration
Module:   alembic.versions.20260618_0016_supplier_relationship
Purpose:  suppliers.relationship — 'active' (we do business with them) vs 'prospect'
          (discovered / outreach only). Promotes to 'active' on enrich or first order.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suppliers",
        sa.Column("relationship", sa.Text(), nullable=False, server_default="active"),
    )


def downgrade() -> None:
    op.drop_column("suppliers", "relationship")
