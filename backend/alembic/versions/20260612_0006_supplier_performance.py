"""supplier performance counters — discrepancy_count, damage_count

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-12

Adds to suppliers:
  - discrepancy_count  INTEGER NOT NULL DEFAULT 0
  - damage_count       INTEGER NOT NULL DEFAULT 0

Used by Phase 3.4 goods-receiving to flag supplier performance events,
and by Phase 7 supplier scorer as feature inputs.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suppliers",
        sa.Column(
            "discrepancy_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "suppliers",
        sa.Column(
            "damage_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("suppliers", "damage_count")
    op.drop_column("suppliers", "discrepancy_count")
