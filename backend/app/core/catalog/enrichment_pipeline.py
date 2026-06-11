"""
Feature:  Catalog Enrichment Pipeline (Sequential)
Layer:    Core / Service
Module:   app.core.catalog.enrichment_pipeline
Purpose:  Phase 2.4 — Deterministic 5-step enrichment pipeline per extracted product.
          Step 1: Icecat Open lookup (EAN → name fallback).
          Step 2: SearXNG meta-search for web specs.
          Step 3: httpx + trafilatura — fetch and clean top 3 pages.
          Step 4: GPT-4o spec extraction from web content.
          Step 5: GPT-4o description generation.
          Confidence: high (Icecat EAN + spec_count ≥ 5), medium (name + spec_count ≥ 3),
          partial (SearXNG only or no specs found).
          This is NOT a LangGraph agent — Phase 8's Enrichment Specialist wraps
          this pipeline in a single LangGraph node.
Depends:  app.infra.llm.openai, httpx, trafilatura
HITL:     None — enrichment is internal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

import httpx
import structlog
import trafilatura

from app.infra.llm.openai import chat_completion

logger = structlog.get_logger(__name__)

_ICECAT_BASE = "https://icecat.us/api"
_SEARXNG_TIMEOUT = 8.0
_HTTPX_TIMEOUT = 10.0
_MAX_WEB_CHARS = 8000  # truncate scraped content to stay within GPT-4o context
_TOP_URLS = 3


# ── Protocols for dependency injection (testable without network) ─────────────


class _IcecatClient(Protocol):
    async def lookup_ean(self, ean: str) -> dict[str, object] | None: ...

    async def lookup_name(self, name: str) -> dict[str, object] | None: ...


class _SearxngClient(Protocol):
    async def search(self, query: str) -> list[str]: ...


class _WebFetcher(Protocol):
    async def fetch_and_clean(self, url: str) -> str: ...


# ── Data types ────────────────────────────────────────────────────────────────


@dataclass
class EnrichmentInput:
    product_name: str
    sku: str | None = None
    barcode: str | None = None
    price: float | None = None
    currency: str | None = None
    specifications: dict[str, str] = field(default_factory=dict)


@dataclass
class EnrichmentOutput:
    product_name: str
    sku: str | None
    barcode: str | None
    price: float | None
    currency: str | None
    specifications: dict[str, str]
    description: str
    image_url: str | None
    enrichment_source: str
    enrichment_confidence: str


# ── Real network clients ──────────────────────────────────────────────────────


class IcecatClient:
    """Icecat Open REST API client. Auth = Basic(username, empty-password)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def lookup_ean(self, ean: str) -> dict[str, object] | None:
        try:
            async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT) as client:
                resp = await client.get(
                    f"{_ICECAT_BASE}/products",
                    params={"ean": ean, "language": "en"},
                    auth=(self._api_key, ""),
                    headers={"Accept": "application/json"},
                )
                if resp.status_code != 200:  # noqa: PLR2004
                    return None
                data: dict[str, object] = resp.json()
                return data.get("data") or None  # type: ignore[return-value]
        except Exception as exc:
            logger.warning("icecat_ean_lookup_failed", ean=ean, error=str(exc))
            return None

    async def lookup_name(self, name: str) -> dict[str, object] | None:
        try:
            async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT) as client:
                resp = await client.get(
                    f"{_ICECAT_BASE}/products",
                    params={"query": name, "language": "en"},
                    auth=(self._api_key, ""),
                    headers={"Accept": "application/json"},
                )
                if resp.status_code != 200:  # noqa: PLR2004
                    return None
                data: dict[str, object] = resp.json()
                results = data.get("data")
                if isinstance(results, list) and results:
                    item = results[0]
                    return item if isinstance(item, dict) else None
                return None
        except Exception as exc:
            logger.warning("icecat_name_lookup_failed", name=name, error=str(exc))
            return None


