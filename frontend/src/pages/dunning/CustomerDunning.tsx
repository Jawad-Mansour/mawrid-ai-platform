// Feature: Financial — Customer Dunning (coming soon). B2C/receivables collections.
import { ComingSoon } from "@/components/ComingSoon";

export function CustomerDunning() {
  return (
    <ComingSoon
      title="Customer Dunning"
      subtitle="Collecting money owed to you by your store customers."
      tagline="Automated, tone-aware collections for your customers"
      points={[
        { label: "B2C Collections", detail: "Day 3 gentle + payment link → Day 7 firm → Day 14 final, by email/SMS." },
        { label: "B2B Receivables", detail: "Wholesale clients: Day 7 / 14 / 21 escalation, segment-aware tone." },
        { label: "ML tone classifier", detail: "Gentle / neutral / firm chosen from segment, history & overdue amount." },
        { label: "Auto-stop on payment", detail: "Any confirmed payment immediately halts that invoice's sequence." },
      ]}
    />
  );
}
