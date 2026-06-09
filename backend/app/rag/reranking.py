"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG / Reranking
Module:   app.rag.reranking
Purpose:  Cross-Encoder reranking using ms-marco-MiniLM-L-6-v2 (loaded at
          startup from disk, not downloaded at runtime). Takes top-k candidates
          from dense + parent-doc + GraphRAG, scores each (query, chunk) pair,
          then MMR diversity pass before returning final context to LLM.
Depends:  sentence-transformers, app.rag.mmr
HITL:     None.
"""
