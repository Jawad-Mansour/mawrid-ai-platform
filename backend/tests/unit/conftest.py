"""
Feature:  All features — Unit Test Infrastructure
Layer:    Test / Unit
Module:   tests.unit.conftest
Purpose:  Shared fixtures for all unit tests. Provides fake implementations
          of all Protocol-typed external dependencies so unit tests never
          touch real DB, Redis, LLM, or external services.
Depends:  pytest, app.core protocols
HITL:     None
"""

from __future__ import annotations

from typing import Any

import pytest


class FakeLLM:
    """Protocol-compatible LLM stub. Returns deterministic responses."""

    def __init__(self, response: str = "enriched product description"):
        self._response = response

    async def ainvoke(self, prompt: str, **kwargs: Any) -> str:
        return self._response

    async def astream(self, prompt: str, **kwargs: Any):
        yield self._response


class FakePaymentGateway:
    """Protocol-compatible payment gateway stub. Always succeeds."""

    async def charge(self, amount: float, currency: str, source: str) -> dict[str, Any]:
        return {"status": "succeeded", "transaction_id": "fake_txn_001"}

    async def refund(self, transaction_id: str) -> dict[str, Any]:
        return {"status": "refunded", "transaction_id": transaction_id}


class FakeEmailSender:
    """Protocol-compatible email sender stub. Captures sent emails."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, to: str, subject: str, body: str, **kwargs: Any) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body, **kwargs})


class FakeObjectStorage:
    """Protocol-compatible MinIO stub. In-memory key-value store."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        self._store[key] = data

    async def get(self, key: str) -> bytes:
        return self._store[key]

    def exists(self, key: str) -> bool:
        return key in self._store


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_payment_gateway() -> FakePaymentGateway:
    return FakePaymentGateway()


@pytest.fixture
def fake_email_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def fake_object_storage() -> FakeObjectStorage:
    return FakeObjectStorage()
