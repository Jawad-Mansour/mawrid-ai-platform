Show which checklist items are done and pending for the current implementation phase.

**Step 1** — Read `CLAUDE.md` at the project root. Find the Phase Progress table. Identify the current phase as the first ⬜ Pending entry that has sub-phases not yet complete.

**Step 2** — Read the corresponding phase section in `resources/plan/plan.md`. Collect every checklist item (`- [ ]` or `- [x]`) in that phase.

**Step 3** — For each checklist item, determine its actual status by inspecting the codebase:
- File to create: use `Glob` or `Read` to check existence
- Test to pass: run `uv run pytest backend/tests/unit/ -q` or `uv run pytest backend/tests/integration/ -q` (unit tests only unless Docker is up)
- Command to run manually: state it clearly so the user can run it

**Step 4** — Print the phase summary in this format:

```
## Phase X — <Name>

### Done ✅
- Item description [FILE: backend/app/core/...]

### Pending ⬜
- Item description [FILE: backend/app/core/... — needs to be created]
- Item description [TEST: uv run pytest backend/tests/unit/test_...]

### Blocked 🔴
- Any item that cannot proceed until a dependency completes
  (state what it's blocked on)

### Next action
<exact single command or file to create to unblock the phase>
```

**Step 5** — State clearly: "Ready to move to Phase X+1" or "X items remaining in Phase X before verify gate passes."

**Known phase states as of June 2026:**
- Phase 0 — Complete (training data scripts exist but data files not yet generated)
- Phase 1 — Complete
- Phase 2 — Complete (one gap: `/enrich` still runs synchronously — Phase 2.5 fix needed)
- Phase 3 — Not started (procurement API is empty stub)
- Phases 4–14 — Not started

Use this at the start of each work session to pick up exactly where we left off.
