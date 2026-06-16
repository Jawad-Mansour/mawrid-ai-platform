"""
Feature:  Catalog Enrichment + Procurement
Layer:    Infra / Migration
Module:   alembic.versions.20260616_0010_enrichment_sources_supplier_location
Purpose:  Add products.source_urls (JSON list of {title,url} reference links
          surfaced like an AI-overview "sources" block) and suppliers.location
          (captured at upload time alongside supplier name).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("source_urls", sa.JSON(), nullable=True))
    op.add_column("suppliers", sa.Column("location", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("suppliers", "location")
    op.drop_column("products", "source_urls")
