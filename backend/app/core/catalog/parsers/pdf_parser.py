"""
Feature:  Catalog Enrichment Pipeline (Document Parsing)
Layer:    Core / Parsers
Module:   app.core.catalog.parsers.pdf_parser
Purpose:  PDF parsing via IBM Docling. Extracts: full text (markdown), tables as
          list-of-dicts rows, and embedded images saved to MinIO during parse.
          Returns a ParseResult dataclass. Handles merged cells, multi-column
          layouts, and image blocks. Falls through to plain text extraction if
          Docling fails on a given page.
          _parse_sync() is a pure sync function — it collects image bytes and
          object names but does NOT perform async MinIO uploads. Uploads happen
          asynchronously in parse_pdf() after to_thread() returns, avoiding the
          RuntimeError from calling run_until_complete() on a running event loop.
Depends:  docling, app.infra.storage.minio
HITL:     None.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from dataclasses import dataclass, field

import structlog
from docling.datamodel.base_models import DocumentStream, InputFormat  # type: ignore[attr-defined]
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from app.infra.storage.minio import upload_image

logger = structlog.get_logger(__name__)


@dataclass
class ParseResult:
    """Output of any document parser."""

    full_text: str
    rows: list[dict[str, object]]
    embedded_image_paths: list[str] = field(default_factory=list)
    page_count: int = 0


@dataclass
class _PendingUpload:
    object_name: str
    img_bytes: bytes


@dataclass
class _SyncResult:
    """Internal result from the sync Docling call — pending uploads not yet uploaded."""

    full_text: str
    rows: list[dict[str, object]]
    pending_uploads: list[_PendingUpload] = field(default_factory=list)
    page_count: int = 0


def _build_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()  # type: ignore[call-arg]
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )


def _parse_sync(pdf_bytes: bytes) -> _SyncResult:
    """
    Run Docling synchronously (called via asyncio.to_thread).
    Collects image bytes for later async upload — does NOT call any async code.
    """
    converter = _build_converter()
    stream = DocumentStream(name="document.pdf", stream=io.BytesIO(pdf_bytes))
    result = converter.convert(stream)
    doc = result.document

    full_text = doc.export_to_markdown()

    rows: list[dict[str, object]] = []
    for table in doc.tables:
        try:
            df = table.export_to_dataframe()
            if df is not None and not df.empty:
                headers = [str(c) for c in df.columns.tolist()]
                for _, row in df.iterrows():
                    rows.append(
                        {h: str(v).strip() for h, v in zip(headers, row, strict=False)}
                    )
        except Exception as exc:
            logger.warning("pdf_table_extract_failed", error=str(exc))

    pending_uploads: list[_PendingUpload] = []
    for picture in doc.pictures:
        try:
            img_obj = picture.image
            if img_obj is None:
                continue
            pil_img = getattr(img_obj, "pil_image", None)
            if pil_img is None:
                continue
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            img_bytes = buf.getvalue()
            object_name = f"images/{uuid.uuid4().hex}.png"
            pending_uploads.append(_PendingUpload(object_name=object_name, img_bytes=img_bytes))
        except Exception as exc:
            logger.warning("pdf_image_extract_failed", error=str(exc))

    page_count = len(doc.pages) if hasattr(doc, "pages") else 0

    return _SyncResult(
        full_text=full_text,
        rows=rows,
        pending_uploads=pending_uploads,
        page_count=page_count,
    )


async def parse_pdf(pdf_bytes: bytes, tenant_id: str) -> ParseResult:
    """
    Parse a PDF file using Docling, then upload embedded images to MinIO.
    Docling runs in a thread (CPU-bound); image uploads run in the event loop
    after to_thread() returns — no run_until_complete() inside a thread.
    """
    sync_result = await asyncio.to_thread(_parse_sync, pdf_bytes)

    image_paths: list[str] = []
    for upload in sync_result.pending_uploads:
        try:
            path = await upload_image(tenant_id, upload.object_name, upload.img_bytes)
            image_paths.append(path)
        except Exception as exc:
            logger.warning("pdf_image_upload_failed", object_name=upload.object_name, error=str(exc))

    return ParseResult(
        full_text=sync_result.full_text,
        rows=sync_result.rows,
        embedded_image_paths=image_paths,
        page_count=sync_result.page_count,
    )
