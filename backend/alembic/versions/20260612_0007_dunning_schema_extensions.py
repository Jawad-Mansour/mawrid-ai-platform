"""dunning schema extensions — customer segment/language/count + invoice contact fields

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-12

Adds to customers:
  - segment              TEXT NOT NULL DEFAULT 'Regular'  (VIP|Regular|At-Risk|Dormant)
  - language             TEXT NOT NULL DEFAULT 'en'       (ISO 639-1)
  - previous_dunning_count INTEGER NOT NULL DEFAULT 0

Adds to invoices:
  - contact_email        TEXT NULL    (fallback when no supplier/customer FK)
  - contact_name         TEXT NULL
  - contact_language     TEXT NULL
  - customer_id          TEXT NULL    (FK-like, no constraint — resolved at app layer)
  - supplier_id          TEXT NULL
  - order_id             TEXT NULL    (B2C order reference for payment link)
  - currency             TEXT NOT NULL DEFAULT 'USD'
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── customers extensions ──────────────────────────────────────────────────
    op.add_column(
        "customers",
        sa.Column("segment", sa.Text, nullable=False, server_default="Regular"),
    )
    op.add_column(
        "customers",
        sa.Column("language", sa.Text, nullable=False, server_default="en"),
    )
    op.add_column(
        "customers",
        sa.Column("previous_dunning_count", sa.Integer, nullable=False, server_default="0"),
    )

    # ── invoices extensions ───────────────────────────────────────────────────
    op.add_column("invoices", sa.Column("contact_email", sa.Text, nullable=True))
    op.add_column("invoices", sa.Column("contact_name", sa.Text, nullable=True))
    op.add_column("invoices", sa.Column("contact_language", sa.Text, nullable=True))
    op.add_column("invoices", sa.Column("customer_id", sa.Text, nullable=True))
    op.add_column("invoices", sa.Column("supplier_id", sa.Text, nullable=True))
    op.add_column("invoices", sa.Column("order_id", sa.Text, nullable=True))
    op.add_column(
        "invoices",
        sa.Column("currency", sa.Text, nullable=False, server_default="USD"),
    )


def downgrade() -> None:
    # invoices
    op.drop_column("invoices", "currency")
    op.drop_column("invoices", "order_id")
    op.drop_column("invoices", "supplier_id")
    op.drop_column("invoices", "customer_id")
    op.drop_column("invoices", "contact_language")
    op.drop_column("invoices", "contact_name")
    op.drop_column("invoices", "contact_email")

    # customers
    op.drop_column("customers", "previous_dunning_count")
    op.drop_column("customers", "language")
    op.drop_column("customers", "segment")
