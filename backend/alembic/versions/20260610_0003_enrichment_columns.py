"""enrichment columns — products, documents, review_queue tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-10

Adds:
  - products: description, specifications (JSONB), image_path, enrichment_source,
              enrichment_confidence, currency
  - New table: documents (document_id = SHA-256 of file bytes, dedup key + PK)
  - New table: review_queue (failed rows land here, no product row created)
  - RLS policies on both new tables
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── products: enrichment output columns ──────────────────────────────────
    op.add_column("products", sa.Column("description", sa.Text, nullable=True))
    op.add_column(
        "products", sa.Column("specifications", postgresql.JSONB, nullable=True)
    )
    op.add_column("products", sa.Column("image_path", sa.Text, nullable=True))
    op.add_column("products", sa.Column("enrichment_source", sa.Text, nullable=True))
    op.add_column(
        "products", sa.Column("enrichment_confidence", sa.Text, nullable=True)
    )
    op.add_column("products", sa.Column("currency", sa.Text, nullable=True))

    # ── documents ─────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("document_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("mime_type", sa.Text, nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("row_counts", postgresql.JSONB, nullable=True),
        sa.Column("parsed_rows", postgresql.JSONB, nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── review_queue ──────────────────────────────────────────────────────────
    op.create_table(
        "review_queue",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False, index=True),
        sa.Column("document_id", sa.Text, nullable=False, index=True),
        sa.Column("raw_row", postgresql.JSONB, nullable=False),
        sa.Column("failure_reason", sa.Text, nullable=False),
        sa.Column(
            "status", sa.Text, nullable=False, server_default="pending_review"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── RLS on new tables ─────────────────────────────────────────────────────
    for table in ("documents", "review_queue"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.current_tenant_id', true))
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true))
            """
        )


def downgrade() -> None:
    op.drop_table("review_queue")
    op.drop_table("documents")

    op.drop_column("products", "currency")
    op.drop_column("products", "enrichment_confidence")
    op.drop_column("products", "enrichment_source")
    op.drop_column("products", "image_path")
    op.drop_column("products", "specifications")
    op.drop_column("products", "description")
