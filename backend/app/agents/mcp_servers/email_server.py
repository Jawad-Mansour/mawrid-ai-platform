"""
Feature:  AI Agents — MCP Server: Email Drafting
Layer:    Agent / MCP
Module:   app.agents.mcp_servers.email_server
Purpose:  MCP server for email composition by agents. Returns draft payloads
          only — does NOT send directly. Communication Agent wraps the output
          in a HITL action. Enforces the HITL rule: no email leaves the system
          without importer approval. Tools: draft_email, draft_purchase_order,
          draft_dunning_message.
Depends:  mcp, app.infra.llm.openai
HITL:     Indirect — output used to create HITL actions, never sent directly.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

server: Server = Server("mawrid-email-server")  # type: ignore[type-arg]


@server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="draft_email",
            description=(
                "Draft a professional email. Returns the draft text. "
                "NEVER sends — caller must create a HITL action."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "purpose": {"type": "string", "description": "Brief description of email purpose"},
                    "recipient_name": {"type": "string"},
                    "language": {"type": "string", "default": "en"},
                    "tone": {"type": "string", "enum": ["gentle", "neutral", "firm"], "default": "neutral"},
                    "context": {"type": "string", "description": "Background information for the draft"},
                },
                "required": ["purpose", "context"],
            },
        ),
        Tool(
            name="draft_purchase_order",
            description="Draft a purchase order email for a supplier. Returns draft text.",
            inputSchema={
                "type": "object",
                "properties": {
                    "supplier_name": {"type": "string"},
                    "supplier_email": {"type": "string"},
                    "product_name": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "language": {"type": "string", "default": "en"},
                },
                "required": ["supplier_name", "product_name", "quantity"],
            },
        ),
        Tool(
            name="draft_dunning_message",
            description="Draft a dunning message for an overdue invoice. Returns draft text.",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                    "invoice_id": {"type": "string"},
                    "amount": {"type": "number"},
                    "days_overdue": {"type": "integer"},
                    "tone": {"type": "string", "enum": ["gentle", "neutral", "firm"], "default": "neutral"},
                    "language": {"type": "string", "default": "en"},
                },
                "required": ["customer_name", "invoice_id", "amount", "days_overdue"],
            },
        ),
    ]


@server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "draft_email":
            result = await _draft_email(arguments)
        elif name == "draft_purchase_order":
            result = await _draft_purchase_order(arguments)
        elif name == "draft_dunning_message":
            result = await _draft_dunning_message(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        result = {"error": str(exc)}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def _draft_email(args: dict[str, Any]) -> dict[str, str]:
    from app.infra.llm.openai import chat_completion  # noqa: PLC0415

    prompt = (
        f"Draft a professional email.\n"
        f"Purpose: {args['purpose']}\n"
        f"Recipient: {args.get('recipient_name', 'recipient')}\n"
        f"Tone: {args.get('tone', 'neutral')}\n"
        f"Language: {args.get('language', 'en')}\n"
        f"Context: {args['context']}\n\n"
        "Write the email body only (no subject line). Keep it concise."
    )
    draft = await chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model="gpt-4o-mini",
        max_tokens=500,
        temperature=0.3,
    )
    return {"draft": draft, "status": "draft_only — requires HITL approval before sending"}


async def _draft_purchase_order(args: dict[str, Any]) -> dict[str, str]:
    from app.infra.llm.openai import chat_completion  # noqa: PLC0415

    prompt = (
        f"Draft a purchase order email to {args['supplier_name']}.\n"
        f"Product: {args['product_name']}\n"
        f"Quantity: {args['quantity']} units\n"
        f"Language: {args.get('language', 'en')}\n"
        "Write the email body only. Be professional and specific."
    )
    draft = await chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model="gpt-4o-mini",
        max_tokens=400,
        temperature=0.2,
    )
    return {
        "draft": draft,
        "action_type": "purchase_order_send",
        "status": "draft_only — requires HITL approval before sending",
    }


async def _draft_dunning_message(args: dict[str, Any]) -> dict[str, str]:
    from app.infra.llm.openai import chat_completion  # noqa: PLC0415

    tone_instructions = {
        "gentle": "Be polite and understanding. Assume good faith.",
        "neutral": "Be professional and factual.",
        "firm": "Be direct and clear about consequences. Remain professional.",
    }
    tone = args.get("tone", "neutral")
    prompt = (
        f"Draft a payment reminder for {args['customer_name']}.\n"
        f"Invoice: {args['invoice_id']}\n"
        f"Amount: {args['amount']}\n"
        f"Days overdue: {args['days_overdue']}\n"
        f"Tone: {tone} — {tone_instructions.get(tone, '')}\n"
        f"Language: {args.get('language', 'en')}\n"
        "Write the email body only."
    )
    draft = await chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model="gpt-4o-mini",
        max_tokens=400,
        temperature=0.3,
    )
    return {
        "draft": draft,
        "tone_used": tone,
        "status": "draft_only — requires HITL approval before sending",
    }


def get_tool_functions() -> dict[str, Any]:
    return {
        "draft_email": _draft_email,
        "draft_purchase_order": _draft_purchase_order,
        "draft_dunning_message": _draft_dunning_message,
    }
