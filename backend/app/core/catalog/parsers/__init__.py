"""
Feature:  Catalog Enrichment Pipeline (Document Parsing)
Layer:    Core / Parsers
Module:   app.core.catalog.parsers
Purpose:  Document parsers package. Exports ParseResult and the per-format
          parser implementations (PDF via Docling, Excel via openpyxl).
Depends:  app.core.catalog.parsers.pdf_parser, app.core.catalog.parsers.excel_parser
HITL:     None.
"""

from app.core.catalog.parsers.excel_parser import parse_excel
from app.core.catalog.parsers.pdf_parser import parse_pdf

__all__ = ["parse_pdf", "parse_excel"]
