"""
Feature:  AI Agents — Supervisor Agent
Layer:    Agent
Module:   app.agents.supervisor
Purpose:  LangGraph Supervisor agent. Routes tasks to specialist subagents
          (Extraction, Enrichment, Communication, StockMonitor, Discovery).
          Bulk guard: if task involves >10 products, Supervisor pauses and
          asks importer for confirmation before proceeding.
          Checkpoints via AsyncRedisSaver; thread_id = {tenant_id}:{user_id}:{session_uuid}.
          Satisfies 4 MCP server connections (filesystem, DB, email, n8n).
Depends:  langgraph, app.agents.specialists, app.infra.llm
HITL:     Any external write action from a specialist routes to hitl_actions.
"""
