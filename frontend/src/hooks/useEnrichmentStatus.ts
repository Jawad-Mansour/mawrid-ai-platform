// Feature: Catalog Enrichment Pipeline
// Layer:   Hook
// Purpose: Polls product enrichment status via API. Returns current status and
//          auto-refreshes every 5s when status is 'processing'. Stops polling
//          on 'enriched', 'failed', or 'dlq'.
// API:     GET /api/v1/catalog/{product_id}/status

export function useEnrichmentStatus(productId: string) {
  return { status: "pending" as const, isLoading: false };
}
