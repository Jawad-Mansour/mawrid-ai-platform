// Feature: Catalog — product detail modal with enrichment sources + "ask the agent"
// API:     GET /catalog/products/{id} · POST /catalog/products/{id}/ask
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, ExternalLink, Sparkles, Send, ImageOff, Package, ShoppingBag, Check } from "lucide-react";
import { apiPost, apiErr } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Spinner, StatusBadge } from "@/components/ui";
import { useBasket } from "@/stores/basket";
import type { Product, AskProductResponse, SourceLink } from "@/lib/types";

export function ProductModal({ product, onClose }: { product: Product; onClose: () => void }) {
  const basket = useBasket();
  const inBasket = basket.has(product.product_id);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<AskProductResponse | null>(null);
  const [imgOk, setImgOk] = useState(true);
  const specs = Object.entries(product.specifications ?? {});

  async function ask() {
    if (!q.trim() || busy) return;
    setBusy(true);
    setAnswer(null);
    try {
      const r = await apiPost<AskProductResponse>(`/catalog/products/${product.product_id}/ask`, { question: q });
      setAnswer(r);
    } catch (e) {
      setAnswer({ product_id: product.product_id, answer: apiErr(e, "Could not reach the research agent."), sources: [] });
    } finally {
      setBusy(false);
    }
  }

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[80] grid place-items-center bg-black/60 p-4 backdrop-blur-sm"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="card relative max-h-[88vh] w-full max-w-3xl overflow-y-auto p-0"
          initial={{ scale: 0.96, y: 16, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ scale: 0.96, opacity: 0 }}
          transition={{ type: "spring", stiffness: 240, damping: 24 }}
          onClick={(e) => e.stopPropagation()}
        >
          <button onClick={onClose} className="absolute right-3 top-3 z-10 grid h-8 w-8 place-items-center rounded-lg bg-black/30 text-ink hover:bg-black/50">
            <X className="h-4 w-4" />
          </button>

          <div className="grid gap-0 sm:grid-cols-2">
            {/* image */}
            <div className="grid aspect-square place-items-center bg-white/[0.03] sm:rounded-l-2xl">
              {product.image_url && imgOk ? (
                <img src={product.image_url} alt={product.product_name} className="h-full w-full object-contain p-6" onError={() => setImgOk(false)} />
              ) : (
                <div className="flex flex-col items-center gap-2 text-ink-faint"><ImageOff className="h-10 w-10" /><span className="text-xs">No image found</span></div>
              )}
            </div>

            {/* header info */}
            <div className="p-5">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <StatusBadge status={product.enrichment_status} />
                {product.enrichment_source && <span className="chip border-line bg-white/[0.03] text-ink-soft">{product.enrichment_source}</span>}
                {product.enrichment_confidence && <span className="chip border-line bg-white/[0.03] text-ink-soft">{product.enrichment_confidence} confidence</span>}
              </div>
              <h2 className="text-xl font-800 leading-tight text-ink">{product.product_name}</h2>
              <div className="mt-1 font-mono text-xs text-ink-faint">{product.sku ?? "no sku"}{product.barcode ? ` · ${product.barcode}` : ""}</div>
              <div className="mt-3 flex items-baseline gap-3">
                {product.price != null && <span className="text-lg font-700 text-ink">{formatCurrency(product.price, product.currency ?? "USD")}</span>}
                <span className="flex items-center gap-1 text-xs text-ink-faint"><Package className="h-3.5 w-3.5" /> {product.qty_in_stock ?? 0} in stock</span>
              </div>
              <button
                onClick={() => basket.add(product)}
                className={`mt-4 w-full ${inBasket ? "btn-ghost" : "btn-gold"}`}
              >
                {inBasket ? <><Check className="h-4 w-4" /> Noted for order</> : <><ShoppingBag className="h-4 w-4" /> Note for order</>}
              </button>
            </div>
          </div>

          <div className="space-y-5 p-5 pt-0">
            {product.description && (
              <div>
                <div className="mb-1 text-xs font-600 uppercase tracking-wider text-ink-faint">Description</div>
                <p className="text-sm leading-relaxed text-ink-soft">{product.description}</p>
              </div>
            )}

            {specs.length > 0 && (
              <div>
                <div className="mb-2 text-xs font-600 uppercase tracking-wider text-ink-faint">Specifications</div>
                <div className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
                  {specs.map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-3 border-b border-line py-1 text-sm">
                      <span className="text-ink-faint">{k}</span>
                      <span className="text-right font-500 text-ink">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {product.source_urls && product.source_urls.length > 0 && (
              <div>
                <div className="mb-2 text-xs font-600 uppercase tracking-wider text-ink-faint">Sources</div>
                <div className="flex flex-wrap gap-2">
                  {product.source_urls.map((s: SourceLink, i) => (
                    <a key={i} href={s.url} target="_blank" rel="noreferrer" className="chip border-grape/30 bg-grape/10 text-grape-soft hover:bg-grape/20">
                      <ExternalLink className="h-3 w-3" /> {s.title}
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* ask the agent */}
            <div className="rounded-xl border border-gold/30 bg-gold/5 p-4">
              <div className="mb-2 flex items-center gap-2 text-sm font-600 text-ink"><Sparkles className="h-4 w-4 text-gold" /> Ask about this product</div>
              <form onSubmit={(e) => { e.preventDefault(); ask(); }} className="flex gap-2">
                <input className="input" placeholder="e.g. Is it compatible with macOS? What's the warranty?" value={q} onChange={(e) => setQ(e.target.value)} />
                <button type="submit" disabled={busy || !q.trim()} className="btn-gold !px-3.5">{busy ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />}</button>
              </form>
              {answer && (
                <div className="mt-3 rounded-lg bg-black/20 p-3 text-sm text-ink-soft">
                  <p className="whitespace-pre-wrap">{answer.answer}</p>
                  {answer.sources.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {answer.sources.map((s, i) => (
                        <a key={i} href={s.url} target="_blank" rel="noreferrer" className="chip border-line bg-white/[0.03] text-ink-faint hover:text-ink">
                          <ExternalLink className="h-3 w-3" /> {s.title}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
