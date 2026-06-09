"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG / Retrieval
Module:   app.rag.retrieval
Purpose:  Dense retrieval using pgvector HNSW index (top-20 candidates).
          Parent-Doc chunk mapping: child chunks retrieved by embedding, then
          swapped for their parent chunk to provide richer context to the LLM.
          Always applies tenant_id filter before any vector search.
          This is step 3 of the RAG runtime pipeline (after RRF merge).
Depends:  app.infra.vector.pgvector, app.infra.db.repos.catalog_repo
HITL:     None.
"""
