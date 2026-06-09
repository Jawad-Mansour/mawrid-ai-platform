"""
Feature:  NLP Search & RAG Pipeline
Layer:    API / Router
Module:   app.api.search
Purpose:  HTTP routes for internal catalog search (enriched scope) and
          storefront search (published scope). Both use the full 6-technique
          RAG pipeline. Scope enforced at dense retrieval step.
Depends:  app.rag.pipeline, app.api.deps
HITL:     None — search is read-only.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/search", tags=["search"])
