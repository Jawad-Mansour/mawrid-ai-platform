// Feature: All features — shared API types (mirror backend response models)

export type OperationalMode = "hybrid" | "wholesale_only" | "retail_only";

export interface MeResponse {
  user_id: string;
  tenant_id: string;
  email: string;
  role: string;
  operational_mode: OperationalMode;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface DashboardSummary {
  published_products: number;
  enriched_products: number;
  pending_enrichment: number;
  failed_enrichment: number;
  low_stock_count: number;
  active_shipments: number;
  total_invoices: number;
  overdue_invoices: number;
  outstanding_receivables: number;
  pending_hitl_count: number;
  consumer_orders_pending: number;
  generated_at: string;
}

export interface ModelHealth {
  name: string;
  status: string;
  latest_version: string | null;
  stage: string | null;
}
export interface AIHealthResponse {
  models: ModelHealth[];
  eval_thresholds: Record<string, any>;
  drift_status: string;
  checked_at: string;
}

export interface WorkflowStatus {
  workflow_id: string;
  name: string;
  active: boolean;
  last_execution_status: string | null;
  last_execution_at: string | null;
}
export interface N8nStatusResponse {
  status: string;
  workflows: WorkflowStatus[];
}

export interface SourceLink { title: string; url: string }

export interface Product {
  product_id: string;
  product_name: string;
  sku: string | null;
  barcode: string | null;
  description: string | null;
  specifications: Record<string, any> | null;
  enrichment_status: string;
  enrichment_source: string | null;
  enrichment_confidence: string | null;
  inventory_status?: string | null;
  storefront_status: string;
  qty_in_stock?: number;
  storefront_qty?: number;
  price?: number | null;
  retail_price?: number | null;
  currency?: string | null;
  available_qty?: number | null;
  image_url?: string | null;
  source_urls?: SourceLink[] | null;
  supplier_names?: string[] | null;
  document_ids?: string[] | null;
}

export interface AskProductResponse {
  product_id: string;
  answer: string;
  sources: SourceLink[];
}

export interface DocumentHistoryItem {
  document_id: string;
  filename: string;
  status: string;
  supplier_name: string | null;
  rows_extracted: number;
  uploaded_at: string;
}

export interface HITLAction {
  action_id: string;
  action_type: string;
  status: string;
  payload: Record<string, any>;
  created_at: string;
  expires_at: string | null;
}

export interface DunningSequence {
  sequence_id: string;
  invoice_id: string;
  track: string;
  status: string;
  current_step: string | null;
  created_at: string;
}

export interface Supplier {
  supplier_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  language: string | null;
  currency: string | null;
  location?: string | null;
  description?: string | null;
  rating?: number | null;
  moq?: number | null;
  score?: number | null;
  relationship?: string | null;
  condition?: string | null;
  category?: string | null;
  website?: string | null;
}

export interface OrderDraft {
  order_id: string;
  supplier_id: string;
  status: string;
  line_items: Array<Record<string, any>>;
  notes: string | null;
  desired_delivery_date: string | null;
  created_at?: string;
}

export interface ChatSource {
  chunk_id: string;
  product_id: string;
  chunk_text: string;
  score: number;
}
export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  session_id: string | null;
  intent: string | null;
  route: string | null;
  tier_used: number | null;
}
