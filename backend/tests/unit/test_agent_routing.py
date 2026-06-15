"""
Feature:  AI Agents — Supervisor + Checkpointer
Layer:    Tests / Unit
Module:   tests.unit.test_agent_routing
Purpose:  Unit tests for agent routing primitives without a real LLM or DB.
          Covers: make_thread_id, validate_thread_id, get_tenant_from_thread,
          supervisor step-count guard, bulk guard, AgentState structure,
          and supervisor node routing with mocked LLM.
Depends:  app.agents.checkpointer, app.agents.supervisor
HITL:     None — routing/state tests only.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage


class TestThreadIdUtils:
    """Pure functions — no network, no DB."""

    def test_make_thread_id_format(self) -> None:
        from app.agents.checkpointer import make_thread_id

        tid = make_thread_id("tenant-abc", "user-123", "a1b2c3d4-0000-0000-0000-000000000001")
        assert tid == "tenant-abc:user-123:a1b2c3d4-0000-0000-0000-000000000001"

    def test_validate_valid_thread_id(self) -> None:
        from app.agents.checkpointer import validate_thread_id

        tid = "tenant1:user1:a1b2c3d4-0000-0000-0000-000000000001"
        assert validate_thread_id(tid) is True

    def test_validate_invalid_thread_id_missing_uuid(self) -> None:
        from app.agents.checkpointer import validate_thread_id

        assert validate_thread_id("tenant1:user1") is False

    def test_validate_invalid_thread_id_empty(self) -> None:
        from app.agents.checkpointer import validate_thread_id

        assert validate_thread_id("") is False

    def test_get_tenant_from_thread(self) -> None:
        from app.agents.checkpointer import get_tenant_from_thread

        tid = "acme-corp:user-007:a1b2c3d4-0000-0000-0000-000000000001"
        assert get_tenant_from_thread(tid) == "acme-corp"

    def test_get_tenant_raises_on_invalid(self) -> None:
        from app.agents.checkpointer import get_tenant_from_thread

        with pytest.raises(ValueError, match="Invalid thread_id"):
            get_tenant_from_thread("only-one-part")

    def test_make_and_validate_roundtrip(self) -> None:
        from app.agents.checkpointer import make_thread_id, validate_thread_id

        tid = make_thread_id("tenant-xyz", "user-001", "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert validate_thread_id(tid) is True

    def test_tenant_isolation_different_tenants(self) -> None:
        from app.agents.checkpointer import get_tenant_from_thread, make_thread_id

        session_uuid = "a1b2c3d4-0000-0000-0000-000000000001"
        tid1 = make_thread_id("tenant-a", "user-1", session_uuid)
        tid2 = make_thread_id("tenant-b", "user-1", session_uuid)
        assert get_tenant_from_thread(tid1) == "tenant-a"
        assert get_tenant_from_thread(tid2) == "tenant-b"
        assert tid1 != tid2


class TestAgentState:
    """Verify AgentState TypedDict structure is constructible."""

    def test_agent_state_full_construction(self) -> None:
        from app.agents.supervisor import AgentState

        state = AgentState(
            messages=[HumanMessage(content="Find a supplier")],
            tenant_id="t1",
            user_id="u1",
            thread_id="t1:u1:a1b2c3d4-0000-0000-0000-000000000001",
            task_description="Find a supplier for electronics",
            intent="complex_task",
            active_specialist=None,
            specialist_result=None,
            hitl_action_ids=[],
            bulk_pending=False,
            estimated_product_count=0,
            step_count=0,
            finished=False,
            error=None,
        )
        assert state["tenant_id"] == "t1"
        assert state["intent"] == "complex_task"
        assert state["finished"] is False
        assert state["hitl_action_ids"] == []

    def test_agent_state_with_hitl_ids(self) -> None:
        from app.agents.supervisor import AgentState

        state = AgentState(
            messages=[],
            tenant_id="t1",
            user_id="u1",
            thread_id="t1:u1:a1b2c3d4-0000-0000-0000-000000000001",
            task_description="Send dunning email",
            intent="complex_task",
            active_specialist="communication_specialist",
            specialist_result="Draft created.",
            hitl_action_ids=["hitl-001", "hitl-002"],
            bulk_pending=False,
            estimated_product_count=0,
            step_count=2,
            finished=False,
            error=None,
        )
        assert state["active_specialist"] == "communication_specialist"
        assert len(state["hitl_action_ids"]) == 2


class TestSupervisorNode:
    """Test supervisor_node() logic with mocked LLM — no real OpenAI calls."""

    def _base_state(self, **kwargs: Any) -> dict[str, Any]:
        from langchain_core.messages import HumanMessage

        base: dict[str, Any] = {
            "messages": [HumanMessage(content="Find a new appliance supplier")],
            "tenant_id": "t1",
            "user_id": "u1",
            "thread_id": "t1:u1:a1b2c3d4-0000-0000-0000-000000000001",
            "task_description": "Find a new appliance supplier",
            "intent": "complex_task",
            "active_specialist": None,
            "specialist_result": None,
            "hitl_action_ids": [],
            "bulk_pending": False,
            "estimated_product_count": 0,
            "step_count": 0,
            "finished": False,
            "error": None,
        }
        base.update(kwargs)
        return base

    @pytest.mark.asyncio
    async def test_step_count_guard_stops_at_10(self) -> None:
        from app.agents.supervisor import supervisor_node
        from langgraph.graph import END

        state = self._base_state(step_count=10, specialist_result="Done already.")
        cmd = await supervisor_node(state)  # type: ignore[arg-type]
        assert cmd.goto == END

    @pytest.mark.asyncio
    async def test_finished_flag_stops_immediately(self) -> None:
        from app.agents.supervisor import supervisor_node
        from langgraph.graph import END

        state = self._base_state(step_count=2, finished=True, specialist_result="All good.")
        cmd = await supervisor_node(state)  # type: ignore[arg-type]
        assert cmd.goto == END

    @pytest.mark.asyncio
    async def test_bulk_guard_pauses_on_pending(self) -> None:
        from app.agents.supervisor import supervisor_node
        from langgraph.graph import END

        state = self._base_state(bulk_pending=True, estimated_product_count=25)
        cmd = await supervisor_node(state)  # type: ignore[arg-type]
        assert cmd.goto == END
        # Response message should mention the count
        msgs = (cmd.update or {}).get("messages", [])
        assert any("25" in str(m.content) for m in msgs)

    @pytest.mark.asyncio
    async def test_llm_routes_to_discovery_specialist(self) -> None:
        from app.agents.supervisor import supervisor_node

        state = self._base_state()

        with patch(
            "app.infra.llm.openai.chat_completion",
            new_callable=AsyncMock,
            return_value="discovery_specialist",
        ):
            cmd = await supervisor_node(state)  # type: ignore[arg-type]

        assert cmd.goto == "discovery_specialist"
        assert (cmd.update or {}).get("active_specialist") == "discovery_specialist"

    @pytest.mark.asyncio
    async def test_llm_done_routes_to_end(self) -> None:
        from app.agents.supervisor import supervisor_node
        from langgraph.graph import END

        state = self._base_state(specialist_result="Suppliers found and HITL created.")

        with patch(
            "app.infra.llm.openai.chat_completion", new_callable=AsyncMock, return_value="done"
        ):
            cmd = await supervisor_node(state)  # type: ignore[arg-type]

        assert cmd.goto == END
        assert (cmd.update or {}).get("finished") is True

    @pytest.mark.asyncio
    async def test_llm_failure_graceful_end(self) -> None:
        """If LLM throws, supervisor ends gracefully instead of crashing."""
        from app.agents.supervisor import supervisor_node
        from langgraph.graph import END

        state = self._base_state()

        with patch(
            "app.infra.llm.openai.chat_completion",
            new_callable=AsyncMock,
            side_effect=RuntimeError("OpenAI unavailable"),
        ):
            cmd = await supervisor_node(state)  # type: ignore[arg-type]

        assert cmd.goto == END

    @pytest.mark.asyncio
    async def test_llm_unknown_decision_graceful_end(self) -> None:
        from app.agents.supervisor import supervisor_node
        from langgraph.graph import END

        state = self._base_state()

        with patch(
            "app.infra.llm.openai.chat_completion",
            new_callable=AsyncMock,
            return_value="do_magic_things",
        ):
            cmd = await supervisor_node(state)  # type: ignore[arg-type]

        assert cmd.goto == END

    @pytest.mark.parametrize(
        "specialist",
        [
            "extraction_specialist",
            "enrichment_specialist",
            "communication_specialist",
            "stock_monitor_specialist",
            "discovery_specialist",
        ],
    )
    @pytest.mark.asyncio
    async def test_all_specialists_routable(self, specialist: str) -> None:
        from app.agents.supervisor import supervisor_node

        state = self._base_state()

        with patch(
            "app.infra.llm.openai.chat_completion", new_callable=AsyncMock, return_value=specialist
        ):
            cmd = await supervisor_node(state)  # type: ignore[arg-type]

        assert cmd.goto == specialist


class TestAllSpecialists:
    """Verify ALL_SPECIALISTS list is consistent with code."""

    def test_all_specialists_list(self) -> None:
        from app.agents.supervisor import ALL_SPECIALISTS

        expected = {
            "extraction_specialist",
            "enrichment_specialist",
            "communication_specialist",
            "stock_monitor_specialist",
            "discovery_specialist",
        }
        assert set(ALL_SPECIALISTS) == expected

    def test_bulk_guard_threshold(self) -> None:
        from app.agents.supervisor import BULK_GUARD_THRESHOLD

        assert BULK_GUARD_THRESHOLD == 10
