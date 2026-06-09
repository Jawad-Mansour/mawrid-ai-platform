"""
Feature:  NLP Search & RAG Pipeline (GraphRAG)
Layer:    Infra / DB Models
Module:   app.infra.db.models.graph
Purpose:  SQLAlchemy ORM model for `graph_edges` table. Stores the knowledge
          graph edges used by the GraphRAG pipeline: product→supplier,
          product→category, supplier→category relationships. Edge weights
          reflect co-occurrence frequency. Tenant-scoped. Loaded into networkx
          at query time for graph traversal during RAG retrieval.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None.
"""
