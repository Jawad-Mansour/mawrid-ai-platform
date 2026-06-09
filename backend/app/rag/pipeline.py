"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG
Module:   app.rag.pipeline
Purpose:  Orchestrates the full 6-technique RAG pipeline in runtime execution
          order: (1) HyDE + Multi-Query expansion, (2) RRF fusion, (3) Dense
          retrieval (pgvector HNSW + tenant filter), (4) Parent-Doc expansion
          (1024-token parents, 256-token child chunks), (5) GraphRAG (entity
          relationships), (6) Cross-Encoder reranking → MMR diversity →
          LLM response → NeMo output guardrail. Scope enforced via filter at
          step 3 (enriched vs published).
Depends:  app.rag.hyde, app.rag.multi_query, app.rag.reranking, app.rag.graph_rag,
          app.infra.llm, app.infra.db.repos.catalog_repo
HITL:     None — RAG is read-only.
"""
