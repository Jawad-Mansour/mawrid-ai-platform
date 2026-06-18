"""
Feature:  Catalog Enrichment Pipeline (GPT-4o Extraction)
Layer:    Core / Service
Module:   app.core.catalog.extractor
Purpose:  Phase 2.3 — Row-by-row GPT-4o extraction from parsed document rows.
          Normalises multilingual column headers to English keys.
          Preserves product_name EXACTLY as written (never translated).
          Rows without a resolvable product_name are placed in failed_rows
          and routed to review_queue by the caller — no product record is created.
          Processes rows in batches of 20 to stay within GPT-4o context limits.
Depends:  app.infra.llm.openai
HITL:     None — extraction is internal.
"""

from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass, field

import structlog

from app.infra.llm.openai import chat_completion

logger = structlog.get_logger(__name__)

_BATCH_SIZE = 20

_SYSTEM_PROMPT = """\
You are a product data extraction assistant for a wholesale trading platform.
Your output is used to look the product up on the web, so the product_name and
model code must be the SEARCHABLE identity of the item — not a generic category.

Given a list of product rows from a supplier price list (PDF/Excel), output a JSON
array where each element has these fields:

{
  "product_name": "<a complete, searchable product title>",
  "sku": "<the manufacturer model number / MPN, or null>",
  "barcode": "<EAN-13 / UPC-12 barcode (12-13 digits) or null>",
  "price": <float or null>,
  "currency": "<3-letter ISO code or null>",
  "specifications": { "<English key>": "<value>" },
  "_row_index": <integer — same as input row_index>,
  "_failure_reason": "<short reason if no product can be identified, else null>"
}

Rules:
1. product_name: build the title a person would type to find this exact product.
   Supplier sheets often split it across columns (Brand, category/"Product",
   "Description", "Model"). COMBINE them into one title: "<Brand> <type> <model code>".
   Keep original spelling; never translate. Do not output a bare category like
   "WASHING MACHINE" if a brand and model code exist in the row.
2. sku = the MANUFACTURER MODEL NUMBER / MPN — the alphanumeric code (e.g.
   "ROW41066DWMCZ-19", "WH-1000XM5", "920-011568"). A purely numeric internal/supplier
   code (e.g. "31011482") is NOT a model number — put it in specifications as
   "Supplier Code" and use the real model code for sku. The model code is often in a
   column labelled "Description", "Model", "MPN" or similar even when the header says
   something else.
3. barcode = 12-13 digit EAN/UPC only (never the model code).
4. price = the SUPPLIER'S unit price from the sheet, as a plain number (no currency
   symbol, no thousands separators). Price columns are labelled many ways across
   languages: "Price", "Unit Price", "Cost", "PU", "Prix", "Prix Unitaire", "Tarif",
   "السعر", "ثمن", "Importo", "Precio". If several prices exist (e.g. cost vs RRP),
   pick the supplier/cost price. If no price is present, use null.
5. currency = the 3-letter ISO code for that price ("USD", "EUR", "LBP", "AED"…).
   Infer from a currency symbol ($ → USD, € → EUR, £ → GBP) or a currency column.
6. ALWAYS capture the available quantity / stock the supplier is offering into
   specifications under the EXACT English key "Quantity", as a plain integer string.
   Quantity columns are labelled "QTY", "Qty", "Stock", "Available", "On Hand",
   "Quantité", "الكمية", "المخزون", "Cantidad". This is what the importer can order.
7. Normalise any OTHER useful columns to English keys in specifications (Color, Material,
   Size, Capacity, Power, Dimensions, Weight, etc.) — these power search and the card.
   Record colour/finish verbatim if given (e.g. "Silver", "Inox", "Anthracite").
8. If a row truly has no identifiable product, set product_name=null + _failure_reason.
9. Return ONLY a valid JSON array — no markdown fences, no extra text.

Worked example — input row:
  {"Product Line":"WASHING","Product Code":"31011482","Product Description":"ROW41066DWMCZ-19","Brand":"CANDY","Product":"WASHING MACHINE","Color":"Silver","Prix":"389.00","QTY":"272"}
Correct output element:
  {"product_name":"Candy Washing Machine ROW41066DWMCZ-19","sku":"ROW41066DWMCZ-19","barcode":null,"price":389.0,"currency":"USD",
   "specifications":{"Brand":"Candy","Type":"Washing Machine","Color":"Silver","Supplier Code":"31011482","Quantity":"272"},"_row_index":0,"_failure_reason":null}
"""


