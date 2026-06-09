"""
Feature:  AI Agents — Enrichment Specialist
Layer:    Agent / Specialist
Module:   app.agents.specialists.enrichment_agent
Purpose:  Enriches extracted product data: category classification, brand
          resolution, image analysis (GPT-4o Vision), barcode lookup (GS1),
          synonym generation, and embedding trigger. Writes via outbox pattern.
Depends:  langgraph, app.infra.llm, app.core.catalog.services
HITL:     None — enrichment is internal.
"""
