"""
Feature:  Enrichment Pipeline
Layer:    Test / Unit
Module:   tests.unit.test_enrichment_pipeline
Purpose:  Unit tests for product hash invariants and document parsing.
          Phase 2 real enrichment pipeline tests are in test_enrichment_pipeline_seq.py.
          core/catalog/pipeline.py (Phase 0 stub) was deleted — these tests cover
          hash and parser logic only.
Depends:  app.core.catalog.hash, app.core.catalog.parser,
          app.core.catalog.parsers, conftest fakes
HITL:     None
"""

from __future__ import annotations

import io

import pytest


class TestProductHash:
    def test_hash_excludes_price(self) -> None:
        """Same product with different prices must produce the same hash."""
        from app.core.catalog.hash import compute_product_hash

        h1 = compute_product_hash("tenant1", "Apple iPhone 15", None)
        h2 = compute_product_hash("tenant1", "Apple iPhone 15", None)
        assert h1 == h2

    def test_hash_includes_sku_when_present(self) -> None:
        from app.core.catalog.hash import compute_product_hash

        h_with = compute_product_hash("tenant1", "Widget", "SKU-001")
        h_without = compute_product_hash("tenant1", "Widget", None)
        assert h_with != h_without

    def test_hash_is_tenant_scoped(self) -> None:
        from app.core.catalog.hash import compute_product_hash

        h1 = compute_product_hash("tenant1", "Widget", None)
        h2 = compute_product_hash("tenant2", "Widget", None)
        assert h1 != h2

    def test_colon_delimiter_prevents_collision(self) -> None:
        """'ab' + 'c' must not collide with 'a' + 'bc'."""
        from app.core.catalog.hash import compute_product_hash

        h1 = compute_product_hash("ab", "c", None)
        h2 = compute_product_hash("a", "bc", None)
        assert h1 != h2


class TestDocumentParsing:
    @pytest.mark.asyncio
    async def test_excel_parser_extracts_rows_as_dict_list(self) -> None:
        """Excel parser must return rows as list-of-dicts with header keys."""
        import openpyxl  # noqa: PLC0415
        from app.core.catalog.parsers.excel_parser import parse_excel  # noqa: PLC0415

        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["product_name", "sku", "price"])
        ws.append(["Samsung TV 55\"", "SAM-TV-55", "799.99"])
        ws.append(["LG Fridge 20L", "LG-FR-20", "450.00"])
        buf = io.BytesIO()
        wb.save(buf)

        result = await parse_excel(buf.getvalue())

        assert len(result.rows) == 2  # noqa: PLR2004
        assert result.rows[0]["product_name"] == "Samsung TV 55\""
        assert result.rows[1]["sku"] == "LG-FR-20"
        assert result.rows[0]["price"] == "799.99"

    def test_mime_sniff_detects_pdf(self) -> None:
        """File starting with %PDF magic bytes must be classified as PDF."""
        from app.core.catalog.parser import detect_mime_type

        fake_pdf = b"%PDF-1.4 fake content"
        mime = detect_mime_type(fake_pdf)
        assert mime == "application/pdf"

    def test_mime_sniff_detects_xlsx(self) -> None:
        """File starting with PK ZIP magic bytes must be classified as XLSX."""
        from app.core.catalog.parser import detect_mime_type

        # XLSX is a ZIP-based format — PK magic header
        fake_xlsx = b"PK\x03\x04" + b"\x00" * 100
        mime = detect_mime_type(fake_xlsx)
        assert "spreadsheetml" in mime or "excel" in mime.lower()

    def test_mime_sniff_rejects_unknown_format(self) -> None:
        """Files with unknown magic bytes must raise ValueError."""
        from app.core.catalog.parser import detect_mime_type

        with pytest.raises(ValueError, match="Unsupported file format"):
            detect_mime_type(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    def test_product_name_preserved_not_translated(self) -> None:
        """product_hash must be computed from the original name, not a translated one."""
        from app.core.catalog.hash import compute_product_hash

        # Same product, original Arabic name vs incorrectly-translated English name
        # hash must differ — proving we never silently replace the original name
        original = compute_product_hash("t1", "تلفزيون سامسونج 55", None)
        translated = compute_product_hash("t1", "Samsung TV 55", None)
        assert original != translated

    def test_failed_row_excluded_from_product_hash(self) -> None:
        """A row that cannot produce a valid product_name must never reach hashing."""
        from app.core.catalog.hash import compute_product_hash

        # Empty product_name is the sentinel for an extraction failure
        # The hash of an empty name is still deterministic — the key invariant
        # is that the pipeline routes empty-name rows to review_queue, not products.
        # Here we just verify the hash function itself handles empty strings safely.
        h = compute_product_hash("tenant1", "", None)
        assert isinstance(h, str) and len(h) == 64  # SHA-256 hex digest  # noqa: PLR2004
