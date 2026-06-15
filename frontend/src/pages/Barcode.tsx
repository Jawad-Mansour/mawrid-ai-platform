// Feature: Barcode Live Lookup — @zxing camera scan -> product + stock
import { useEffect, useRef, useState } from "react";
import { BrowserMultiFormatReader, type IScannerControls } from "@zxing/browser";
import { ScanLine, Camera, CameraOff, PackageSearch, Boxes } from "lucide-react";
import { apiGet, apiErr } from "@/lib/api";
import { Card, SectionTitle, StatusBadge } from "@/components/ui";
import type { Product } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

export function Barcode() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const [scanning, setScanning] = useState(false);
  const [code, setCode] = useState("");
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState("");

  async function lookup(value: string) {
    if (!value) return;
    setError(""); setProduct(null);
    try {
      const p = await apiGet<Product>(`/catalog/barcode/${encodeURIComponent(value)}`);
      setProduct(p);
    } catch (e) {
      setError(apiErr(e, "No product found for that code"));
    }
  }

  async function start() {
    setError(""); setScanning(true);
    try {
      const reader = new BrowserMultiFormatReader();
      controlsRef.current = await reader.decodeFromVideoDevice(undefined, videoRef.current!, (result) => {
        if (result) {
          const text = result.getText();
          setCode(text);
          lookup(text);
          stop();
        }
      });
    } catch (e) {
      setError(apiErr(e, "Camera unavailable — check permissions"));
      setScanning(false);
    }
  }
  function stop() {
    controlsRef.current?.stop();
    controlsRef.current = null;
    setScanning(false);
  }
  useEffect(() => () => stop(), []);

  return (
    <div className="space-y-6">
      <SectionTitle title="Barcode Lookup" subtitle="Point your camera at any product for instant stock & pricing." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <div className="relative aspect-video overflow-hidden rounded-xl border border-line bg-black/40">
            <video ref={videoRef} className="h-full w-full object-cover" muted playsInline />
            {!scanning && (
              <div className="absolute inset-0 grid place-items-center text-ink-faint">
                <div className="text-center">
                  <ScanLine className="mx-auto h-12 w-12 text-gold/60" />
                  <p className="mt-2 text-sm">Camera idle</p>
                </div>
              </div>
            )}
            {scanning && <div className="pointer-events-none absolute left-1/2 top-1/2 h-28 w-64 -translate-x-1/2 -translate-y-1/2 rounded-lg border-2 border-gold/70 shadow-glow" />}
          </div>

          <div className="mt-4 flex gap-2">
            {scanning ? (
              <button className="btn-danger flex-1" onClick={stop}><CameraOff className="h-4 w-4" /> Stop</button>
            ) : (
              <button className="btn-gold flex-1" onClick={start}><Camera className="h-4 w-4" /> Start camera</button>
            )}
          </div>

          <div className="mt-4">
            <label className="label">Or enter a code manually</label>
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); lookup(code); }}>
              <input className="input font-mono" placeholder="EAN / UPC / SKU" value={code} onChange={(e) => setCode(e.target.value)} />
              <button className="btn-ghost" type="submit"><PackageSearch className="h-4 w-4" /></button>
            </form>
          </div>
        </Card>

        <Card>
          <SectionTitle title="Result" />
          {error && <div className="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger">{error}</div>}
          {!error && !product && (
            <div className="grid place-items-center py-16 text-center text-ink-faint">
              <Boxes className="h-10 w-10" />
              <p className="mt-2 text-sm">Scan or enter a code to see product details.</p>
            </div>
          )}
          {product && (
            <div className="space-y-4">
              <div>
                <div className="text-xl font-700 text-ink">{product.product_name}</div>
                <div className="font-mono text-xs text-ink-faint">{product.sku ?? product.barcode ?? "—"}</div>
              </div>
              {product.description && <p className="text-sm text-ink-soft">{product.description}</p>}
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-xl border border-line bg-white/[0.02] p-3 text-center">
                  <div className="metric-num text-xl">{product.qty_in_stock ?? "—"}</div>
                  <div className="text-xs text-ink-faint">In stock</div>
                </div>
                <div className="rounded-xl border border-line bg-white/[0.02] p-3 text-center">
                  <div className="metric-num text-xl">{product.retail_price != null ? formatCurrency(product.retail_price) : "—"}</div>
                  <div className="text-xs text-ink-faint">Retail</div>
                </div>
                <div className="grid place-items-center rounded-xl border border-line bg-white/[0.02] p-3">
                  <StatusBadge status={product.storefront_status} />
                </div>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
