"""
Feature:  AI Agents — MCP Servers
Layer:    Agent / MCP
Module:   app.agents.mcp_servers.email_server
Purpose:  MCP server for email composition by agents. Does NOT send directly —
          returns draft payload that Communication Agent wraps in a HITL action.
          Enforces HITL rule: no email leaves the system without importer approval.
Depends:  mcp
HITL:     Indirect — output used in HITL actions, not sent directly.
"""
