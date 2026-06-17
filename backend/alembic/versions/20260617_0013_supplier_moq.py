"""
Feature:  Procurement — supplier minimum order quantity
Layer:    Infra / Migration
Module:   alembic.versions.20260617_0013_supplier_moq
Purpose:  suppliers.moq — minimum total units a supplier requires per order. The
          order builder warns if the chosen quantities fall below it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("suppliers", sa.Column("moq", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("suppliers", "moq")
