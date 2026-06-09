"""
Feature:  Document Storage (cross-cutting)
Layer:    Infra / Storage
Module:   app.infra.storage.minio
Purpose:  MinIO S3-compatible async client. Handles supplier document uploads
          (PDF/Excel/image), invoice PDF storage, and presigned URL generation
          for downloads. Bucket-per-tenant isolation.
Depends:  aioboto3 (S3-compatible)
HITL:     None — storage infrastructure only.
"""
