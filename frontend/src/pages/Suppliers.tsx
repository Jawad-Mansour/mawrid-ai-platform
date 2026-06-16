// Feature: Supplier Intelligence — list, add, score & compare
import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Users, Plus, BarChart3, Mail, Phone, X, Trophy } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { Card, SectionTitle, Loading, EmptyState } from "@/components/ui";
import type { Supplier } from "@/lib/types";

function asList(d: unknown): Supplier[] {
  if (Array.isArray(d)) return d as Supplier[];
  if (d && typeof d === "object" && Array.isArray((d as any).suppliers)) return (d as any).suppliers;
  return [];
}
function scoreOf(d: any): number {
  if (typeof d === "number") return d;
  return Number(d?.score ?? d?.value ?? d?.supplier_score ?? 0);
}
function tone(s: number) {
  return s >= 80 ? "bg-emerald" : s >= 60 ? "bg-gold" : s >= 40 ? "bg-warn" : "bg-danger";
}

export function Suppliers() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", phone: "", language: "en", currency: "USD" });

  const list = useQuery({ queryKey: ["suppliers"], queryFn: () => apiGet<unknown>("/suppliers") });
  const suppliers = useMemo(() => asList(list.data), [list.data]);

  const create = useMutation({
    mutationFn: () => apiPost("/suppliers", { ...form, email: form.email || null, phone: form.phone || null }),
    onSuccess: () => {
      toast.success("Supplier added");
      setAdding(false);
      setForm({ name: "", email: "", phone: "", language: "en", currency: "USD" });
      qc.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (e) => toast.error(apiErr(e, "Could not add supplier")),
  });

  // fetch scores only for selected suppliers (comparison)
  const scoreQueries = useQueries({
    queries: selected.map((id) => ({
      queryKey: ["supplier-score", id],
      queryFn: () => apiGet<any>(`/suppliers/${id}/score`),
    })),
  });

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length >= 3 ? s : [...s, id]));

  const compare = selected.map((id, i) => {
    const sup = suppliers.find((s) => s.supplier_id === id);
    const score = scoreQueries[i]?.data ? scoreOf(scoreQueries[i].data) : null;
    return { id, name: sup?.name ?? id.slice(0, 8), score, loading: scoreQueries[i]?.isLoading };
  });
  const best = compare.reduce<{ id: string; score: number } | null>((acc, c) => (c.score != null && (!acc || c.score > acc.score) ? { id: c.id, score: c.score } : acc), null);

  return (
    <div className="space-y-6">
      <SectionTitle title="Suppliers" subtitle="Scored by delivery reliability, price consistency & catalog completeness."
        right={<button className="btn-gold !py-2" onClick={() => setAdding((a) => !a)}><Plus className="h-4 w-4" /> Add supplier</button>} />

      {adding && (
        <Card>
          <SectionTitle title="New supplier" />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div><label className="label">Name</label><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Acme Supplies" /></div>
            <div><label className="label">Email</label><input className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="sales@acme.com" /></div>
            <div><label className="label">Phone</label><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+961…" /></div>
            <div><label className="label">Language</label>
              <select className="input" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
                <option value="en">English</option><option value="fr">French</option><option value="ar">Arabic</option>
              </select>
            </div>
            <div><label className="label">Currency</label>
              <select className="input" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
                <option>USD</option><option>EUR</option><option>LBP</option>
              </select>
            </div>
          </div>
          <button className="btn-gold mt-4" disabled={!form.name || create.isPending} onClick={() => create.mutate()}>Save supplier</button>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <SectionTitle title="Directory" subtitle="Select up to 3 to compare →" />
            {list.isLoading ? <Loading /> : suppliers.length === 0 ? (
              <EmptyState icon={<Users className="h-8 w-8" />} title="No suppliers yet" hint="Add your first supplier to start scoring and comparing." />
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {suppliers.map((s) => {
                  const on = selected.includes(s.supplier_id);
                  return (
                    <button key={s.supplier_id} onClick={() => toggle(s.supplier_id)}
                      className={`card p-4 text-left transition-all ${on ? "ring-1 ring-gold/50 shadow-glow" : "hover:bg-white/[0.04]"}`}>
                      <div className="flex items-center justify-between">
                        <span className="truncate font-700 text-ink">{s.name}</span>
                        <span className={`grid h-5 w-5 place-items-center rounded-md border ${on ? "border-gold bg-gold text-bg" : "border-line"}`}>
                          {on && <BarChart3 className="h-3 w-3" />}
                        </span>
                      </div>
                      <div className="mt-2 space-y-1 text-xs text-ink-faint">
                        {s.email && <div className="flex items-center gap-1.5"><Mail className="h-3 w-3" /> {s.email}</div>}
                        {s.phone && <div className="flex items-center gap-1.5"><Phone className="h-3 w-3" /> {s.phone}</div>}
                        <div className="flex gap-2 pt-1">
                          <span className="chip border-line bg-white/[0.02] uppercase">{s.language ?? "en"}</span>
                          <span className="chip border-line bg-white/[0.02]">{s.currency ?? "USD"}</span>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </Card>
        </div>

        {/* comparison */}
        <div>
          <Card>
            <SectionTitle title="Comparison" subtitle={selected.length ? `${selected.length} selected` : "Pick suppliers to compare"} />
            {selected.length === 0 ? (
              <EmptyState icon={<BarChart3 className="h-8 w-8" />} title="Nothing selected" hint="Choose up to 3 suppliers from the directory." />
            ) : (
              <div className="space-y-4">
                {compare.map((c) => (
                  <div key={c.id}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="flex items-center gap-1.5 font-600 text-ink">
                        {best?.id === c.id && <Trophy className="h-3.5 w-3.5 text-gold-soft" />}{c.name}
                      </span>
                      <button onClick={() => toggle(c.id)} className="text-ink-faint hover:text-danger"><X className="h-3.5 w-3.5" /></button>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-white/10">
                        <div className={`h-full rounded-full transition-all duration-500 ${c.score != null ? tone(c.score) : "bg-white/10"}`} style={{ width: `${c.score ?? 0}%` }} />
                      </div>
                      <span className="w-12 text-right font-mono text-sm text-ink">{c.loading ? "…" : c.score != null ? c.score.toFixed(0) : "—"}</span>
                    </div>
                  </div>
                ))}
                <p className="pt-2 text-xs text-ink-faint">Scores 0–100 from the Ridge supplier model (delivery reliability, damage rate, price vs market, responsiveness, data completeness).</p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
