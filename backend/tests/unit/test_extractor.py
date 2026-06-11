"""
Feature:  Catalog Enrichment Pipeline (GPT-4o Extraction)
Layer:    Test / Unit
Module:   tests.unit.test_extractor
Purpose:  Unit tests for the GPT-4o row extractor (Phase 2.3).
          Verifies: product_name preservation, failed row routing, batch
          processing, JSON parse robustness, multilingual header normalisation.
          All LLM calls replaced with fake that returns deterministic JSON.
Depends:  app.core.catalog.extractor
HITL:     None
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


class TestExtractor:
    @pytest.mark.asyncio
    async def test_extracts_product_name_exactly(self) -> None:
        """product_name in output must match input value verbatim."""
        from app.core.catalog.extractor import extract_rows

        rows: list[dict[str, object]] = [
            {"product_name": "Samsung Galaxy S24 Ultra", "price": "1199.99", "sku": "SGS24U"}
        ]
        llm_response = json.dumps([
            {
                "row_index": 0,
                "product_name": "Samsung Galaxy S24 Ultra",
                "sku": "SGS24U",
                "barcode": None,
                "price": 1199.99,
                "currency": "USD",
                "specifications": {"RAM": "12GB", "Storage": "256GB"},
                "_failure_reason": None,
            }
        ])

        with patch("app.core.catalog.extractor.chat_completion", new=AsyncMock(return_value=llm_response)):
            result = await extract_rows(rows)

        assert len(result.products) == 1
        assert result.products[0].product_name == "Samsung Galaxy S24 Ultra"
        assert result.products[0].sku == "SGS24U"
        assert result.products[0].price == 1199.99  # noqa: PLR2004

    @pytest.mark.asyncio
    async def test_arabic_product_name_preserved(self) -> None:
        """Arabic product names must not be translated by the extractor."""
        from app.core.catalog.extractor import extract_rows

        rows: list[dict[str, object]] = [{"اسم المنتج": "تلفزيون سامسونج 55 بوصة", "السعر": "750"}]
        llm_response = json.dumps([
            {
                "row_index": 0,
                "product_name": "تلفزيون سامسونج 55 بوصة",
                "sku": None,
                "barcode": None,
                "price": 750.0,
                "currency": None,
                "specifications": {"Screen Size": "55 inch"},
                "_failure_reason": None,
            }
        ])

        with patch("app.core.catalog.extractor.chat_completion", new=AsyncMock(return_value=llm_response)):
            result = await extract_rows(rows)

        assert len(result.products) == 1
        assert result.products[0].product_name == "تلفزيون سامسونج 55 بوصة"

    @pytest.mark.asyncio
    async def test_row_without_product_name_goes_to_failed(self) -> None:
        """Rows where GPT-4o cannot determine product_name must go to failed_rows."""
        from app.core.catalog.extractor import extract_rows

        rows: list[dict[str, object]] = [{"col_0": "", "col_1": "123.00"}]
        llm_response = json.dumps([
            {
                "row_index": 0,
                "product_name": None,
                "sku": None,
                "barcode": None,
                "price": 123.0,
                "currency": None,
                "specifications": {},
                "_failure_reason": "No product name found in row",
            }
        ])

        with patch("app.core.catalog.extractor.chat_completion", new=AsyncMock(return_value=llm_response)):
            result = await extract_rows(rows)

        assert len(result.products) == 0
        assert len(result.failed_rows) == 1
        assert "product name" in result.failed_rows[0][1].lower()

    @pytest.mark.asyncio
    async def test_llm_failure_routes_batch_to_failed(self) -> None:
        """If the LLM call raises an exception, the whole batch goes to failed_rows."""
        from app.core.catalog.extractor import extract_rows

        rows: list[dict[str, object]] = [
            {"product": "Widget A", "price": "10.00"},
            {"product": "Widget B", "price": "20.00"},
        ]

        with patch(
            "app.core.catalog.extractor.chat_completion",
            new=AsyncMock(side_effect=RuntimeError("API timeout")),
        ):
            result = await extract_rows(rows)

        assert len(result.products) == 0
        assert len(result.failed_rows) == 2  # noqa: PLR2004
        assert all("LLM call failed" in reason for _, reason in result.failed_rows)

    @pytest.mark.asyncio
    async def test_invalid_json_routes_batch_to_failed(self) -> None:
        """If GPT-4o returns non-JSON, the batch goes to failed_rows."""
        from app.core.catalog.extractor import extract_rows

        rows: list[dict[str, object]] = [{"product": "Widget A", "price": "10.00"}]

        with patch(
            "app.core.catalog.extractor.chat_completion",
            new=AsyncMock(return_value="Sorry, I cannot help with that."),
        ):
            result = await extract_rows(rows)

        assert len(result.products) == 0
        assert len(result.failed_rows) == 1

    @pytest.mark.asyncio
    async def test_specifications_are_english_keys(self) -> None:
        """Specification keys must be in English regardless of source language."""
        from app.core.catalog.extractor import extract_rows

        rows: list[dict[str, object]] = [
            {"المنتج": "كمبيوتر محمول ديل", "الذاكرة": "16 جيجابايت"}
        ]
        llm_response = json.dumps([
            {
                "row_index": 0,
                "product_name": "كمبيوتر محمول ديل",
                "sku": None,
                "barcode": None,
                "price": None,
                "currency": None,
                "specifications": {"RAM": "16GB", "Brand": "Dell"},
                "_failure_reason": None,
            }
        ])

        with patch("app.core.catalog.extractor.chat_completion", new=AsyncMock(return_value=llm_response)):
            result = await extract_rows(rows)

        assert len(result.products) == 1
        specs = result.products[0].specifications
        assert "RAM" in specs
        assert specs["RAM"] == "16GB"