class SearxngClient:
    """SearXNG meta-search client. Returns list of result URLs."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=_SEARXNG_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/search",
                    params={"q": query, "format": "json", "categories": "general"},
                )
                if resp.status_code != 200:  # noqa: PLR2004
                    return []
                payload: dict[str, object] = resp.json()
                results = payload.get("results", [])
                if not isinstance(results, list):
                    return []
                return [
                    str(r["url"])
                    for r in results
                    if isinstance(r, dict) and r.get("url")
                ][:_TOP_URLS]
        except Exception as exc:
            logger.warning("searxng_search_failed", query=query, error=str(exc))
            return []


class WebFetcher:
    """Fetches a URL and returns cleaned plaintext via trafilatura."""

    async def fetch_and_clean(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code >= 400:  # noqa: PLR2004
                    return ""
                text = trafilatura.extract(resp.text) or ""
                return text[:_MAX_WEB_CHARS]
        except Exception as exc:
            logger.warning("web_fetch_failed", url=url, error=str(exc))
            return ""


# ── Icecat response parsing ───────────────────────────────────────────────────


def _parse_icecat(
    data: dict[str, object],
    matched_by: str,
) -> tuple[dict[str, str], str | None, int, str]:
    """
    Extract specs, image URL, spec count, and confidence from Icecat response.
    Returns (specs, image_url, spec_count, source).
    """
    specs: dict[str, str] = {}
    image_url: str | None = None

    features_groups = data.get("FeaturesGroups") or data.get("featuresGroups") or []
    if isinstance(features_groups, list):
        for group in features_groups:
            if not isinstance(group, dict):
                continue
            features = group.get("Features") or group.get("features") or []
            if not isinstance(features, list):
                continue
            for feat in features:
                if not isinstance(feat, dict):
                    continue
                name = feat.get("Feature", {})
                if isinstance(name, dict):
                    key = str(name.get("Name") or name.get("name") or "")
                else:
                    key = str(name)
                value = str(feat.get("Value") or feat.get("value") or "")
                if key and value:
                    specs[key] = value

    img_data = data.get("Image") or data.get("image") or {}
    if isinstance(img_data, dict):
        image_url = str(img_data.get("HighPic") or img_data.get("highPic") or "") or None

    spec_count = len(specs)
    confidence: str
    if matched_by == "ean" and spec_count >= 5:  # noqa: PLR2004
        confidence = "high"
    elif spec_count >= 3:  # noqa: PLR2004
        confidence = "medium"
    else:
        confidence = "partial"

    return specs, image_url, spec_count, confidence


# ── GPT-4o spec fill ─────────────────────────────────────────────────────────

_SPEC_FILL_PROMPT = """\
You are a technical product data specialist.

Given the product name, existing specifications (may be empty), and web content
scraped from product pages, extract or infer additional specifications.

Return a JSON object with these keys only:
{
  "specifications": { "<English key>": "<value>" },
  "description": "<2-3 sentence product description in English>"
}

