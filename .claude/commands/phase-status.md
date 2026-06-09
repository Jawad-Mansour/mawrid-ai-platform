Show which checklist items are done and pending for the current implementation phase.

**Step 1** — Check if `CLAUDE.md` exists at the project root. If it does, read its Phase Progress table to identify the current phase (first ⬜ Pending entry). If it does not exist yet, read `resources/plan/plan.md` and find the first phase that still has unchecked `- [ ]` items — that is the current phase.

**Step 2** — Read the corresponding phase section in `resources/plan/plan.md`. Find every checklist item (`- [ ]` or `- [x]`) in that phase.

**Step 3** — For each checklist item, determine its actual status by checking the codebase:
- If it's a file to create: check if the file exists (`Glob` or `Read`)
- If it's a test to pass: run `uv run pytest <path> -q` if services are available
- If it's a command to run: report what the user needs to run manually

**Step 4** — Print the phase summary in this format:

```
## Phase X — <Name>

### Done ✅
- Item 1 description
- Item 2 description

### Pending ⬜
- Item 3 description  [FILE: backend/app/core/...]
- Item 4 description  [TEST: uv run pytest tests/unit/test_...]

### Blocked 🔴
- Any item that cannot proceed until another item completes

### Verify Command
<exact command to run to confirm this phase is complete>
```

**Step 5** — State clearly: "Ready to move to Phase X+1" or "X items remaining in Phase X."

Use this at the start of each work session to pick up exactly where we left off.
