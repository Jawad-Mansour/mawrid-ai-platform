// Feature: Catalog Enrichment — Upload History: every supplier sheet uploaded.
//          Each row can attach / fix its supplier (name · email · location) and be deleted.
// API:     GET /catalog/documents · PATCH /catalog/documents/{id}/supplier ·
//          DELETE /catalog/documents/{id} · GET /suppliers
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { FileSpreadsheet, UploadCloud, RefreshCw, Boxes, Mail, Pencil, AlertCircle, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPatch, apiDelete, apiErr } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState, StatusBadge, Spinner } from "@/components/ui";
import { SupplierEditModal } from "@/components/SupplierEditModal";
import { formatRelativeDate } from "@/lib/utils";
import type { DocumentHistoryItem, Supplier } from "@/lib/types";

function asList(d: unknown): DocumentHistoryItem[] {
  return Array.isArray(d) ? (d as DocumentHistoryItem[]) : [];
}
function asSuppliers(d: unknown): Supplier[] {
  return Array.isArray(d) ? (d as Supplier[]) : [];
}

export function UploadHistory() {
  const qc = useQueryClient();
  const docs = useQuery({ queryKey: ["documents"], queryFn: () => apiGet<unknown>("/catalog/documents"), refetchInterval: 10_000 });
  const suppliers = useQuery({ queryKey: ["suppliers"], queryFn: () => apiGet<unknown>("/suppliers") });
  const list = asList(docs.data);
  const supplierList = asSuppliers(suppliers.data);
  // The sheet whose supplier we're attaching/editing (null = modal closed).
  const [edit, setEdit] = useState<{ doc: DocumentHistoryItem; supplier: Supplier | null } | null>(null);

  function findSupplier(name: string | null): Supplier | null {
    if (!name) return null;
    return supplierList.find((s) => s.name.toLowerCase() === name.toLowerCase()) ?? null;
  }

  // Link (or update) a sheet's supplier after the modal saves it.
  const link = useMutation({
    mutationFn: ({ docId, s }: { docId: string; s: Supplier }) =>
      apiPatch(`/catalog/documents/${docId}/supplier`, { supplier_name: s.name, supplier_email: s.email, supplier_location: s.location }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["suppliers"] });
      toast.success("Supplier linked to sheet");
    },
    onError: (e) => toast.error(apiErr(e, "Couldn't link supplier")),
  });

  const del = useMutation({
    mutationFn: (docId: string) => apiDelete(`/catalog/documents/${docId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["catalog"] });
      toast.success("Sheet deleted");
    },
    onError: (e) => toast.error(apiErr(e, "Delete failed")),
  });

  return (
    <div className="space-y-6">
      <SectionTitle title="Upload History" subtitle="Every supplier sheet you've uploaded."
        right={<Link to="/upload" className="btn-gold !py-2"><UploadCloud className="h-4 w-4" /> Upload a sheet</Link>} />

      <Card>
        {docs.isLoading ? (
          <Loading />
        ) : list.length === 0 ? (
          <EmptyState icon={<FileSpreadsheet className="h-8 w-8" />} title="No uploads yet" hint="Upload a supplier sheet to get started." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-faint">
                  <th className="py-2.5 pr-3 font-600">Sheet</th>
                  <th className="px-3 font-600">Supplier</th>
                  <th className="px-3 font-600">Email</th>
                  <th className="px-3 font-600">Location</th>
                  <th className="px-3 font-600">Rows</th>
                  <th className="px-3 font-600">Status</th>
                  <th className="px-3 font-600">Uploaded</th>
                  <th className="px-3 font-600"></th>
                </tr>
              </thead>
              <tbody>
                {list.map((d) => {
                  const sup = findSupplier(d.supplier_name);
                  return (
                    <tr key={d.document_id} className="table-row">
                      <td className="py-3 pr-3">
                        <div className="flex items-center gap-2">
                          <FileSpreadsheet className="h-4 w-4 shrink-0 text-emerald-soft" />
                          <span className="truncate font-600 text-ink">{d.filename}</span>
                        </div>
                      </td>
                      <td className="px-3">
                        {d.supplier_name ? (
                          <button onClick={() => setEdit({ doc: d, supplier: sup })}
                            className="group inline-flex items-center gap-1.5 text-left font-600 text-ink hover:text-gold-soft" title="Edit supplier details">
                            <span className="truncate">{d.supplier_name}</span>
                            <Pencil className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-100" />
                          </button>
                        ) : (
                          <button onClick={() => setEdit({ doc: d, supplier: null })}
                            className="inline-flex items-center gap-1 text-xs font-600 text-grape-soft hover:underline" title="Attach a supplier to this sheet">
                            <Plus className="h-3 w-3" /> add supplier
                          </button>
                        )}
                      </td>
                      <td className="px-3 text-xs">
                        {sup?.email ? <span className="flex items-center gap-1 text-ink-soft"><Mail className="h-3 w-3 text-emerald-soft" /> {sup.email}</span>
                          : <button onClick={() => setEdit({ doc: d, supplier: sup })} className="flex items-center gap-1 text-warn hover:underline" title="Add a contact email"><AlertCircle className="h-3 w-3" /> add email</button>}
                      </td>
                      <td className="px-3 text-xs text-ink-soft">{sup?.location ?? <span className="text-ink-faint">—</span>}</td>
                      <td className="px-3 font-mono text-ink-soft">{d.rows_extracted}</td>
                      <td className="px-3"><StatusBadge status={d.status} /></td>
                      <td className="px-3 text-ink-faint">{formatRelativeDate(d.uploaded_at)}</td>
                      <td className="px-3">
                        <div className="flex items-center justify-end gap-1.5">
                          <Link to={`/catalog?doc=${d.document_id}`} className="btn-ghost !py-1.5 text-xs"><Boxes className="h-3.5 w-3.5" /> Catalogue</Link>
                          <button
                            onClick={() => { if (confirm(`Remove "${d.filename}" from upload history? Your enriched catalogue products are kept.`)) del.mutate(d.document_id); }}
                            disabled={del.isPending}
                            className="grid h-8 w-8 place-items-center rounded-lg border border-line text-ink-faint transition-colors hover:border-danger/50 hover:text-danger"
                            title="Delete this sheet">
                            {del.isPending && del.variables === d.document_id ? <Spinner className="h-3.5 w-3.5" /> : <Trash2 className="h-3.5 w-3.5" />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <button onClick={() => docs.refetch()} className="btn-ghost mt-4 !py-2"><RefreshCw className="h-4 w-4" /> Refresh</button>
      </Card>

      {edit && (
        <SupplierEditModal
          supplier={edit.supplier}
          presetName={edit.supplier ? undefined : (edit.doc.supplier_name ?? undefined)}
          onClose={() => setEdit(null)}
          onSaved={(s) => link.mutate({ docId: edit.doc.document_id, s })}
        />
      )}
    </div>
  );
}
