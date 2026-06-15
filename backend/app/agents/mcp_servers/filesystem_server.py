"""
Feature:  AI Agents — MCP Server: Filesystem (MinIO)
Layer:    Agent / MCP
Module:   app.agents.mcp_servers.filesystem_server
Purpose:  MCP server for MinIO storage access by agents. Scoped to the
          tenant's bucket — agents cannot access other tenants' files or
          the host filesystem. Tools: list_documents, get_document_presigned_url.
          Read-only. Write operations go through the catalog API, not directly
          through this MCP server.
Depends:  mcp, app.infra.storage.minio
HITL:     None — read-only access.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

server: Server = Server("mawrid-filesystem-server")  # type: ignore[type-arg]


@server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_documents",
            description="List uploaded supplier documents for the tenant (MinIO catalog bucket).",
            inputSchema={
                "type": "object",
                "properties": {
                    "tenant_id": {"type": "string"},
                    "prefix": {
                        "type": "string",
                        "default": "docs/",
                        "description": "MinIO path prefix",
                    },
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["tenant_id"],
            },
        ),
        Tool(
            name="get_document_presigned_url",
            description="Get a presigned URL to access a specific document in MinIO.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tenant_id": {"type": "string"},
                    "object_path": {
                        "type": "string",
                        "description": "MinIO object path within tenant bucket",
                    },
                    "expires_in_seconds": {"type": "integer", "default": 900},
                },
                "required": ["tenant_id", "object_path"],
            },
        ),
    ]


@server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    result: Any
    try:
        if name == "list_documents":
            result = await _list_documents(
                arguments["tenant_id"],
                arguments.get("prefix", "docs/"),
                arguments.get("limit", 20),
            )
        elif name == "get_document_presigned_url":
            result = await _get_presigned_url(
                arguments["tenant_id"],
                arguments["object_path"],
                arguments.get("expires_in_seconds", 900),
            )
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        result = {"error": str(exc)}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def _list_documents(tenant_id: str, prefix: str, limit: int) -> list[dict[str, Any]]:
    try:
        import asyncio  # noqa: PLC0415

        from app.infra.storage.minio import _get_client  # noqa: PLC0415

        client = await asyncio.to_thread(_get_client)
        bucket = f"tenant-{tenant_id}"
        objects_iter = client.list_objects(bucket, prefix=prefix, recursive=True)
        results: list[dict[str, Any]] = []
        for i, obj in enumerate(objects_iter):
            if i >= limit:
                break
            results.append(
                {
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": str(obj.last_modified),
                }
            )
        return results
    except Exception as exc:
        logger.warning("filesystem_list_failed", extra={"error": str(exc)})
        return [{"error": str(exc)}]


async def _get_presigned_url(tenant_id: str, object_path: str, expires: int) -> dict[str, Any]:
    try:
        from app.infra.storage.minio import get_presigned_url  # noqa: PLC0415

        clean_path = object_path.lstrip("/")
        url = await get_presigned_url(tenant_id, clean_path, expires_seconds=expires)
        return {"url": url, "expires_in": expires, "tenant_id": tenant_id}
    except Exception as exc:
        logger.warning("filesystem_presign_failed", extra={"error": str(exc)})
        return {"error": str(exc)}


def get_tool_functions() -> dict[str, Any]:
    return {
        "list_documents": _list_documents,
        "get_document_presigned_url": _get_presigned_url,
    }
