"""
Feature:  Per-sheet catalogues + richer supplier profile
Layer:    Infra / Migration
Module:   alembic.versions.20260617_0012_sheet_catalogues_supplier_profile
Purpose:  - products.document_ids : JSON list of the sheets (documents) a product
            came from, so each uploaded sheet has its own catalogue view.
          - suppliers.description / suppliers.rating : supplier profile fields used
            later when drafting purchase orders / outreach. rating is 0–5 and may be
            updated from feedback.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("document_ids", sa.JSON(), nullable=True))
    op.add_column("suppliers", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("suppliers", sa.Column("rating", sa.Numeric(3, 1), nullable=True))


def downgrade() -> None:
    op.drop_column("suppliers", "rating")
    op.drop_column("suppliers", "description")
    op.drop_column("products", "document_ids")
