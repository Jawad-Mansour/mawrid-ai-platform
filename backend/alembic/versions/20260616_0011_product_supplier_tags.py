"""
Feature:  Catalog Enrichment — per-supplier / per-sheet catalogues
Layer:    Infra / Migration
Module:   alembic.versions.20260616_0011_product_supplier_tags
Purpose:  Track which supplier(s) a product came from so the catalogue can be
          filtered by supplier, and a product that already exists (pre-enriched)
          can be associated with a new supplier's sheet without re-enriching.
          - documents.supplier_name : the supplier entered at upload time
          - products.supplier_names : JSON list of supplier names that include it
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("supplier_name", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("supplier_names", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "supplier_names")
    op.drop_column("documents", "supplier_name")
