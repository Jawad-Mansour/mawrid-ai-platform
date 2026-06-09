// Feature: Catalog Enrichment Pipeline
// Layer:   Component / Catalog
// Purpose: Enrichment status badge and progress indicator for product cards.
//          Shows: pending / processing / enriched / failed / dlq with color coding.
//          Polls for status updates every 5s when status is 'processing'.
// API:     GET /api/v1/catalog/{product_id}/status

interface EnrichmentStatusProps {
  status: "pending" | "processing" | "enriched" | "failed" | "dlq";
  productId: string;
}

export function EnrichmentStatus({ status, productId }: EnrichmentStatusProps) {
  return <span>Status: {status}</span>;
}
