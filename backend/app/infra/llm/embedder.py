"""
Feature:  Catalog Enrichment Pipeline / RAG Pipeline
Layer:    Infra / LLM
Module:   app.infra.llm.embedder
Purpose:  Async embedding client using text-embedding-3-small (1536 dims).
          Used by enrichment pipeline (outbox event) and RAG pipeline (query
          embedding for HyDE + dense retrieval). Batching handled internally.
Depends:  openai, app.infra.llm.openai_client
HITL:     None.
"""
