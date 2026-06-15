"""
Feature:  Database (cross-cutting)
Layer:    Infra / DB
Module:   app.infra.db.coerce
Purpose:  Small value-coercion helpers for the repository layer. asyncpg requires
          native Python types for typed columns — e.g. a DATE column rejects an
          ISO date string with "'str' object has no attribute 'toordinal'".
          to_date() accepts str | date | None and returns date | None so repos
          are robust whether the caller passes a Pydantic-parsed date or a raw
          ISO string from JSON.
Depends:  (stdlib only)
HITL:     None.
"""

from __future__ import annotations

from datetime import date


def to_date(value: str | date | None) -> date | None:
    """Coerce an ISO date string (or date) to a date. None passes through."""
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
