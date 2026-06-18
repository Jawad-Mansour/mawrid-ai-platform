// Feature: Inventory — Demand Signals (coming soon). Future demand-aware restocking.
import { ComingSoon } from "@/components/ComingSoon";

export function Demand() {
  return (
    <ComingSoon
      title="Demand Signals"
      subtitle="Smarter restocking that goes beyond a simple quantity threshold."
      tagline="Restock based on real demand — not just what's left on the shelf"
      points={[
        { label: "Sales velocity", detail: "How fast each product is selling, so fast-movers reorder sooner." },
        { label: "Time-to-sell", detail: "How long stock typically takes to clear — avoid over- and under-ordering." },
        { label: "Customer interest", detail: "Views, searches and add-to-cart signals from the storefront." },
        { label: "Seasonality & need", detail: "Demand trends per category to time orders with the supplier's lead time." },
      ]}
    />
  );
}
