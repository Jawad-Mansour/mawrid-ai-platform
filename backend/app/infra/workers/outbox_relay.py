"""
Feature:  Catalog Enrichment Pipeline
Layer:    Infra / Workers
Module:   app.infra.workers.outbox_relay
Purpose:  Outbox relay process. Drains the outbox table, generates embeddings
          via SentenceTransformer, writes vectors to pgvector. Crash-safe:
          each row is marked processed only after successful pgvector write.
          No duplicates, no missing embeddings even after partial failure.
          Runs as a separate Docker process (not part of the FastAPI app).
Depends:  app.infra.db, app.infra.vector.pgvector, app.infra.llm.embedder
HITL:     None — relay is internal.
"""
