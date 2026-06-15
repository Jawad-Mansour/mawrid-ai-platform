"""
Feature:  RAG Pipeline / AI Agents / Enrichment (cross-cutting)
Layer:    Infra / LLM
Module:   app.infra.llm.openai
Purpose:  Async OpenAI client wrapper. Provides chat completion (GPT-4o) and
          text embeddings (text-embedding-3-small, 1536-dim). All LLM calls
          for enrichment, RAG, and agents go through this module.
          Retry logic: 3 attempts with exponential backoff (tenacity).
          Usage is logged via structlog for cost tracking.
Depends:  openai, tenacity, app.infra.secrets.vault
HITL:     None — infrastructure only.
"""

from __future__ import annotations

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.infra.secrets.vault import get_secrets

logger = structlog.get_logger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        secrets = get_secrets()
        _client = AsyncOpenAI(api_key=secrets.openai_api_key)
    return _client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def chat_completion(
    messages: list[dict[str, object]],
    model: str = "gpt-4o",
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> str:
    """Call GPT-4o chat completion. Returns the assistant message text."""
    from openai.types.chat import ChatCompletionMessageParam  # noqa: PLC0415

    typed_messages: list[ChatCompletionMessageParam] = messages  # type: ignore[assignment]
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=typed_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content or ""
    logger.info(
        "llm_call",
        model=model,
        prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
        completion_tokens=response.usage.completion_tokens if response.usage else 0,
    )
    return content


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def embed_text(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Embed a single text string. Returns 1536-dim float vector."""
    client = _get_client()
    response = await client.embeddings.create(input=text, model=model)
    return response.data[0].embedding


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def embed_batch(texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
    """Embed a batch of texts. Returns list of 1536-dim float vectors."""
    client = _get_client()
    response = await client.embeddings.create(input=texts, model=model)
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
