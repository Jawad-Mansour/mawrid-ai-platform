"""
Feature:  AI Agents — MCP Servers
Layer:    Agent / MCP
Module:   app.agents.mcp_servers.filesystem_server
Purpose:  MCP server for filesystem access by agents. Scoped to MinIO bucket
          paths only — agents cannot access host filesystem. Provides read/list
          tools for supplier documents.
Depends:  mcp, app.infra.storage.minio
HITL:     None — read-only filesystem access.
"""
