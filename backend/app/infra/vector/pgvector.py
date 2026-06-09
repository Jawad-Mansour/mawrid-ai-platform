"""
Feature:  Catalog Enrichment / RAG Pipeline (cross-cutting)
Layer:    Infra / Vector
Module:   app.infra.vector.pgvector
Purpose:  pgvector search client using HNSW index. ALL searches include a
          tenant_id filter — this is the third tenant isolation layer.
          Admin chatbot scope: WHERE enrichment_status='enriched' AND tenant_id=?
          Consumer chatbot scope: WHERE storefront_status='published' AND tenant_id=?
          Returns top-K candidates for cross-encoder reranking.
Depends:  sqlalchemy, pgvector
HITL:     None — infrastructure only.
"""
