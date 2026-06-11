"""
Feature:  Document Storage (cross-cutting)
Layer:    Infra / Storage
Module:   app.infra.storage.minio
Purpose:  MinIO S3-compatible client. Handles supplier document uploads (PDF/Excel),
          embedded product image storage, and presigned URL generation for downloads.
          Bucket name = tenant_id for per-tenant isolation. image_path stored as
          MinIO object path (tenant_id/images/uuid.ext) — never a raw URL.
          Presigned URLs are generated at serve time with a short TTL.
Depends:  minio (SDK), app.infra.secrets.vault
HITL:     None — storage infrastructure only.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.infra.secrets.vault import get_secrets

_client: Minio | None = None


def _get_client() -> Minio:
    global _client
    if _client is None:
        secrets = get_secrets()
        _client = Minio(
            endpoint=secrets.minio_endpoint,
            access_key=secrets.minio_access_key,
            secret_key=secrets.minio_secret_key,
            secure=False,
        )
    return _client


def _ensure_bucket(client: Minio, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def _upload_sync(bucket: str, object_name: str, data: bytes, content_type: str) -> str:
    client = _get_client()
    _ensure_bucket(client, bucket)
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return f"{bucket}/{object_name}"


def _presign_sync(bucket: str, object_name: str, expires_seconds: int = 3600) -> str:
    client = _get_client()
    return client.presigned_get_object(
        bucket_name=bucket,
        object_name=object_name,
        expires=timedelta(seconds=expires_seconds),
    )


def _download_sync(bucket: str, object_name: str) -> bytes:
    client = _get_client()
    response = client.get_object(bucket_name=bucket, object_name=object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def _delete_sync(bucket: str, object_name: str) -> None:
    client = _get_client()
    with contextlib.suppress(S3Error):
        client.remove_object(bucket_name=bucket, object_name=object_name)


async def upload_document(
    tenant_id: str,
    object_name: str,
    data: bytes,
    content_type: str,
) -> str:
    """Upload bytes to MinIO. Returns object path (tenant_id/object_name)."""
    return await asyncio.to_thread(
        _upload_sync, tenant_id, object_name, data, content_type
    )


async def upload_image(
    tenant_id: str,
    object_name: str,
    data: bytes,
) -> str:
    """Upload image bytes to MinIO. Returns object path."""
    return await asyncio.to_thread(
        _upload_sync, tenant_id, object_name, data, "image/png"
    )


async def get_presigned_url(
    tenant_id: str,
    object_name: str,
    expires_seconds: int = 3600,
) -> str:
    """Generate a presigned GET URL valid for expires_seconds."""
    return await asyncio.to_thread(
        _presign_sync, tenant_id, object_name, expires_seconds
    )


async def download_bytes(tenant_id: str, object_name: str) -> bytes:
    """Download an object and return its bytes."""
    return await asyncio.to_thread(_download_sync, tenant_id, object_name)


async def delete_object(tenant_id: str, object_name: str) -> None:
    """Delete an object. Silently ignores missing objects."""
    await asyncio.to_thread(_delete_sync, tenant_id, object_name)


def split_object_path(path: str) -> tuple[str, str]:
    """Split 'bucket/object/name' into (bucket, object/name)."""
    parts = path.split("/", 1)
    if len(parts) != 2:  # noqa: PLR2004
        raise ValueError(f"Invalid MinIO object path: {path!r}")
    return parts[0], parts[1]
