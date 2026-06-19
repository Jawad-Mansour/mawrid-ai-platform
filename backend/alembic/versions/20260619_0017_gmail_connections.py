"""
Feature:  Connect Gmail — per-tenant OAuth mailbox connection
Layer:    Infra / Migration
Module:   alembic.versions.20260619_0017_gmail_connections
Purpose:  gmail_connections — stores each tenant's connected Gmail (address + OAuth refresh
          token) so Mawrid can send POs/outreach/dunning AS the user (inbox deliverability)
          and read their replies back to auto-detect/thread them. One row per tenant.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmail_connections",
        sa.Column("tenant_id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("gmail_connections")
