"""
Feature:  RAG Pipeline / AI Agents (cross-cutting)
Layer:    Infra / LLM
Module:   app.infra.llm.openai
Purpose:  Async OpenAI client wrapper with retry logic, usage tracking, and
          token budget enforcement. All LLM calls for enrichment, RAG, and
          agents go through this module. GPT-4o is the zero-shot fallback in
          the 3-tier intent classifier.
Depends:  openai, tenacity
HITL:     None — infrastructure only.
"""
