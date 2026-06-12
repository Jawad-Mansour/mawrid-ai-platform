"""
Feature:  NLP Search & RAG Pipeline / AI Agents (cross-cutting)
Layer:    Guardrails / Safety
Module:   app.guardrails.nemo_guard
Purpose:  Two-layer guardrail: input rail (jailbreak + off-topic + prompt
          injection detection) and output rail (grounding / hallucination
          guard). Uses prompts from nemo/prompts.yml and calls gpt-4o-mini
          for each check. Fail-open: if the LLM check itself fails, the
          request is allowed through and the error is logged.
          Protocol-typed so unit tests can inject a FakeGuard without any
          LLM calls.
Depends:  app.infra.llm.openai, pyyaml
HITL:     None — guardrails are automated.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml

logger = logging.getLogger(__name__)

# Path to prompts.yml relative to this file
_PROMPTS_PATH = Path(__file__).parent / "nemo" / "prompts.yml"

# Refusal / fallback messages (must match what input.co sends)
_INPUT_BLOCKED_MSG = (
    "I can only help with questions about your import business and product catalog."
)
_OUTPUT_FALLBACK_MSG = (
    "I can only provide information based on the available product data. "
    "I don't have enough information to answer that accurately."
)

# gpt-4o-mini for rail checks (cheap + fast per config.yml)
_GUARD_MODEL = "gpt-4o-mini"


# ── Protocol ────────────────────────────────────────────────────────────────


@runtime_checkable
class GuardProtocol(Protocol):
    """
    Interface for input + output guardrail checks.
    Inject a fake implementation in unit tests to avoid real LLM calls.
    """

    async def check_input(self, text: str) -> tuple[bool, str]:
        """
        Check whether a user message should be allowed to reach the LLM.

        Returns:
            (True, "")           — message is safe, proceed normally.
            (False, refusal_msg) — blocked; return refusal_msg to the user.
        """
        ...

    async def check_output(self, response: str, context: str) -> tuple[bool, str]:
        """
        Check whether an LLM response is grounded in the provided context.

        Returns:
            (True, "")            — response is grounded, return to user.
            (False, fallback_msg) — hallucination detected; return fallback_msg.
        """
        ...


# ── Prompt loader ────────────────────────────────────────────────────────────


def _load_prompts() -> dict[str, str]:
    """Load task → template mapping from nemo/prompts.yml."""
    with open(_PROMPTS_PATH) as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return {entry["task"]: entry["content"] for entry in data.get("prompts", [])}


# ── Production implementation ────────────────────────────────────────────────


class NeMoGuard:
    """
    Production guardrail backed by gpt-4o-mini self-check calls.

    Input rail:  reads self_check_input prompt from prompts.yml.
    Output rail: reads self_check_output prompt from prompts.yml.

    Both rails are fail-open: if the LLM call itself raises, the request
    is allowed through (availability > strict blocking).
    """

    def __init__(self) -> None:
        self._prompts: dict[str, str] = _load_prompts()

    async def check_input(self, text: str) -> tuple[bool, str]:
        """
        Runs the self_check_input rail.
        Returns (True, "") if safe, (False, refusal_msg) if blocked.
        """
        template = self._prompts.get("self_check_input", "")
        if not template:
            return True, ""

        prompt = template.replace("{{ user_input }}", text)
        try:
            from app.infra.llm.openai import chat_completion  # noqa: PLC0415

            verdict = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=_GUARD_MODEL,
                temperature=0.0,
                max_tokens=8,
            )
            is_safe = verdict.strip().lower().startswith("yes")
            if not is_safe:
                logger.warning("nemo_input_blocked text=%s", text[:80])
                return False, _INPUT_BLOCKED_MSG
            return True, ""
        except Exception:
            logger.exception("nemo_input_check_failed_fail_open")
            return True, ""

    async def check_output(self, response: str, context: str) -> tuple[bool, str]:
        """
        Runs the self_check_output rail.
        Returns (True, "") if grounded, (False, fallback_msg) if hallucinated.
        """
        template = self._prompts.get("self_check_output", "")
        if not template:
            return True, ""

        prompt = template.replace(
            "{{ context }}", context[:4000]
        ).replace("{{ bot_response }}", response)  # cap context for token budget
        try:
            from app.infra.llm.openai import chat_completion  # noqa: PLC0415

            verdict = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=_GUARD_MODEL,
                temperature=0.0,
                max_tokens=8,
            )
            is_grounded = verdict.strip().lower().startswith("yes")
            if not is_grounded:
                logger.warning("nemo_output_hallucination_detected")
                return False, _OUTPUT_FALLBACK_MSG
            return True, ""
        except Exception:
            logger.exception("nemo_output_check_failed_fail_open")
            return True, ""


# ── Lazy singleton ───────────────────────────────────────────────────────────

_default_guard: NeMoGuard | None = None


def get_default_guard() -> NeMoGuard:
    """Return (or lazily create) the module-level NeMoGuard singleton."""
    global _default_guard
    if _default_guard is None:
        _default_guard = NeMoGuard()
    return _default_guard
