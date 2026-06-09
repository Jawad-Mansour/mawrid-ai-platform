"""
Feature:  Catalog Enrichment Pipeline (Outbox Pattern)
Layer:    Infra / DB Models
Module:   app.infra.db.models.outbox
Purpose:  SQLAlchemy ORM model for the `outbox` table. Stores embedding
          generation events written atomically with the product record.
          The outbox relay drains this table: generates embedding →
          writes to pgvector → marks row processed. Crash-safe: each row
          is marked processed only after successful pgvector write.
          No dual-write — DB commit + queue publish is forbidden.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — infrastructure only.
"""
