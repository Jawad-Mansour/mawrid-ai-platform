// Feature: All features (cross-cutting)
// Layer:   Lib / Types
// Purpose: Shared TypeScript type definitions mirroring backend Pydantic models.
//          Single source of truth for frontend API types — generated from
//          OpenAPI schema in CI Gate 6.

export type OperationalMode = "hybrid" | "wholesale_only" | "retail_only";

export type HITLActionType =
  | "purchase_order_send" | "dispute_letter" | "supplier_outreach"
  | "supplier_match_review" | "customer_match_review"
  | "dunning_payables_advance" | "dunning_disputes_on_demand"
  | "dunning_receivables_day7" | "dunning_receivables_day14" | "dunning_receivables_day21"
  | "dunning_b2c_day3" | "dunning_b2c_day7" | "dunning_b2c_day14"
  | "fulfillment_notification";

export type HITLStatus = "pending" | "approved" | "rejected" | "editing" | "executed" | "expired";

export interface HITLAction {
  action_id: string;
  tenant_id: string;
  action_type: HITLActionType;
  status: HITLStatus;
  payload: Record<string, unknown>;
  created_at: string;
  expires_at: string | null;
}

export interface Product {
  product_id: string;
  product_name: string;
  sku: string | null;
  enrichment_status: "pending" | "processing" | "enriched" | "failed" | "dlq";
  inventory_status: "in_stock" | "low_stock" | "out_of_stock";
  storefront_status: "draft" | "published" | "archived";
  qty_in_stock: number;
  storefront_qty: number;
}
