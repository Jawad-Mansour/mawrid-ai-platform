// Feature: Catalog — human edit of a product (fill/fix image, description, specs, price).
// API:     PATCH /catalog/products/{id}
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { X, Plus, Trash2, ImageOff, Save } from "lucide-react";
import { toast } from "sonner";
import { apiPatch, apiErr } from "@/lib/api";
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

  const save = useMutation({
    mutationFn: () =>
      apiPatch(`/catalog/products/${product.product_id}`, {
        product_name: name,
        image_url: image || null,
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

          <div className="grid gap-5 sm:grid-cols-[160px_1fr]">
            {/* image preview + url */}
            <div>
              <div className="grid aspect-square place-items-center overflow-hidden rounded-xl border border-line bg-white">
                {image && imgOk ? <img src={image} alt="" className="h-full w-full object-contain p-2" onError={() => setImgOk(false)} /> : <ImageOff className="h-7 w-7 text-ink-faint/60" />}
              </div>
              <label className="label mt-2">Image URL</label>
              <input className="input" placeholder="https://…/image.jpg" value={image} onChange={(e) => { setImage(e.target.value); setImgOk(true); }} />
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
