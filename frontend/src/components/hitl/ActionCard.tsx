// Feature: HITL Approval Center
// Layer:   Component / HITL
// Purpose: Individual HITL action card. Renders action_type-specific payload
//          (PO details, dunning message, supplier outreach draft, etc.).
//          Shows status badge, expiry countdown, and action buttons.
// API:     none (receives HITLAction prop from parent)

interface ActionCardProps {
  actionId: string;
  actionType: string;
  payload: Record<string, unknown>;
  status: string;
  expiresAt: string | null;
}

export function ActionCard({ actionId, actionType, payload, status, expiresAt }: ActionCardProps) {
  return <div>ActionCard: {actionType}</div>;
}
