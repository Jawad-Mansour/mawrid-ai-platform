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
from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile, status

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
from app.infra.storage.minio import get_presigned_url, split_object_path, upload_document

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


class ProductCard(StrictModel):
    """Full catalog card — everything the listing/order pages render."""

    product_id: str
    product_name: str
    sku: str | None
    barcode: str | None
    description: str | None
    specifications: dict[str, Any] | None
    image_url: str | None
    source_urls: list[dict[str, str]] | None
    price: float | None
    currency: str | None
    retail_price: float | None
    qty_in_stock: int
    enrichment_status: str
    inventory_status: str
    storefront_status: str
    enrichment_confidence: str | None
    enrichment_source: str | None


class AskProductRequest(StrictModel):
    question: str


class AskProductResponse(StrictModel):
    product_id: str
    answer: str
    sources: list[dict[str, str]]


async def _resolve_image_url(tenant_id: str, image_path: str | None) -> str | None:
    """An enriched image is either a direct http(s) URL (Icecat/web og:image) or a
    MinIO object path; return something the browser can load directly."""
    if not image_path:
        return None
    if image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path
    try:
        bucket, obj = split_object_path(image_path)
        return await get_presigned_url(bucket, obj)
    except Exception as exc:  # noqa: BLE001
        logger.warning("image_presign_failed", path=image_path, error=str(exc))
        return None


def _latest_price(product: Product) -> float | None:
    history = product.price_history or []
    if not history:
        return None
    last = history[-1]
    if isinstance(last, dict) and last.get("price") is not None:
        try:
            return float(last["price"])
        except (TypeError, ValueError):
            return None
    return None


async def _to_card(tenant_id: str, p: Product) -> ProductCard:
    return ProductCard(
        product_id=p.product_id,
        product_name=p.product_name,
        sku=p.sku,
        barcode=p.barcode,
        description=p.description,
        specifications=p.specifications,
        image_url=await _resolve_image_url(tenant_id, p.image_path),
        source_urls=p.source_urls,
        price=_latest_price(p),
        currency=p.currency,
        retail_price=float(p.retail_price) if p.retail_price is not None else None,
        qty_in_stock=p.qty_in_stock,
        enrichment_status=p.enrichment_status,
        inventory_status=p.inventory_status,
        storefront_status=p.storefront_status,
        enrichment_confidence=p.enrichment_confidence,
        enrichment_source=p.enrichment_source,
    )


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
    supplier_name: str | None = Form(default=None),
    supplier_location: str | None = Form(default=None),
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

    # Capture the supplier (name + location) provided at upload time.
    if supplier_name and supplier_name.strip():
        from app.infra.db.repos.supplier_repo import SupplierRepository  # noqa: PLC0415

        sup_repo = SupplierRepository(session, tenant_id)
        existing_sup = await sup_repo.find_by_name_exact(supplier_name.strip())
        if existing_sup is None:
            await sup_repo.create(
                supplier_id=uuid.uuid4().hex,
                name=supplier_name.strip(),
                location=(supplier_location.strip() if supplier_location else None),
            )
        elif supplier_location and supplier_location.strip():
            await sup_repo.update(existing_sup.supplier_id, location=supplier_location.strip())

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
    response_model=list[ProductCard],
    summary="List internal catalog products with full enrichment (image, specs, sources, price)",
)
async def list_catalog_products(
    current_user: CurrentUser,
    session: SessionDep,
    limit: int = 200,
) -> list[ProductCard]:
    product_repo = ProductRepository(session, current_user.tenant_id)
    products = await product_repo.list_all(limit=limit)
    return [await _to_card(current_user.tenant_id, p) for p in products]


@router.get(
    "/products/{product_id}",
    response_model=ProductCard,
    summary="Get one product with full enrichment detail",
)
async def get_catalog_product(
    product_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> ProductCard:
    product_repo = ProductRepository(session, current_user.tenant_id)
    product = await product_repo.get_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return await _to_card(current_user.tenant_id, product)


@router.post(
    "/products/{product_id}/ask",
    response_model=AskProductResponse,
    summary="Ask the enrichment agent a follow-up question about a specific product",
)
async def ask_about_product(
    product_id: str,
    body: AskProductRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> AskProductResponse:
    """Grounded Q&A about one product: the agent searches the web by the product's
    code/name for fresh detail and answers the importer's follow-up question."""
    product_repo = ProductRepository(session, current_user.tenant_id)
    product = await product_repo.get_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    from app.core.config import get_settings  # noqa: PLC0415
    from app.core.catalog.enrichment_pipeline import WebFetcher  # noqa: PLC0415
    from app.infra.llm.openai import chat_completion  # noqa: PLC0415
    from app.infra.secrets.vault import get_secrets  # noqa: PLC0415

    settings = get_settings()
    sources: list[dict[str, str]] = list(product.source_urls or [])
    web_text = ""
    try:
        from app.core.catalog.enrichment_pipeline import SearxngClient  # noqa: PLC0415

        searx = SearxngClient(settings.searxng_base_url)
        fetcher = WebFetcher()
        code = product.sku or product.barcode or product.product_name
        urls = await searx.search(f"{product.product_name} {code} {body.question}")
        from urllib.parse import urlparse  # noqa: PLC0415

        for url in urls[:3]:
            text, _ = await fetcher.fetch_page(url)
            if text:
                web_text += text[:3000] + "\n\n"
                sources.append({"title": urlparse(url).netloc or url, "url": url})
    except Exception as exc:  # noqa: BLE001
        logger.warning("ask_product_web_failed", product_id=product_id, error=str(exc))

    _ = get_secrets()  # ensure secrets are loaded for the LLM call
    context = {
        "product_name": product.product_name,
        "sku": product.sku,
        "specifications": product.specifications or {},
        "known_description": product.description or "",
        "fresh_web_research": web_text[:6000],
    }
    import json as _json  # noqa: PLC0415

    answer = await chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a product research assistant for an importer. Answer the user's "
                    "question about this specific product using the provided product data and "
                    "web research. Be concrete and concise. If you are unsure, say so plainly."
                ),
            },
            {"role": "user", "content": f"Question: {body.question}\n\nProduct data:\n{_json.dumps(context, ensure_ascii=False)}"},
        ],
        temperature=0.2,
        max_tokens=400,
    )
    # de-dup sources by url
    seen: set[str] = set()
    uniq = [s for s in sources if s.get("url") and not (s["url"] in seen or seen.add(s["url"]))]
    return AskProductResponse(product_id=product_id, answer=answer.strip(), sources=uniq[:6])
