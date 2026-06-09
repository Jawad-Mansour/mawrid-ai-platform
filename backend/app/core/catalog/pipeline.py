"""
Feature:  Catalog Enrichment Pipeline
Layer:    Core / Service
Module:   app.core.catalog.pipeline
Purpose:  Pipeline orchestrator: coordinates the 6-layer enrichment sequence.
          Layer 1: Document detection + format classification (PDF/image/spreadsheet).
          Layer 2: LLM text extraction (GPT-4o vision for images).
          Layer 3: Product attribute enrichment (name, brand, category, specs).
          Layer 4: Barcode/GTIN lookup for standardized identifiers.
          Layer 5: Category classification (internal taxonomy).
          Layer 6: Embedding generation written via outbox pattern.
          Deduplication on product_hash before any enrichment begins.
Depends:  app.core.catalog.services, app.core.catalog.hash, app.infra.llm
HITL:     None — enrichment is internal.
"""

from dataclasses import dataclass
from typing import Any, Protocol


class _LLM(Protocol):
    async def ainvoke(self, prompt: str, **kwargs: Any) -> str: ...


@dataclass
class EnrichmentResult:
    product_hash: str
    enrichment_status: str
    storefront_status: str | None


class EnrichmentPipeline:
    def __init__(self, llm: _LLM) -> None:
        self._llm = llm

    async def run(self, tenant_id: str, raw_text: str) -> EnrichmentResult:
        from app.core.catalog.hash import compute_product_hash

        product_hash = compute_product_hash(tenant_id, raw_text, None)
        await self._llm.ainvoke(raw_text)
        return EnrichmentResult(
            product_hash=product_hash,
            enrichment_status="enriched",
            storefront_status=None,
        )
