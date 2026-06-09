"""
Feature:  AI Agents — Trajectory Snapshots
Layer:    Test / Evals (PR Gate 6)
Module:   tests.evals.test_agent_trajectories
Purpose:  Agent trajectory snapshot tests (Gate 6, PR to master).
          Loads golden trajectories from fixtures/, replays them against
          the current agent graph, and asserts the tool call sequence and
          final node match the snapshot. Fails CI if agent behavior regresses.
Depends:  langgraph, app.agents, snapshot fixtures in tests/evals/fixtures/
HITL:     None
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_snapshot(name: str) -> dict:
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        pytest.skip(f"Snapshot fixture {name}.json not yet created")
    with open(path) as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_enrichment_agent_trajectory() -> None:
    """Enrichment agent must follow the golden tool call sequence."""
    snapshot = load_snapshot("enrichment_agent_golden")
    from app.agents.specialists.enrichment_agent import run_enrichment_agent

    result = await run_enrichment_agent(
        tenant_id="tenant_eval",
        input_text=snapshot["input"],
    )
    assert result["final_node"] == snapshot["expected_final_node"]
    assert result["tool_calls"] == snapshot["expected_tool_calls"]


@pytest.mark.asyncio
async def test_communication_agent_drafts_only() -> None:
    """Communication agent must never send — only produce a HITL draft."""
    snapshot = load_snapshot("communication_agent_golden")
    from app.agents.specialists.communication_agent import run_communication_agent

    result = await run_communication_agent(
        tenant_id="tenant_eval",
        input_text=snapshot["input"],
    )
    assert result["hitl_action_created"] is True
    assert result["email_sent"] is False
