"""
Feature:  NLP Search & RAG Pipeline / AI Agents (cross-cutting)
Layer:    Guardrails
Module:   app.guardrails
Purpose:  Public API for Phase 5 guardrails. Import from here — do not
          reach into the sub-modules directly.
Depends:  app.guardrails.presidio, app.guardrails.nemo_guard
HITL:     None
"""

from app.guardrails.nemo_guard import (
    GuardProtocol,
    NeMoGuard,
    get_default_guard,
)
from app.guardrails.presidio import (
    RedactionResult,
    async_redact,
    redact,
)

__all__ = [
    "GuardProtocol",
    "NeMoGuard",
    "get_default_guard",
    "RedactionResult",
    "async_redact",
    "redact",
]
