"""
Feature:  AI Chatbot (Admin + Consumer)
Layer:    API / Router
Module:   app.api.chat
Purpose:  HTTP routes for the importer-facing admin chatbot (all enriched
          products + operational queries) and the consumer-facing storefront
          chatbot (published products only). Routes through 3-tier intent
          classifier. Guardrails + Presidio active on all LLM calls.
Depends:  app.ml.intent.classifier, app.rag.pipeline, app.agents.supervisor, app.api.deps
HITL:     Any write action initiated by the agent routes through hitl_actions.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["chat"])
