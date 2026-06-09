"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG / Graph
Module:   app.rag.graph
Purpose:  GraphRAG entity relationship retrieval. Maintains a tenant-scoped
          entity graph (products, suppliers, categories, brands). Adds
          relationship-traversal context to the candidate pool before reranking.
          This is step 5 of the RAG runtime pipeline.
Depends:  networkx (or neo4j optional), app.infra.db.repos.catalog_repo
HITL:     None.
"""
