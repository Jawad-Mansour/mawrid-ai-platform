"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG / Graph
Module:   app.rag.graph
Purpose:  GraphRAG entity relationship retrieval. Loads the tenant's knowledge
          graph (product→supplier, product→category edges) from graph_edges table
          into networkx. Extracts entity IDs from the candidate pool, traverses
          2 hops, and fetches product chunks for related entities not yet in the
          candidate pool. Adds relationship context before cross-encoder reranking.
          Step 5 of the RAG runtime pipeline.
Depends:  networkx, sqlalchemy, app.rag.retrieval
HITL:     None.
"""

from __future__ import annotations

import networkx as nx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.retrieval import ChunkResult


async def load_graph(session: AsyncSession, tenant_id: str) -> nx.DiGraph:
    """Load all graph edges for the tenant into a networkx DiGraph."""
    sql = text(
        """
        SELECT source_id, source_type, target_id, target_type, relation, weight
        FROM graph_edges
        WHERE tenant_id = :tenant_id
        """
    )
    result = await session.execute(sql, {"tenant_id": tenant_id})
    rows = result.fetchall()

    graph: nx.DiGraph = nx.DiGraph()
    for row in rows:
        graph.add_edge(
            row.source_id,
            row.target_id,
            relation=row.relation,
            weight=float(row.weight),
            source_type=row.source_type,
            target_type=row.target_type,
        )
    return graph


async def graph_expand(
    session: AsyncSession,
    tenant_id: str,
    candidates: list[ChunkResult],
    graph: nx.DiGraph | None = None,
    max_hops: int = 2,
    top_neighbors: int = 5,
) -> list[ChunkResult]:
    """
    Traverse the knowledge graph from candidate product IDs to find related
    products. Fetch their parent chunks and add to candidate pool.
    If graph is None, loads it from DB. Passes through unchanged if graph is empty.
    """
    if graph is None:
        graph = await load_graph(session, tenant_id)

    if graph.number_of_nodes() == 0:
        return candidates

    # Collect product IDs already in candidate pool
    existing_product_ids = {c.product_id for c in candidates}
    seed_ids = list(existing_product_ids)

    # BFS up to max_hops from each seed product
    neighbor_ids: set[str] = set()
    for seed in seed_ids:
        if seed not in graph:
            continue
        # Get nodes within max_hops
        reachable = nx.single_source_shortest_path_length(graph, seed, cutoff=max_hops)
        neighbor_ids.update(nid for nid in reachable if nid not in existing_product_ids)

    if not neighbor_ids:
        return candidates

    # Fetch parent chunks for neighbor product IDs
    neighbor_list = list(neighbor_ids)[:top_neighbors]
    sql = text(
        """
        SELECT chunk_id, product_id, chunk_type, parent_chunk_id, chunk_text
        FROM product_chunks
        WHERE tenant_id = :tenant_id
          AND product_id = ANY(:ids)
          AND chunk_type = 'parent'
        LIMIT :lim
        """
    )
    result = await session.execute(
        sql,
        {"tenant_id": tenant_id, "ids": neighbor_list, "lim": top_neighbors},
    )
    rows = result.fetchall()

    graph_chunks = [
        ChunkResult(
            chunk_id=row.chunk_id,
            product_id=row.product_id,
            chunk_type=row.chunk_type,
            parent_chunk_id=row.parent_chunk_id,
            chunk_text=row.chunk_text,
            rrf_score=0.1,  # lower weight than direct retrieval hits
        )
        for row in rows
        if row.chunk_id not in {c.chunk_id for c in candidates}
    ]

    return candidates + graph_chunks
