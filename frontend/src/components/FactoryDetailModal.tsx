// Feature: Supplier & Factory Network — full-detail popup for a factory/supplier card.
//          Shows every real field; for your own (saved/discovered) suppliers you can
//          upload a logo if the logo agent couldn't find one.
// API:     POST /suppliers/{id}/logo
import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { X, MapPin, Globe, Mail, Tag, Building2, Factory, GitCompare, Check, UploadCloud, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { apiUpload, apiErr } from "@/lib/api";
import { Spinner } from "@/components/ui";

export interface DetailPin {
  id: string; source: string; name: string; category: string; subcategory?: string | null;
  city?: string | null; country?: string | null; website?: string | null; logo_url?: string | null;
  email?: string | null; condition?: string | null; offering?: string | null;
}

export function FactoryDetailModal({ pin, color, selected, onClose, onToggle, onContact }: {
  pin: DetailPin; color: string; selected: boolean; onClose: () => void; onToggle: () => void; onContact: () => void;
}) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [logo, setLogo] = useState(pin.logo_url ?? "");
  const [uploading, setUploading] = useState(false);
  const [imgOk, setImgOk] = useState(true);
  const isSupplier = !pin.id.startsWith("ref_");
  const loc = [pin.city, pin.country].filter(Boolean).join(", ");

  async function uploadLogo(file: File) {
    if (!file.type.startsWith("image/")) { toast.error("Choose an image"); return; }
    setUploading(true);
    try {
      const r = await apiUpload<{ logo_url?: string }>(`/suppliers/${pin.id}/logo`, file);
      setLogo(r.logo_url ?? ""); setImgOk(true);
      qc.invalidateQueries({ queryKey: ["factories"] });
      toast.success("Logo updated");
    } catch (e) { toast.error(apiErr(e, "Upload failed")); }
    finally { setUploading(false); }
  }

  const rows: { label: string; value?: string | null; icon: typeof Tag }[] = [
    { label: "Category", value: [pin.category, pin.subcategory].filter(Boolean).join(" · "), icon: Tag },
    { label: "Provides", value: pin.offering, icon: Factory },
    { label: "Location", value: loc, icon: MapPin },
    { label: "Sells (condition)", value: pin.condition, icon: Tag },
    { label: "Email", value: pin.email, icon: Mail },
  ];

  return (
    <AnimatePresence>
      <motion.div className="fixed inset-0 z-[95] grid place-items-center bg-black/60 p-4 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
        <motion.div className="card relative w-full max-w-md overflow-hidden p-0"
          initial={{ scale: 0.92, y: 18, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ scale: 0.92, opacity: 0 }}
          transition={{ type: "spring", stiffness: 240, damping: 22 }} onClick={(e) => e.stopPropagation()}>
          <button onClick={onClose} className="absolute right-3 top-3 z-10 grid h-8 w-8 place-items-center rounded-lg bg-black/30 text-ink hover:bg-black/50"><X className="h-4 w-4" /></button>
          {/* header with glowing logo */}
          <div className="relative flex flex-col items-center gap-3 p-6" style={{ background: `radial-gradient(120% 80% at 50% 0%, ${color}22, transparent)` }}>
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadLogo(f); e.target.value = ""; }} />
            <motion.div initial={{ scale: 0.6 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 200, damping: 14 }}
              className="grid h-20 w-20 place-items-center overflow-hidden rounded-2xl bg-white" style={{ boxShadow: `0 0 26px ${color}66` }}>
              {uploading ? <Spinner className="h-6 w-6" /> : logo && imgOk ? <img src={logo} alt="" className="h-full w-full object-contain p-2" onError={() => setImgOk(false)} /> : <Factory className="h-8 w-8 text-ink-faint" />}
            </motion.div>
            <div className="text-center">
              <div className="text-lg font-800 text-ink">{pin.name}</div>
              <div className="mt-0.5 flex items-center justify-center gap-1 text-[11px] text-ink-faint">
                {pin.source === "curated" ? <Building2 className="h-3 w-3" /> : <MapPin className="h-3 w-3" />}
                <span className="capitalize">{pin.source === "curated" ? "Verified manufacturer" : pin.source === "discovered" ? "Discovered prospect" : "Your supplier"}</span>
              </div>
            </div>
            {isSupplier && (!logo || !imgOk) && (
              <button onClick={() => fileRef.current?.click()} className="chip border-gold/40 bg-gold/10 text-gold-soft"><UploadCloud className="h-3.5 w-3.5" /> Upload logo</button>
            )}
          </div>

          <div className="space-y-2 px-6 pb-4">
            {rows.filter((r) => r.value).map((r) => (
              <div key={r.label} className="flex items-start gap-2 text-sm">
                <r.icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-faint" />
                <span className="w-28 shrink-0 text-xs uppercase tracking-wide text-ink-faint">{r.label}</span>
                <span className="flex-1 text-ink">{r.value}</span>
              </div>
            ))}
            {pin.website && (
              <div className="flex items-center gap-2 text-sm"><Globe className="h-3.5 w-3.5 text-ink-faint" /><span className="w-28 shrink-0 text-xs uppercase tracking-wide text-ink-faint">Website</span>
                <a href={pin.website} target="_blank" rel="noreferrer" className="flex-1 truncate text-grape-soft hover:underline">{pin.website}</a></div>
            )}
          </div>

          <div className="flex gap-2 border-t border-line p-4">
            <button onClick={onToggle} className={`btn-ghost flex-1 ${selected ? "!border-gold/50 !text-gold-soft" : ""}`}>{selected ? <Check className="h-4 w-4" /> : <GitCompare className="h-4 w-4" />} {selected ? "Selected" : "Compare"}</button>
            <button onClick={onContact} className="btn-gold flex-1"><Mail className="h-4 w-4" /> Contact <ArrowRight className="h-3.5 w-3.5" /></button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
