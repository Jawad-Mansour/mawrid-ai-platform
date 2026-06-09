// Feature: HITL Approval Center
// Layer:   Hook
// Purpose: Custom React hook for HITL queue management. Fetches pending actions,
//          provides approve/reject/edit mutations with optimistic updates,
//          and handles keyboard shortcut registration (A, R, E, ↑↓, Esc, Enter).
// API:     GET /api/v1/hitl, POST /api/v1/hitl/{id}/approve,
//          POST /api/v1/hitl/{id}/reject, PATCH /api/v1/hitl/{id}/edit

export function useHITLQueue() {
  return { actions: [], approve: () => {}, reject: () => {}, edit: () => {} };
}
