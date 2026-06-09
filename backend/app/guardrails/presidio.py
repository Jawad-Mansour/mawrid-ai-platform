"""
Feature:  NLP Search & RAG Pipeline / AI Agents (cross-cutting)
Layer:    Guardrails / PII
Module:   app.guardrails.presidio
Purpose:  PII redaction using Microsoft Presidio. Strips PII from LLM inputs
          and outputs across all features (RAG queries, dunning drafts, agent
          responses). Supports EN / AR / FR. Called before every LLM call and
          before returning any LLM output to the client.
          Scope-enforcement check: storefront chatbot must not reveal
          cost / margin / supplier data.
Depends:  presidio-analyzer, presidio-anonymizer
HITL:     None — guardrails are automated.
"""
