// Feature: Dunning Engine (4 Tracks)
// Layer:   Component / Dunning
// Purpose: Invoice aging buckets table. Shows invoices grouped by days overdue:
//          current / 1-30 / 31-60 / 61-90 / 90+ days. All dates computed
//          from due_date (not invoice_date). Color-coded severity.
// API:     GET /api/v1/invoices?include_aging=true

export function InvoiceAgingTable() {
  return <div>InvoiceAgingTable</div>;
}
