// Feature: HITL Approval Center
// Layer:   Component / HITL
// Purpose: Main approval queue component. Renders list of pending HITL actions
//          with urgency sorting. Implements keyboard shortcuts:
//          A=Approve, R=Reject, E=Edit, ↑↓=navigate, Esc=cancel, Enter=save.
//          Supports all 14 action_types with type-specific payload renderers.
// API:     GET /api/v1/hitl?status=pending, POST /api/v1/hitl/{id}/approve,
//          POST /api/v1/hitl/{id}/reject, PATCH /api/v1/hitl/{id}/edit

export function ApprovalQueue() {
  return <div>ApprovalQueue</div>;
}
