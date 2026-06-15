"""
Feature:  API Layer (cross-cutting)
Layer:    API / Schemas
Module:   app.api.schemas
Purpose:  Shared Pydantic v2 base for all request/response DTOs. StrictModel sets
          extra="forbid" so unknown fields in request bodies are rejected (422)
          rather than silently ignored — per the project coding standard.
Depends:  pydantic
HITL:     None.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
