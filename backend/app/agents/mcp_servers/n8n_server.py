"""
Feature:  AI Agents — MCP Servers
Layer:    Agent / MCP
Module:   app.agents.mcp_servers.n8n_server
Purpose:  MCP server for n8n workflow triggering by agents. Agents can trigger
          specific n8n workflows (WF-01 to WF-15) by ID. Each trigger creates
          an audit log entry. Workflows that result in external actions must
          still go through HITL.
Depends:  mcp, httpx
HITL:     Indirect — some triggered workflows create HITL actions.
"""
