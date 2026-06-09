"""
Feature:  Operations Command Center
Layer:    API / Router
Module:   app.api.admin
Purpose:  HTTP routes for the admin dashboard: business summary stats, AI model
          health (classifier F1, RAGAS scores, drift metrics), enrichment queue
          panel, n8n workflow run status, and agent trace log access.
Depends:  app.infra.db.repos, app.infra.llm, app.api.deps
HITL:     None — dashboard is read-only.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])
