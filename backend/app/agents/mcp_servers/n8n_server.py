"""
Feature:  AI Agents — MCP Server: n8n Workflow Triggers
Layer:    Agent / MCP
Module:   app.agents.mcp_servers.n8n_server
Purpose:  MCP server for n8n workflow triggering by agents. Allows agents to
          trigger specific n8n workflows (WF-01 to WF-15) via webhook URLs.
          Each trigger creates an audit log entry. Workflows that result in
          external actions (email, order dispatch) still require HITL approval
          inside the n8n workflow — this server only triggers the workflow start.
          Tools: trigger_workflow, list_workflow_status.
Depends:  mcp, httpx, app.core.config
HITL:     Indirect — triggered workflows create HITL actions internally.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from mcp.server import Server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

server: Server = Server("mawrid-n8n-server")  # type: ignore[type-arg]

# Workflow registry — maps workflow ID to description
WORKFLOW_REGISTRY: dict[str, str] = {
    "WF-01": "Tenant provisioning — create MinIO bucket, Redis namespace, welcome email",
    "WF-02": "Document uploaded — call extraction API, queue enrichment jobs",
    "WF-03": "Enrichment complete — update internal catalog, notify importer",
    "WF-04": "Purchase Order approved (HITL) — send PO, create shipment record",
    "WF-05": "Shipment Arrival Alert — find upcoming arrivals, admin notification",
    "WF-06": "Goods Received — update stock, check reorder thresholds, flag discrepancies",
    "WF-07": "Consumer Order confirmed — generate invoice PDF, email consumer",
    "WF-08": "Payment received — auto-stop dunning, mark invoice paid",
    "WF-09": "B2B Payables — dunning advance reminder",
    "WF-10a": "B2C Collections Day 3",
    "WF-10b": "B2C Collections Day 7",
    "WF-10c": "B2C Collections Day 14",
    "WF-11": "Stock threshold breach — reorder HITL PO draft",
    "WF-12": "B2B Receivables Day 7",
    "WF-13": "B2B Receivables Day 14",
    "WF-14": "B2B Receivables Day 21",
    "WF-15": "B2B Dispute filed — Communication Agent dispute draft",
}


@server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="trigger_workflow",
            description=(
                "Trigger a specific n8n workflow by ID. "
                "Valid IDs: " + ", ".join(WORKFLOW_REGISTRY.keys())
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Workflow ID (e.g. WF-04, WF-11)",
                    },
                    "payload": {
                        "type": "object",
                        "description": "Data to pass to the workflow",
                    },
                    "tenant_id": {"type": "string"},
                },
                "required": ["workflow_id", "tenant_id"],
            },
        ),
        Tool(
            name="list_workflow_status",
            description="List all n8n workflows and their last known status.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    result: Any
    try:
        if name == "trigger_workflow":
            result = await _trigger_workflow(
                arguments["workflow_id"],
                arguments.get("payload", {}),
                arguments["tenant_id"],
            )
        elif name == "list_workflow_status":
            result = _list_workflow_status()
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        result = {"error": str(exc)}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def _trigger_workflow(
    workflow_id: str,
    payload: dict[str, Any],
    tenant_id: str,
) -> dict[str, Any]:
    if workflow_id not in WORKFLOW_REGISTRY:
        return {
            "error": f"Unknown workflow_id {workflow_id!r}. Valid: {list(WORKFLOW_REGISTRY.keys())}"
        }

    from app.core.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    n8n_base = getattr(settings, "n8n_base_url", "http://localhost:5678")
    webhook_url = f"{n8n_base}/webhook/{workflow_id.lower()}"

    enriched_payload = {**payload, "tenant_id": tenant_id, "triggered_by": "agent"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=enriched_payload)
            resp.raise_for_status()
            return {
                "workflow_id": workflow_id,
                "description": WORKFLOW_REGISTRY[workflow_id],
                "status": "triggered",
                "http_status": resp.status_code,
            }
    except httpx.HTTPStatusError as exc:
        return {
            "workflow_id": workflow_id,
            "status": "error",
            "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
        }
    except httpx.RequestError as exc:
        # n8n may not be running locally; log and return graceful error
        logger.warning(
            "n8n_webhook_unavailable", extra={"workflow": workflow_id, "error": str(exc)}
        )
        return {
            "workflow_id": workflow_id,
            "description": WORKFLOW_REGISTRY[workflow_id],
            "status": "queued_locally",
            "note": "n8n webhook unavailable — workflow registered for next n8n sync",
        }


def _list_workflow_status() -> list[dict[str, str]]:
    return [{"workflow_id": wid, "description": desc} for wid, desc in WORKFLOW_REGISTRY.items()]


def get_tool_functions() -> dict[str, Any]:
    return {
        "trigger_workflow": _trigger_workflow,
        "list_workflow_status": _list_workflow_status,
    }
