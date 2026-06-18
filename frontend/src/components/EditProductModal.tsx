// Feature: Catalog — human edit of a product (fill/fix image, description, specs, price).
// API:     PATCH /catalog/products/{id}
import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { X, Plus, Trash2, ImageOff, Save, UploadCloud, Link2 } from "lucide-react";
import { toast } from "sonner";
import { apiPatch, apiErr, apiUpload } from "@/lib/api";
import { Spinner } from "@/components/ui";
import type { Product } from "@/lib/types";

export function EditProductModal({ product, onClose }: { product: Product; onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState(product.product_name);
  const [image, setImage] = useState(product.image_url ?? "");
  const [description, setDescription] = useState(product.description ?? "");
  const [price, setPrice] = useState(product.price != null ? String(product.price) : "");
  const [currency, setCurrency] = useState(product.currency ?? "USD");
  const [specs, setSpecs] = useState<[string, string][]>(Object.entries(product.specifications ?? {}).map(([k, v]) => [k, String(v)]));
  const [imgOk, setImgOk] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [showUrl, setShowUrl] = useState(false);
  const [urlEdited, setUrlEdited] = useState(false); // only PATCH image_url if the user typed one
  const fileRef = useRef<HTMLInputElement>(null);

  async function uploadImage(file: File) {
    if (!file.type.startsWith("image/")) { toast.error("Please choose an image file"); return; }
    setUploading(true);
    try {
      const card = await apiUpload<Product>(`/catalog/products/${product.product_id}/image`, file);
      setImage(card.image_url ?? "");
      setImgOk(true);
      qc.invalidateQueries({ queryKey: ["catalog"] });
      toast.success("Image updated");
    } catch (e) {
      toast.error(apiErr(e, "Upload failed"));
    } finally {
      setUploading(false);
    }
  }

  const save = useMutation({
    mutationFn: () =>
      apiPatch(`/catalog/products/${product.product_id}`, {
        product_name: name,
        // uploaded images are already saved server-side (and their presigned URL
        // expires) — only send image_url when the user pasted one manually.
        ...(urlEdited ? { image_url: image || null } : {}),
        description: description || null,
        specifications: Object.fromEntries(specs.filter(([k]) => k.trim())),
        retail_price: price ? Number(price) : null,
        currency,
      }),
    onSuccess: () => { toast.success("Product updated"); qc.invalidateQueries({ queryKey: ["catalog"] }); onClose(); },
    onError: (e) => toast.error(apiErr(e, "Save failed")),
  });

  return (
    <AnimatePresence>
      <motion.div className="fixed inset-0 z-[90] grid place-items-center bg-black/60 p-4 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
        <motion.div
          className="card relative max-h-[90vh] w-full max-w-2xl overflow-y-auto p-6"
          initial={{ scale: 0.96, y: 16, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ scale: 0.96, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <button onClick={onClose} className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-lg bg-black/20 text-ink hover:bg-black/40"><X className="h-4 w-4" /></button>
          <h2 className="mb-1 text-lg font-800 text-ink">Edit product</h2>
          <p className="mb-5 text-sm text-ink-soft">Fill in anything the AI missed — the image, description or specs.</p>

          <div className="grid gap-5 sm:grid-cols-[180px_1fr]">
            {/* image: drop / browse / url */}
            <div>
              <div
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files?.[0]; if (f) uploadImage(f); }}
                onClick={() => fileRef.current?.click()}
                title="Drop an image, or click to browse"
                className={`relative grid aspect-square cursor-pointer place-items-center overflow-hidden rounded-xl border-2 border-dashed transition-colors ${dragging ? "border-gold bg-gold/10" : "border-line bg-white"}`}
              >
                {uploading ? (
                  <div className="flex flex-col items-center gap-2 text-ink-soft"><Spinner className="h-6 w-6" /><span className="text-[11px]">Uploading…</span></div>
                ) : image && imgOk ? (
                  <img src={image} alt="" className="h-full w-full object-contain p-2" onError={() => setImgOk(false)} />
                ) : (
                  <div className="flex flex-col items-center gap-1.5 text-ink-faint/70"><UploadCloud className="h-7 w-7" /><span className="px-2 text-center text-[11px]">Drop image or click to browse</span></div>
                )}
                {image && imgOk && !uploading && (
                  <span className="absolute bottom-1 left-1/2 -translate-x-1/2 rounded-md bg-black/55 px-2 py-0.5 text-[10px] text-white">Click to replace</span>
                )}
              </div>
              <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadImage(f); e.target.value = ""; }} />
              <div className="mt-2 flex gap-2">
                <button type="button" onClick={() => fileRef.current?.click()} className="btn-ghost flex-1 !py-1.5 text-xs"><UploadCloud className="h-3.5 w-3.5" /> Browse</button>
                <button type="button" onClick={() => setShowUrl((s) => !s)} title="Paste an image URL" className={`grid h-8 w-9 place-items-center rounded-xl border text-xs ${showUrl ? "border-gold/50 bg-gold/10 text-gold-soft" : "border-line text-ink-soft hover:text-ink"}`}><Link2 className="h-3.5 w-3.5" /></button>
              </div>
              {showUrl && (
                <input className="input mt-2 text-xs" placeholder="https://…/image.jpg" value={image} onChange={(e) => { setImage(e.target.value); setImgOk(true); setUrlEdited(true); }} />
              )}
            </div>

            <div className="space-y-3">
              <div><label className="label">Product name</label><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="label">Price</label><input className="input" type="number" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="0.00" /></div>
                <div><label className="label">Currency</label>
                  <select className="input" value={currency} onChange={(e) => setCurrency(e.target.value)}><option>USD</option><option>EUR</option><option>LBP</option></select>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4"><label className="label">Description</label>
            <textarea className="input min-h-[120px] resize-y" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Full product description (Markdown supported)…" />
          </div>

          <div className="mt-4">
            <div className="mb-1.5 flex items-center justify-between">
              <label className="label !mb-0">Specifications</label>
              <button onClick={() => setSpecs((s) => [...s, ["", ""]])} className="chip border-line bg-white/[0.03] text-ink-soft hover:text-ink"><Plus className="h-3 w-3" /> Add</button>
            </div>
            <div className="space-y-2">
              {specs.map(([k, v], i) => (
                <div key={i} className="flex gap-2">
                  <input className="input flex-1" placeholder="Spec name" value={k} onChange={(e) => setSpecs((s) => s.map((row, j) => (j === i ? [e.target.value, row[1]] : row)))} />
                  <input className="input flex-1" placeholder="Value" value={v} onChange={(e) => setSpecs((s) => s.map((row, j) => (j === i ? [row[0], e.target.value] : row)))} />
                  <button onClick={() => setSpecs((s) => s.filter((_, j) => j !== i))} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-line text-ink-faint hover:text-danger"><Trash2 className="h-4 w-4" /></button>
                </div>
              ))}
              {specs.length === 0 && <p className="text-xs text-ink-faint">No specifications yet — add some.</p>}
            </div>
          </div>

          <div className="mt-6 flex justify-end gap-3">
            <button onClick={onClose} className="btn-ghost">Cancel</button>
            <button onClick={() => save.mutate()} disabled={save.isPending} className="btn-gold">{save.isPending ? <Spinner className="h-4 w-4" /> : <Save className="h-4 w-4" />} Save changes</button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
