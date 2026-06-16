// Feature: Catalog Enrichment — Upload History: every supplier sheet uploaded.
// API:     GET /catalog/documents
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { FileSpreadsheet, UploadCloud, RefreshCw } from "lucide-react";
import { apiGet } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState, StatusBadge } from "@/components/ui";
import { formatRelativeDate } from "@/lib/utils";
import type { DocumentHistoryItem } from "@/lib/types";

function asList(d: unknown): DocumentHistoryItem[] {
  return Array.isArray(d) ? (d as DocumentHistoryItem[]) : [];
}

export function UploadHistory() {
  const docs = useQuery({ queryKey: ["documents"], queryFn: () => apiGet<unknown>("/catalog/documents"), refetchInterval: 10_000 });
  const list = asList(docs.data);

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
                  <th className="px-3 font-600">Rows</th>
                  <th className="px-3 font-600">Status</th>
                  <th className="px-3 font-600">Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {list.map((d) => (
                  <tr key={d.document_id} className="table-row">
                    <td className="py-3 pr-3">
                      <div className="flex items-center gap-2">
                        <FileSpreadsheet className="h-4 w-4 shrink-0 text-emerald-soft" />
                        <span className="truncate font-600 text-ink">{d.filename}</span>
                      </div>
                    </td>
                    <td className="px-3 font-mono text-ink-soft">{d.rows_extracted}</td>
                    <td className="px-3"><StatusBadge status={d.status} /></td>
                    <td className="px-3 text-ink-faint">{formatRelativeDate(d.uploaded_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <button onClick={() => docs.refetch()} className="btn-ghost mt-4 !py-2"><RefreshCw className="h-4 w-4" /> Refresh</button>
      </Card>
    </div>
  );
}
