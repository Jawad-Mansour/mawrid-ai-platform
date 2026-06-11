"""rag — product_chunks (parent/child), graph_edges tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-11

Adds:
  - product_chunks: chunk_id, product_id, tenant_id, chunk_type, parent_chunk_id,
    chunk_index, chunk_text, embedding Vector(1536), HNSW index, created_at, RLS
  - graph_edges: edge_id, tenant_id, source_id, source_type, target_id,
    target_type, relation, weight, created_at, RLS
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # product_chunks
    op.create_table(
        "product_chunks",
        sa.Column("chunk_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("product_id", sa.Text, nullable=False),
        sa.Column("chunk_type", sa.Text, nullable=False),  # parent | child
        sa.Column("parent_chunk_id", sa.Text, nullable=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_chunk_product_id", "product_chunks", ["product_id"])
    op.create_index("ix_chunk_tenant_id", "product_chunks", ["tenant_id"])
    op.execute(
        """
        CREATE INDEX ix_chunk_embedding_hnsw
        ON product_chunks USING hnsw (embedding vector_l2_ops)
        WITH (m = 16, ef_construction = 64);
        """
    )
    op.execute("ALTER TABLE product_chunks ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation_product_chunks
        ON product_chunks
        USING (tenant_id = current_setting('app.tenant_id', true));
        """
    )

    # graph_edges
    op.create_table(
        "graph_edges",
        sa.Column("edge_id", sa.Text, primary_key=True),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("target_id", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text, nullable=False),
        sa.Column("relation", sa.Text, nullable=False),
        sa.Column("weight", sa.Numeric(6, 4), server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_graph_edge_tenant_id", "graph_edges", ["tenant_id"])
    op.create_index("ix_graph_source_id", "graph_edges", ["source_id"])
    op.execute("ALTER TABLE graph_edges ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation_graph_edges
        ON graph_edges
        USING (tenant_id = current_setting('app.tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_graph_edges ON graph_edges;")
    op.drop_table("graph_edges")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_product_chunks ON product_chunks;")
    op.execute("DROP INDEX IF EXISTS ix_chunk_embedding_hnsw;")
    op.drop_table("product_chunks")