@dataclass
class ExtractedProduct:
    row_index: int
    product_name: str
    sku: str | None
    barcode: str | None
    price: float | None
    currency: str | None
    specifications: dict[str, str]
    raw_row: dict[str, object]


@dataclass
class ExtractionResult:
    products: list[ExtractedProduct] = field(default_factory=list)
    failed_rows: list[tuple[dict[str, object], str]] = field(default_factory=list)


def _build_user_message(batch: list[dict[str, object]], start_idx: int) -> str:
    rows_with_index = [{"row_index": start_idx + i, **row} for i, row in enumerate(batch)]
    return json.dumps(rows_with_index, ensure_ascii=False)


def _parse_response(
    raw: str,
    batch: list[dict[str, object]],
    start_idx: int,
) -> tuple[list[ExtractedProduct], list[tuple[dict[str, object], str]]]:
    """Parse GPT-4o JSON output. Returns (products, failed_rows)."""
    # Strip markdown code fences if model adds them despite instructions
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        items: list[dict[str, object]] = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("extractor_json_parse_failed", error=str(exc), raw=raw[:200])
        return [], [(row, "GPT-4o response was not valid JSON") for row in batch]

    products: list[ExtractedProduct] = []
    failed: list[tuple[dict[str, object], str]] = []

    for item in items:
        row_idx: int = int(str(item.get("_row_index", start_idx)))
        original_row: dict[str, object] = (
            batch[row_idx - start_idx] if 0 <= row_idx - start_idx < len(batch) else {}
        )
        failure_reason: str | None = (
            str(item["_failure_reason"]) if item.get("_failure_reason") else None
        )
        product_name: str | None = str(item["product_name"]) if item.get("product_name") else None

        if not product_name or failure_reason:
            reason = failure_reason or "product_name could not be determined"
            failed.append((dict(original_row), reason))
            continue

        specs_raw = item.get("specifications", {})
        specs: dict[str, str] = (
            {str(k): str(v) for k, v in specs_raw.items()} if isinstance(specs_raw, dict) else {}
        )

        price_raw = item.get("price")
        price: float | None = None
        if price_raw is not None:
            with contextlib.suppress(TypeError, ValueError):
                price = float(str(price_raw))

        products.append(
            ExtractedProduct(
                row_index=row_idx,
                product_name=str(product_name),
                sku=str(item["sku"]) if item.get("sku") else None,
                barcode=str(item["barcode"]) if item.get("barcode") else None,
                price=price,
                currency=str(item["currency"]) if item.get("currency") else None,
                specifications=specs,
                raw_row=dict(original_row),
            )
        )

    return products, failed


async def extract_rows(rows: list[dict[str, object]]) -> ExtractionResult:
    """
    Extract structured product data from parsed document rows using GPT-4o.

    Processes rows in batches of 20. Each batch is one GPT-4o call.
    Returns ExtractionResult with products (success) and failed_rows (routed to
    review_queue by the caller — no product record is created for failed rows).
    """
    result = ExtractionResult()

    for batch_start in range(0, len(rows), _BATCH_SIZE):
        batch = rows[batch_start : batch_start + _BATCH_SIZE]
        logger.info("extractor_batch", start=batch_start, size=len(batch))

        messages: list[dict[str, object]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(batch, batch_start)},
        ]

        try:
            raw = await chat_completion(messages, temperature=0.0, max_tokens=4096)
            products, failed = _parse_response(raw, batch, batch_start)
            result.products.extend(products)
            result.failed_rows.extend(failed)
        except Exception as exc:
            logger.error("extractor_batch_failed", start=batch_start, error=str(exc))
            result.failed_rows.extend((row, f"LLM call failed: {exc}") for row in batch)

    logger.info(
        "extractor_complete",
        total_rows=len(rows),
        extracted=len(result.products),
        failed=len(result.failed_rows),
    )
    return result
