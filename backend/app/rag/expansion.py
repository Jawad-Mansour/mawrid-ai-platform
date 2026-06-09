"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG / Query Expansion
Module:   app.rag.expansion
Purpose:  Query expansion step (step 1 of the RAG pipeline).
          HyDE: generates a hypothetical answer document via GPT-4o-mini, embeds
          it, uses that embedding for dense retrieval (step 1a).
          Multi-Query: generates 3 alternative phrasings of the user query via
          GPT-4o-mini; all variants + original searched separately (step 1b).
          Both results merged via Reciprocal Rank Fusion (RRF) before retrieval.
Depends:  app.infra.llm.openai, app.infra.llm.embedder
HITL:     None.
"""
