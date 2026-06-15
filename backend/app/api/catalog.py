"""
Feature:  Catalog Enrichment Pipeline
Layer:    API / Router
Module:   app.api.catalog
Purpose:  HTTP routes for supplier document upload (Layer 1), async enrichment
          trigger (Layer 2-4 via ARQ), enrichment status polling, internal
          catalog browse, and review queue listing.
          Upload is idempotent: document_id = SHA-256(file_bytes). Re-uploading
          the same file returns 200 with the existing document record.
          /enrich submits one ARQ job per extracted product and returns immediately.
Depends:  app.core.catalog.parser, app.core.catalog.extractor,
          app.infra.db.repos.*, app.infra.storage.minio, app.api.deps
HITL:     None — enrichment is internal. Publishing is in procurement.py.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.core.catalog.extractor import extract_rows
from app.core.catalog.hash import compute_product_hash
from app.core.catalog.parser import detect_mime_type, parse_document
from app.infra.cache.redis_client import get_arq_pool
from app.infra.db.models.document import Document
from app.infra.db.models.product import Product
from app.infra.db.repos.document_repo import DocumentRepository
from app.infra.db.repos.product_repo import ProductRepository
from app.infra.db.repos.review_queue_repo import ReviewQueueRepository
from app.infra.storage.minio import upload_document

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])

# ── Response schemas ───────────────────────────────────────────────────────────


class DocumentUploadResponse(StrictModel):
    document_id: str
    status: str
    filename: str
    rows_extracted: int
    already_existed: bool


class DocumentStatusResponse(StrictModel):
    document_id: str
    status: str
    filename: str
    row_counts: dict[str, Any] | None
    enrichment_progress: dict[str, int] | None
    uploaded_at: str
    completed_at: str | None


class EnrichResponse(StrictModel):
    document_id: str
    jobs_submitted: int
    failed_rows: int


class ProductSummary(StrictModel):
    product_id: str
    product_name: str
    sku: str | None
    enrichment_status: str
    storefront_status: str
    enrichment_confidence: str | None
    enrichment_source: str | None


class ReviewQueueItemResponse(StrictModel):
    id: str
    document_id: str
    raw_row: dict[str, Any]
    failure_reason: str
    status: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload a supplier document (PDF or Excel) for enrichment",
)
async def upload_supplier_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    session: SessionDep,
) -> DocumentUploadResponse:
    """
    Upload a PDF or Excel supplier catalog. Idempotent on document content:
    re-uploading the same file returns the existing record without re-processing.

    Steps:
    1. Hash file bytes (SHA-256) → document_id
    2. Idempotency check — return existing record if found
    3. Validate MIME type (PDF or Excel only)
    4. Store raw file in MinIO
    5. Parse document (Docling for PDF, openpyxl for Excel)
    6. Persist document record with status=completed, row_counts, and parsed_rows
    """
    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded.",
        )

    document_id = hashlib.sha256(file_bytes).hexdigest()
    tenant_id = current_user.tenant_id
    doc_repo = DocumentRepository(session, tenant_id)

    # Idempotency check
    existing = await doc_repo.get_by_id(document_id)
    if existing is not None:
        logger.info("document_already_exists", document_id=document_id)
        row_counts = existing.row_counts or {}
        return DocumentUploadResponse(
            document_id=document_id,
            status=existing.status,
            filename=existing.filename,
            rows_extracted=int(row_counts.get("extracted", 0)),
            already_existed=True,
        )

    # Validate format before storing
    try:
        mime_type = detect_mime_type(file_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    filename = file.filename or "upload"

    # Persist document record as processing
    doc = Document(
        document_id=document_id,
        tenant_id=tenant_id,
        filename=filename,
        mime_type=mime_type,
        file_size_bytes=len(file_bytes),
        status="processing",
    )
    await doc_repo.upsert(doc)

    # Store raw file in MinIO (fail silently — we have parsed_rows as backup)
    object_name = f"documents/{document_id}/{filename}"
    try:
        await upload_document(tenant_id, object_name, file_bytes, mime_type)
    except Exception as exc:
        logger.warning("minio_upload_failed", document_id=document_id, error=str(exc))

    # Parse document inline
    try:
        parse_result = await parse_document(file_bytes, tenant_id)
        rows_extracted = len(parse_result.rows)
        await doc_repo.update_status(
            document_id,
            "completed",
            row_counts={"extracted": rows_extracted, "pages": parse_result.page_count},
            parsed_rows=parse_result.rows,
        )
    except Exception as exc:
        logger.error("document_parse_failed", document_id=document_id, error=str(exc))
        await doc_repo.update_status(document_id, "failed")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Document parsing failed: {exc}",
        ) from exc

    await session.commit()

    logger.info(
        "document_uploaded",
        document_id=document_id,
        rows=rows_extracted,
        tenant_id=tenant_id,
    )

    # Notify n8n WF-02 (best-effort background task — never raises)
    from app.infra.n8n.client import fire_event  # noqa: PLC0415

    background_tasks.add_task(
        fire_event,
        "wf02-document-uploaded",
        {"tenant_id": tenant_id, "document_id": document_id, "row_count": rows_extracted},
    )

    return DocumentUploadResponse(
        document_id=document_id,
        status="completed",
        filename=filename,
        rows_extracted=rows_extracted,
        already_existed=False,
    )


@router.post(
    "/documents/{document_id}/enrich",
    response_model=EnrichResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Extract products and submit one ARQ enrichment job per product",
)
async def enrich_document(
    document_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> EnrichResponse:
    """
    Trigger async enrichment for a parsed document.

    Steps:
    1. Load parsed_rows from the documents table
    2. GPT-4o extraction inline — fast (one call per batch of rows)
    3. Failed rows → review_queue
    4. Create product stubs (enrichment_status='pending') — idempotent on product_hash
    5. Submit one ARQ job per product → returns immediately
    """
    tenant_id = current_user.tenant_id
    doc_repo = DocumentRepository(session, tenant_id)
    product_repo = ProductRepository(session, tenant_id)
    review_repo = ReviewQueueRepository(session, tenant_id)

    doc = await doc_repo.get_by_id(document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if doc.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not in completed state (current: {doc.status}).",
        )

    rows: list[dict[str, object]] = doc.parsed_rows or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document has no parsed rows. Re-upload the file.",
        )

    # Step 1: GPT-4o extraction — inline (one batch call, fast)
    extraction = await extract_rows(rows)

    # Step 2: Route failed rows to review_queue
    for raw_row, reason in extraction.failed_rows:
        await review_repo.add(document_id, raw_row, reason)

    # Step 3: Create product stubs + submit ARQ jobs (idempotent)
    arq_pool = get_arq_pool()
    jobs_submitted = 0

    for extracted in extraction.products:
        product_hash = compute_product_hash(tenant_id, extracted.product_name, extracted.sku)
        existing = await product_repo.get_by_hash(product_hash)

        price_entry: dict[str, object] = {}
        if extracted.price is not None:
            price_entry = {
                "price": extracted.price,
                "currency": extracted.currency or "USD",
                "source": "supplier_document",
                "document_id": document_id,
            }

        if existing is None:
            product = Product(
                product_id=uuid.uuid4().hex,
                tenant_id=tenant_id,
                product_hash=product_hash,
                product_name=extracted.product_name,
                sku=extracted.sku,
                barcode=extracted.barcode,
                enrichment_status="pending",
                price_history=[price_entry] if price_entry else [],
            )
            result = await product_repo.upsert(product)
        else:
            # Already exists — update price history if new price
            if price_entry and existing.price_history is not None:
                existing.price_history = [*existing.price_history, price_entry]
            result = existing

        # Skip already-enriched products
        if result.enrichment_status == "enriched":
            continue

        await arq_pool.enqueue_job(
            "enrich_product",
            tenant_id=tenant_id,
            product_id=result.product_id,
        )
        jobs_submitted += 1

    await session.commit()

    logger.info(
        "enrich_jobs_submitted",
        document_id=document_id,
        jobs_submitted=jobs_submitted,
        failed_rows=len(extraction.failed_rows),
        tenant_id=tenant_id,
    )
    return EnrichResponse(
        document_id=document_id,
        jobs_submitted=jobs_submitted,
        failed_rows=len(extraction.failed_rows),
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentStatusResponse,
    summary="Get document processing status and enrichment progress",
)
async def get_document_status(
    document_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> DocumentStatusResponse:
    from sqlalchemy import func, select

    from app.infra.db.models.product import Product

    tenant_id = current_user.tenant_id
    doc_repo = DocumentRepository(session, tenant_id)
    doc = await doc_repo.get_by_id(document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Compute enrichment progress: count products per status linked to this doc's extracted hashes
    # We group by enrichment_status for products under this tenant created from this document.
    # Since products aren't directly linked to documents, we count all tenant products by status.
    progress_result = await session.execute(
        select(Product.enrichment_status, func.count().label("n"))
        .where(Product.tenant_id == tenant_id)
        .group_by(Product.enrichment_status)
    )
    enrichment_progress = {row.enrichment_status: row.n for row in progress_result}

    return DocumentStatusResponse(
        document_id=doc.document_id,
        status=doc.status,
        filename=doc.filename,
        row_counts=doc.row_counts,
        enrichment_progress=enrichment_progress or None,
        uploaded_at=doc.uploaded_at.isoformat(),
        completed_at=doc.completed_at.isoformat() if doc.completed_at else None,
    )


@router.get(
    "/documents/{document_id}/review-queue",
    response_model=list[ReviewQueueItemResponse],
    summary="List rows that failed extraction for a document",
)
async def list_review_queue(
    document_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> list[ReviewQueueItemResponse]:
    review_repo = ReviewQueueRepository(session, current_user.tenant_id)
    items = await review_repo.list_by_document(document_id)
    return [
        ReviewQueueItemResponse(
            id=item.id,
            document_id=item.document_id,
            raw_row=item.raw_row,
            failure_reason=item.failure_reason,
            status=item.status,
        )
        for item in items
    ]


@router.get(
    "/barcode/{barcode}",
    response_model=ProductSummary,
    summary="Look up a product by barcode (EAN-13/UPC/Code-128)",
)
async def get_product_by_barcode(
    barcode: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> ProductSummary:
    product_repo = ProductRepository(session, current_user.tenant_id)
    product = await product_repo.get_by_barcode(barcode)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product with barcode '{barcode}'.",
        )
    return ProductSummary(
        product_id=product.product_id,
        product_name=product.product_name,
        sku=product.sku,
        enrichment_status=product.enrichment_status,
        storefront_status=product.storefront_status,
        enrichment_confidence=product.enrichment_confidence,
        enrichment_source=product.enrichment_source,
    )


@router.post(
    "/products/{product_id}/retry-enrichment",
    summary="Re-queue enrichment for a failed product (DLQ retry)",
)
async def retry_product_enrichment(
    product_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    """Re-submits an enrichment job for a product that previously failed.
    Idempotent: ARQ skips the job if the product is already enriched.
    """
    product_repo = ProductRepository(session, current_user.tenant_id)
    product = await product_repo.get_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    if product.enrichment_status == "enriched":
        return {"product_id": product_id, "status": "already_enriched"}

    arq = get_arq_pool()
    await arq.enqueue_job(
        "enrich_product",
        tenant_id=current_user.tenant_id,
        product_id=product_id,
    )
    logger.info("enrichment_retried", product_id=product_id)
    return {"product_id": product_id, "status": "queued"}


@router.get(
    "/products",
    response_model=list[ProductSummary],
    summary="List internal catalog products (not storefront — use /storefront for published)",
)
async def list_catalog_products(
    current_user: CurrentUser,
    session: SessionDep,
    limit: int = 50,
) -> list[ProductSummary]:
    product_repo = ProductRepository(session, current_user.tenant_id)
    products = await product_repo.list_all(limit=limit)
    return [
        ProductSummary(
            product_id=p.product_id,
            product_name=p.product_name,
            sku=p.sku,
            enrichment_status=p.enrichment_status,
            storefront_status=p.storefront_status,
            enrichment_confidence=p.enrichment_confidence,
            enrichment_source=p.enrichment_source,
        )
        for p in products
    ]
