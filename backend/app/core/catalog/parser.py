"""
Feature:  Catalog Enrichment Pipeline (Document Parsing)
Layer:    Core / Service
Module:   app.core.catalog.parser
Purpose:  MIME-type dispatcher. Sniffs file bytes to determine PDF vs Excel,
          then delegates to the appropriate parser. Returns a unified ParseResult.
          Raises ValueError for unsupported formats. Supported: PDF, XLSX, XLS.
Depends:  app.core.catalog.parsers, python-magic (sniff) or header bytes
HITL:     None.
"""

from __future__ import annotations

from app.core.catalog.parsers.excel_parser import parse_excel
from app.core.catalog.parsers.pdf_parser import ParseResult, parse_pdf

# MIME types we accept
_PDF_MAGIC = b"%PDF"
_XLSX_MAGIC = b"PK\x03\x04"  # ZIP-based (Office Open XML)
_XLS_MAGIC = b"\xd0\xcf\x11\xe0"  # Compound Document


def _sniff_mime(data: bytes) -> str:
    if data[:4] == _PDF_MAGIC:
        return "application/pdf"
    if data[:4] == _XLSX_MAGIC:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if data[:4] == _XLS_MAGIC:
        return "application/vnd.ms-excel"
    raise ValueError("Unsupported file format. Only PDF and Excel files are accepted.")


async def parse_document(file_bytes: bytes, tenant_id: str) -> ParseResult:
    """Dispatch to the correct parser based on file magic bytes."""
    mime = _sniff_mime(file_bytes)
    if mime == "application/pdf":
        return await parse_pdf(file_bytes, tenant_id)
    return await parse_excel(file_bytes)


def detect_mime_type(file_bytes: bytes) -> str:
    """Return the detected MIME type without parsing. Raises ValueError if unsupported."""
    return _sniff_mime(file_bytes)
