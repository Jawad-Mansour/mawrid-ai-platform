"""
Feature:  Catalog Enrichment Pipeline (Sequential)
Layer:    Test / Unit
Module:   tests.unit.test_enrichment_pipeline_seq
Purpose:  Unit tests for the 5-step sequential enrichment pipeline (Phase 2.4).
          All network clients (Icecat, SearXNG, WebFetcher) are replaced with
          in-memory fakes — no real HTTP calls are made.
          Verifies: confidence scoring, Icecat-first logic, SearXNG fallback,
          web scraping integration, GPT-4o description generation, graceful
          degradation when any step fails.
Depends:  app.core.catalog.enrichment_pipeline
HITL:     None
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from app.core.catalog.enrichment_pipeline import (  # noqa: E402
    EnrichmentInput,
    SequentialEnrichmentPipeline,
)


class FakeIcecat:
    """Returns canned Icecat data for EAN lookups; None for name lookups."""

    def __init__(
        self,
        ean_data: dict[str, object] | None = None,
        name_data: dict[str, object] | None = None,
    ) -> None:
        self._ean_data = ean_data
        self._name_data = name_data

    async def lookup_ean(self, ean: str) -> dict[str, object] | None:
        return self._ean_data

    async def lookup_name(self, name: str) -> dict[str, object] | None:
        return self._name_data


class FakeSearxng:
    def __init__(self, urls: list[str] | None = None) -> None:
        self._urls = urls or []

    async def search(self, query: str) -> list[str]:
        return self._urls


class FakeWebFetcher:
    def __init__(self, content: str = "") -> None:
        self._content = content

    async def fetch_and_clean(self, url: str) -> str:
        return self._content


_ICECAT_RESPONSE_5_SPECS: dict[str, object] = {
    "FeaturesGroups": [
        {
            "Features": [
                {"Feature": {"Name": "RAM"}, "Value": "8GB"},
                {"Feature": {"Name": "Storage"}, "Value": "256GB"},
                {"Feature": {"Name": "Display"}, "Value": "6.1 inch"},
                {"Feature": {"Name": "Battery"}, "Value": "3279 mAh"},
                {"Feature": {"Name": "Camera"}, "Value": "12MP"},
            ]
        }
    ],
    "Image": {"HighPic": "https://icecat.example.com/img/product.jpg"},
}

_ICECAT_RESPONSE_2_SPECS: dict[str, object] = {
    "FeaturesGroups": [
        {
            "Features": [
                {"Feature": {"Name": "RAM"}, "Value": "8GB"},
                {"Feature": {"Name": "Storage"}, "Value": "256GB"},
            ]
        }
    ],
    "Image": {},
}


def _make_pipeline(
    icecat: FakeIcecat | None = None,
    searxng: FakeSearxng | None = None,
    fetcher: FakeWebFetcher | None = None,
) -> SequentialEnrichmentPipeline:
    return SequentialEnrichmentPipeline(
        icecat=icecat or FakeIcecat(),
        searxng=searxng or FakeSearxng(),
        fetcher=fetcher or FakeWebFetcher(),
    )


_GPT_ENRICH_RESPONSE = json.dumps(
    {
        "specifications": {"RAM": "8GB", "Storage": "256GB", "Color": "Black"},
        "description": "A flagship smartphone with premium camera and performance.",
    }
)


class TestIcecatConfidence:
    @pytest.mark.asyncio
    async def test_ean_match_high_confidence_skips_web(self) -> None:
        """EAN match with ≥5 specs must produce high confidence and skip SearXNG."""
        pipeline = _make_pipeline(
            icecat=FakeIcecat(ean_data=_ICECAT_RESPONSE_5_SPECS),
            searxng=FakeSearxng(urls=["http://example.com"]),
        )

        with patch(
            "app.core.catalog.enrichment_pipeline.chat_completion",
            new=AsyncMock(return_value=_GPT_ENRICH_RESPONSE),
        ):
            output = await pipeline.run(
                EnrichmentInput(product_name="iPhone 15", barcode="0194253710462")
            )

        assert output.enrichment_confidence == "high"
        assert output.enrichment_source == "icecat"

    @pytest.mark.asyncio
    async def test_ean_match_below_5_specs_is_medium(self) -> None:
        """EAN match with <5 specs falls to medium confidence."""
        pipeline = _make_pipeline(
            icecat=FakeIcecat(ean_data=_ICECAT_RESPONSE_2_SPECS),
        )

        with patch(
            "app.core.catalog.enrichment_pipeline.chat_completion",
            new=AsyncMock(return_value=_GPT_ENRICH_RESPONSE),
        ):
            output = await pipeline.run(
                EnrichmentInput(product_name="Some Phone", barcode="1234567890123")
            )

        assert output.enrichment_confidence in ("medium", "partial")

    @pytest.mark.asyncio
    async def test_icecat_miss_triggers_searxng(self) -> None:
        """When Icecat returns nothing, SearXNG must be called."""
        searxng = FakeSearxng(urls=["http://example.com/specs"])
        fetcher = FakeWebFetcher(content="RAM: 8GB Storage: 256GB")
        pipeline = _make_pipeline(
            icecat=FakeIcecat(ean_data=None, name_data=None),
            searxng=searxng,
            fetcher=fetcher,
        )

        with patch(
            "app.core.catalog.enrichment_pipeline.chat_completion",
            new=AsyncMock(return_value=_GPT_ENRICH_RESPONSE),
        ):
            output = await pipeline.run(
                EnrichmentInput(product_name="Generic Tablet", barcode=None)
            )

        assert output.enrichment_source == "web"

    @pytest.mark.asyncio
    async def test_icecat_timeout_falls_through_to_web(self) -> None:
        """Icecat timeout must not abort pipeline — falls through to SearXNG."""

        class TimeoutIcecat:
            async def lookup_ean(self, ean: str) -> dict[str, object] | None:
                raise TimeoutError("Icecat unreachable")

            async def lookup_name(self, name: str) -> dict[str, object] | None:
                raise TimeoutError("Icecat unreachable")

        pipeline = _make_pipeline(
            icecat=TimeoutIcecat(),  # type: ignore[arg-type]
            searxng=FakeSearxng(urls=["http://example.com"]),
            fetcher=FakeWebFetcher(content="Great product"),
        )

        with patch(
            "app.core.catalog.enrichment_pipeline.chat_completion",
            new=AsyncMock(return_value=_GPT_ENRICH_RESPONSE),
        ):
            output = await pipeline.run(
                EnrichmentInput(product_name="Widget X", barcode="9999999999999")
            )

        # Pipeline must still return a result
        assert output.product_name == "Widget X"
        assert output.enrichment_source == "web"


class TestEnrichmentOutput:
    @pytest.mark.asyncio
    async def test_description_is_generated(self) -> None:
        """Output must always contain a description from GPT-4o."""
        pipeline = _make_pipeline(
            icecat=FakeIcecat(name_data=_ICECAT_RESPONSE_5_SPECS),
        )

        with patch(
            "app.core.catalog.enrichment_pipeline.chat_completion",
            new=AsyncMock(return_value=_GPT_ENRICH_RESPONSE),
        ):
            output = await pipeline.run(EnrichmentInput(product_name="MacBook Pro"))

        assert len(output.description) > 0

    @pytest.mark.asyncio
    async def test_product_name_unchanged_in_output(self) -> None:
        """Pipeline must not alter the product_name — it is preserved verbatim."""
        pipeline = _make_pipeline()

        with patch(
            "app.core.catalog.enrichment_pipeline.chat_completion",
            new=AsyncMock(return_value=_GPT_ENRICH_RESPONSE),
        ):
            output = await pipeline.run(EnrichmentInput(product_name="تلفزيون سامسونج 65 بوصة"))

        assert output.product_name == "تلفزيون سامسونج 65 بوصة"

    @pytest.mark.asyncio
    async def test_existing_specs_merged_with_icecat(self) -> None:
        """Input specifications must be merged with Icecat specs in the output."""
        pipeline = _make_pipeline(
            icecat=FakeIcecat(name_data=_ICECAT_RESPONSE_5_SPECS),
        )
        gpt_response = json.dumps(
            {
                "specifications": {
                    "RAM": "8GB",
                    "Storage": "256GB",
                    "Display": "6.1 inch",
                    "Battery": "3279 mAh",
                    "Camera": "12MP",
                    "Color": "Midnight Black",
                },
                "description": "Flagship device.",
            }
        )

        with patch(
            "app.core.catalog.enrichment_pipeline.chat_completion",
            new=AsyncMock(return_value=gpt_response),
        ):
            output = await pipeline.run(
                EnrichmentInput(
                    product_name="iPhone 15",
                    specifications={"Color": "Midnight Black"},
                )
            )

        assert "RAM" in output.specifications
        assert "Color" in output.specifications
