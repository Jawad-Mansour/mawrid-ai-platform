"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG / Diversity
Module:   app.rag.diversity
Purpose:  Maximal Marginal Relevance diversity pass. Applied after cross-encoder
          reranking to reduce redundant chunks before passing context window to
          LLM. Lambda controls relevance/diversity trade-off (λ=0.5).
Depends:  numpy
HITL:     None.
"""