Rules:
- Merge and deduplicate with existing specifications.
- Do NOT invent values — only use what appears in the web content.
- Keep keys short and in Title Case (e.g. "Screen Size", "RAM", "Battery Capacity").
- Return ONLY valid JSON — no markdown fences.
"""


async def _gpt4o_enrich(
    product_name: str,
    existing_specs: dict[str, str],
    web_content: str,
) -> tuple[dict[str, str], str]:
    """Returns (merged_specs, description)."""
    user_content = json.dumps(
        {
            "product_name": product_name,
            "existing_specifications": existing_specs,
            "web_content": web_content[:_MAX_WEB_CHARS],
        },
        ensure_ascii=False,
    )
    messages: list[dict[str, object]] = [
        {"role": "system", "content": _SPEC_FILL_PROMPT},
        {"role": "user", "content": user_content},
    ]
    try:
        raw = await chat_completion(messages, temperature=0.0, max_tokens=1024)
        import re  # noqa: PLC0415

        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        parsed: dict[str, object] = json.loads(cleaned)
        merged_specs: dict[str, str] = dict(existing_specs)
        new_specs = parsed.get("specifications", {})
        if isinstance(new_specs, dict):
            merged_specs.update({str(k): str(v) for k, v in new_specs.items()})
        description = str(parsed.get("description") or "")
    except Exception as exc:
        logger.warning("gpt4o_enrich_failed", product=product_name, error=str(exc))
        merged_specs = dict(existing_specs)
        description = ""

    return merged_specs, description


# ── Main pipeline ─────────────────────────────────────────────────────────────


class SequentialEnrichmentPipeline:
    """
    5-step sequential enrichment pipeline. One call per product.
    All network calls gracefully degrade: a timeout or error in any step
    does not abort the pipeline — the product is still enriched with
    whatever data was gathered before the failure.
    """

    def __init__(
        self,
        icecat: _IcecatClient,
        searxng: _SearxngClient,
        fetcher: _WebFetcher,
    ) -> None:
        self._icecat = icecat
        self._searxng = searxng
        self._fetcher = fetcher

    async def run(self, inp: EnrichmentInput) -> EnrichmentOutput:
        specs: dict[str, str] = dict(inp.specifications)
        image_url: str | None = None
        confidence = "partial"
        source = "web"

        # ── Step 1: Icecat ────────────────────────────────────────────────────
        icecat_data: dict[str, object] | None = None
        matched_by = "name"

        try:
            if inp.barcode:
                icecat_data = await self._icecat.lookup_ean(inp.barcode)
                matched_by = "ean"

            if icecat_data is None:
                icecat_data = await self._icecat.lookup_name(inp.product_name)
                matched_by = "name"
        except Exception as exc:
            logger.warning("icecat_client_error", product=inp.product_name, error=str(exc))

        if icecat_data is not None:
            icecat_specs, image_url, spec_count, confidence = _parse_icecat(
                icecat_data, matched_by
            )
            specs.update(icecat_specs)
            source = "icecat"
            logger.info(
                "icecat_hit",
                product=inp.product_name,
                matched_by=matched_by,
                spec_count=spec_count,
                confidence=confidence,
            )

        # Skip web search if Icecat already gave us high confidence
        web_text = ""
        if confidence != "high":
            # ── Step 2: SearXNG ───────────────────────────────────────────────
            query = f"{inp.product_name} {inp.sku or ''} specifications datasheet".strip()
            urls = await self._searxng.search(query)

            # ── Step 3: httpx + trafilatura ───────────────────────────────────
            page_texts: list[str] = []
            for url in urls:
                text = await self._fetcher.fetch_and_clean(url)
                if text:
                    page_texts.append(text)
            web_text = "\n\n---\n\n".join(page_texts)

            if source == "icecat":
                source = "icecat"  # stays icecat even if we augment with web
            elif web_text:
                source = "web"

        # ── Steps 4 & 5: GPT-4o spec fill + description ───────────────────────
        merged_specs, description = await _gpt4o_enrich(
            inp.product_name, specs, web_text
        )

        # If confidence is still partial but we got decent specs now, bump it
        if confidence == "partial" and len(merged_specs) >= 3:  # noqa: PLR2004
            confidence = "medium"

        return EnrichmentOutput(
            product_name=inp.product_name,
            sku=inp.sku,
            barcode=inp.barcode,
            price=inp.price,
            currency=inp.currency,
            specifications=merged_specs,
            description=description,
            image_url=image_url,
            enrichment_source=source,
            enrichment_confidence=confidence,
        )


def build_pipeline(icecat_api_key: str, searxng_base_url: str) -> SequentialEnrichmentPipeline:
    """Factory — constructs the real pipeline with live network clients."""
    return SequentialEnrichmentPipeline(
        icecat=IcecatClient(icecat_api_key),
        searxng=SearxngClient(searxng_base_url),
        fetcher=WebFetcher(),
    )
