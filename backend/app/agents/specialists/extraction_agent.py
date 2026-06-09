"""
Feature:  AI Agents — Extraction Specialist
Layer:    Agent / Specialist
Module:   app.agents.specialists.extraction_agent
Purpose:  Extracts structured product data (name, SKU, price, specs) from
          raw supplier documents (PDF/Excel/image). Output feeds enrichment
          pipeline. Delegates to LLM with structured output (Pydantic v2 model).
Depends:  langgraph, app.infra.llm.openai_client, app.core.catalog.models
HITL:     None — extraction is internal.
"""
