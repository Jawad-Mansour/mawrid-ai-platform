// Feature: Suppliers — create / edit a supplier. Name·email·location are REQUIRED.
//          An "Auto-find location" agent resolves the real address + coordinates +
//          country phone code from OpenStreetMap. Reused from Suppliers, Upload History,
//          and the upload page.
// API:     POST/PUT /suppliers · POST /suppliers/resolve-location
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { X, Save, Building2, MapPin, Sparkles, Check } from "lucide-react";
import { toast } from "sonner";
import { apiPost, apiPut, apiErr } from "@/lib/api";
import { Spinner } from "@/components/ui";
import type { Supplier } from "@/lib/types";

const isEmail = (e: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e.trim());

export function SupplierEditModal({ supplier, presetName, onClose, onSaved }: {
  supplier: Supplier | null; presetName?: string; onClose: () => void; onSaved?: (s: Supplier) => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: supplier?.name ?? presetName ?? "",
    email: supplier?.email ?? "",
    phone: supplier?.phone ?? "",
    location: supplier?.location ?? "",
    description: supplier?.description ?? "",
    rating: supplier?.rating != null ? String(supplier.rating) : "",
    moq: supplier?.moq != null ? String(supplier.moq) : "",
    language: supplier?.language ?? "en",
    currency: supplier?.currency ?? "USD",
  });
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [resolved, setResolved] = useState(false);
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const valid = form.name.trim().length > 1 && isEmail(form.email) && form.location.trim().length > 0;

  interface ResolveResp { found: boolean; latitude?: number; longitude?: number; city?: string; country?: string; phone_code?: string; display_name?: string; website?: string | null; email?: string | null }
  const find = useMutation({
    // Resolve the COMPANY's real HQ from its name (GPT knows real brands), then geocode it.
    // The typed location is only a hint/fallback for companies the model doesn't know.
    mutationFn: () => apiPost<ResolveResp>("/suppliers/resolve-location", { name: form.name, place: form.location }),
    onSuccess: (r) => {
      if (!r.found) { toast.error("Couldn't resolve that company — add a rough 'City, Country' as a hint."); return; }
      setForm((f) => {
        // Replace the dial-code prefix with the resolved country's code, keeping any digits typed after it.
        const rest = (f.phone || "").replace(/^\+\d{1,4}\s*/, "").trim();
        return {
          ...f,
          location: [r.city, r.country].filter(Boolean).join(", ") || f.location,
          phone: r.phone_code ? `${r.phone_code} ${rest}`.trim() : f.phone,
          email: f.email.trim() ? f.email : (r.email ?? f.email), // fill a suggested email if empty
        };
      });
      if (r.latitude != null && r.longitude != null) setCoords({ lat: r.latitude, lon: r.longitude });
      setResolved(true);
      toast.success(`Found: ${r.display_name?.split(",").slice(0, 2).join(",") ?? "location"}`);
    },
    onError: (e) => toast.error(apiErr(e, "Lookup failed")),
  });
  const findEmail = useMutation({
    mutationFn: () => apiPost<ResolveResp>("/suppliers/resolve-location", { name: form.name, place: form.location }),
    onSuccess: (r) => {
      if (r.email) { set("email", r.email); toast.success(`Suggested: ${r.email}`); }
      else toast.error("Couldn't find an email — type one (you can use your own for testing).");
    },
    onError: (e) => toast.error(apiErr(e, "Lookup failed")),
  });

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        name: form.name, email: form.email || null, phone: form.phone || null,
        location: form.location || null, description: form.description || null,
        rating: form.rating ? Number(form.rating) : null, moq: form.moq ? Number(form.moq) : null,
        language: form.language, currency: form.currency,
      };
      if (coords) { body.latitude = coords.lat; body.longitude = coords.lon; body.region = "europe"; }
      return supplier ? apiPut<Supplier>(`/suppliers/${supplier.supplier_id}`, body) : apiPost<Supplier>("/suppliers", body);
    },
    onSuccess: (s) => {
      toast.success(supplier ? "Supplier updated" : "Supplier created");
      qc.invalidateQueries({ queryKey: ["suppliers"] });
      qc.invalidateQueries({ queryKey: ["documents"] });
      onSaved?.(s); onClose();
    },
    onError: (e) => toast.error(apiErr(e, "Save failed")),
  });

  return (
    <AnimatePresence>
      <motion.div className="fixed inset-0 z-[90] grid place-items-center bg-black/60 p-4 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
        <motion.div className="card relative max-h-[90vh] w-full max-w-lg overflow-y-auto p-6"
          initial={{ scale: 0.96, y: 16, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ scale: 0.96, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}>
          <button onClick={onClose} className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-lg bg-black/20 text-ink hover:bg-black/40"><X className="h-4 w-4" /></button>
          <h2 className="mb-1 flex items-center gap-2 text-lg font-800 text-ink"><Building2 className="h-5 w-5 text-gold-soft" /> {supplier ? "Edit supplier" : "Add supplier"}</h2>
          <p className="mb-5 text-sm text-ink-soft">Name, email and location are required. Use <b>Auto-find location</b> to fill the real place, map pin and phone code.</p>

          <div className="grid gap-3 sm:grid-cols-2">
            <div><label className="label">Name <span className="text-danger">*</span></label><input className="input" value={form.name} onChange={(e) => { set("name", e.target.value); setResolved(false); }} /></div>
            <div>
              <label className="label">Email <span className="text-danger">*</span></label>
              <div className="flex gap-2">
                <input className={`input flex-1 ${form.email && !isEmail(form.email) ? "!border-danger/60" : ""}`} type="email" value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="type one, or auto-find →" />
                <button type="button" onClick={() => findEmail.mutate()} disabled={findEmail.isPending || !form.name.trim()} className="btn-ghost shrink-0 !px-3 !py-2.5" title="Auto-find a contact email from the company">
                  {findEmail.isPending ? <Spinner className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <div className="sm:col-span-2">
              <label className="label">Location <span className="text-danger">*</span></label>
              <div className="flex gap-2">
                <input className="input flex-1" value={form.location} onChange={(e) => { set("location", e.target.value); setResolved(false); }} placeholder="City, Country (or a rough place)" />
                <button type="button" onClick={() => find.mutate()} disabled={find.isPending || (!form.location.trim() && !form.name.trim())} className="btn-ghost shrink-0 !py-2.5" title="Auto-find with OpenStreetMap">
                  {find.isPending ? <Spinner className="h-4 w-4" /> : resolved ? <Check className="h-4 w-4 text-emerald-soft" /> : <Sparkles className="h-4 w-4" />} Auto-find
                </button>
              </div>
              {coords && <p className="mt-1 flex items-center gap-1 text-[11px] text-emerald-soft"><MapPin className="h-3 w-3" /> Pinned at {coords.lat.toFixed(3)}, {coords.lon.toFixed(3)}</p>}
            </div>
            <div><label className="label">Phone</label><input className="input" value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="auto from country" /></div>
            <div><label className="label">Rating (0–5)</label><input className="input" type="number" min={0} max={5} step={0.5} value={form.rating} onChange={(e) => set("rating", e.target.value)} /></div>
            <div><label className="label">Min order qty (MOQ)</label><input className="input" type="number" min={0} value={form.moq} onChange={(e) => set("moq", e.target.value)} placeholder="e.g. 50" /></div>
            <div><label className="label">Language</label>
              <select className="input" value={form.language} onChange={(e) => set("language", e.target.value)}>
                <option value="en">English</option><option value="fr">French</option><option value="ar">Arabic</option>
              </select>
            </div>
            <div><label className="label">Currency</label>
              <select className="input" value={form.currency} onChange={(e) => set("currency", e.target.value)}>
                <option>USD</option><option>EUR</option><option>LBP</option>
              </select>
            </div>
          </div>
          <div className="mt-3"><label className="label">Notes</label>
            <textarea className="input min-h-[70px] resize-y" value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="What they supply, terms, contacts, notes…" />
          </div>

          {!valid && <p className="mt-3 text-xs text-warn">Fill name, a valid email and a location to save.</p>}
          <div className="mt-5 flex justify-end gap-3">
            <button onClick={onClose} className="btn-ghost">Cancel</button>
            <button onClick={() => save.mutate()} disabled={!valid || save.isPending} className="btn-gold">{save.isPending ? <Spinner className="h-4 w-4" /> : <Save className="h-4 w-4" />} Save</button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
