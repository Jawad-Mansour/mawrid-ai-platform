"""
Feature:  AI Agents — MCP Server: Database
Layer:    Agent / MCP
Module:   app.agents.mcp_servers.db_server
Purpose:  MCP server providing read-only DB query tools to agents.
          Tools: search_products, get_order_status, check_stock,
                 get_shipment_status, list_overdue_invoices.
          All queries are tenant-scoped — agents only see their tenant's data.
          No write tools exposed — agents write via HITL only.
          Runs as an MCP Server (stdio transport) for protocol compliance;
          also exposes get_tool_functions() for direct agent use.
Depends:  mcp, app.infra.db.repos, sqlalchemy
HITL:     None — read-only.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

server: Server = Server("mawrid-db-server")  # type: ignore[type-arg]


@server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_products",
            description="Search the internal product catalog by name or description.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query", "tenant_id"],
            },
        ),
        Tool(
            name="get_order_status",
            description="Get the status of a purchase order by order_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "tenant_id": {"type": "string"},
                },
                "required": ["order_id", "tenant_id"],
            },
        ),
        Tool(
            name="check_stock",
            description="Check current stock level for a product by name or product_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_query": {"type": "string"},
                    "tenant_id": {"type": "string"},
                },
                "required": ["product_query", "tenant_id"],
            },
        ),
        Tool(
            name="get_shipment_status",
            description="Get shipment status by order_id or shipment_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {"type": "string"},
                    "tenant_id": {"type": "string"},
                },
                "required": ["reference", "tenant_id"],
            },
        ),
        Tool(
            name="list_overdue_invoices",
            description="List all overdue invoices for the tenant.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tenant_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["tenant_id"],
            },
        ),
    ]


@server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    tenant_id = arguments.get("tenant_id", "")

    result: Any
    try:
        if name == "search_products":
            result = await _search_products(arguments["query"], tenant_id, arguments.get("limit", 10))
        elif name == "get_order_status":
            result = await _get_order_status(arguments["order_id"], tenant_id)
        elif name == "check_stock":
            result = await _check_stock(arguments["product_query"], tenant_id)
        elif name == "get_shipment_status":
            result = await _get_shipment_status(arguments["reference"], tenant_id)
        elif name == "list_overdue_invoices":
            result = await _list_overdue_invoices(tenant_id, arguments.get("limit", 20))
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        result = {"error": str(exc)}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def _get_session(tenant_id: str) -> Any:
    from app.core.config import get_settings  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: PLC0415

    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return session_factory, engine


async def _search_products(query: str, tenant_id: str, limit: int) -> list[dict[str, Any]]:
    session_factory, engine = await _get_session(tenant_id)
    try:
        from app.infra.db.repos.product_repo import ProductRepository  # noqa: PLC0415
        async with session_factory() as session:
            repo = ProductRepository(session, tenant_id)
            products = await repo.list_all()
            q = query.lower()
            matches = [
                {
                    "product_id": p.product_id,
                    "name": p.product_name,
                    "qty_in_stock": p.qty_in_stock,
                    "enrichment_status": p.enrichment_status,
                    "storefront_status": getattr(p, "storefront_status", None),
                }
                for p in products
                if q in (p.product_name or "").lower()
            ][:limit]
        return matches
    finally:
        await engine.dispose()


async def _get_order_status(order_id: str, tenant_id: str) -> dict[str, Any]:
    session_factory, engine = await _get_session(tenant_id)
    try:
        from app.infra.db.repos.order_repo import OrderRepository  # noqa: PLC0415
        async with session_factory() as session:
            repo = OrderRepository(session, tenant_id)
            order = await repo.get_by_id(order_id)
            if order is None:
                return {"error": f"Order {order_id!r} not found"}
            return {
                "order_id": order.order_id,
                "status": order.status,
                "supplier_id": order.supplier_id,
            }
    finally:
        await engine.dispose()


async def _check_stock(product_query: str, tenant_id: str) -> list[dict[str, Any]]:
    return await _search_products(product_query, tenant_id, 5)


async def _get_shipment_status(reference: str, tenant_id: str) -> dict[str, Any]:
    session_factory, engine = await _get_session(tenant_id)
    try:
        from app.infra.db.repos.shipment_repo import ShipmentRepository  # noqa: PLC0415
        async with session_factory() as session:
            repo = ShipmentRepository(session, tenant_id)
            shipments = await repo.list_by_po(reference)
            if not shipments:
                return {"error": f"No shipment found for reference {reference!r}"}
            shipment = shipments[0]
            return {
                "shipment_id": shipment.shipment_id,
                "status": shipment.status,
                "carrier": shipment.carrier,
                "eta": str(shipment.expected_arrival_date) if shipment.expected_arrival_date else None,
            }
    finally:
        await engine.dispose()


async def _list_overdue_invoices(tenant_id: str, limit: int) -> list[dict[str, Any]]:
    session_factory, engine = await _get_session(tenant_id)
    try:
        from datetime import date  # noqa: PLC0415

        from app.infra.db.repos.invoice_repo import InvoiceRepository  # noqa: PLC0415
        async with session_factory() as session:
            repo = InvoiceRepository(session, tenant_id)
            invoices = await repo.list_overdue_b2b_receivables(date.today())
            return [
                {
                    "invoice_id": inv.invoice_id,
                    "amount": float(inv.amount_due),
                    "due_date": str(inv.due_date),
                    "status": inv.status,
                }
                for inv in invoices[:limit]
            ]
    finally:
        await engine.dispose()


def get_tool_functions() -> dict[str, Any]:
    """Return tool functions for direct agent use (bypassing MCP protocol)."""
    return {
        "search_products": _search_products,
        "get_order_status": _get_order_status,
        "check_stock": _check_stock,
        "get_shipment_status": _get_shipment_status,
        "list_overdue_invoices": _list_overdue_invoices,
    }
