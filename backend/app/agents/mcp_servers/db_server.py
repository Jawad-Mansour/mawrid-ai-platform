"""
Feature:  AI Agents — MCP Servers
Layer:    Agent / MCP
Module:   app.agents.mcp_servers.db_server
Purpose:  MCP server for read-only database access by agents. Provides
          structured query tools (not raw SQL) for product, invoice, supplier,
          and customer data. Tenant isolation enforced — agents only see
          their own tenant's data.
Depends:  mcp, app.infra.db.repos
HITL:     None — read-only.
"""
