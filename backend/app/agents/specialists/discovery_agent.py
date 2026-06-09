"""
Feature:  AI Agents — Discovery Specialist (Stretch Feature)
Layer:    Agent / Specialist
Module:   app.agents.specialists.discovery_agent
Purpose:  Proactive supplier discovery: web search for new suppliers matching
          product category, scrapes public product databases, scores candidates
          via supplier scorer, and creates supplier_outreach HITL action for
          importer review. Marked as stretch — may be deferred to Phase 14.
Depends:  langgraph, app.core.suppliers.services, app.core.hitl.services,
          app.infra.llm.openai_client
HITL:     supplier_outreach
"""
