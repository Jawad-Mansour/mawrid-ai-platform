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
