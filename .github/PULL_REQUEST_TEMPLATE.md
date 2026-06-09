## What
Brief description of what this PR does.

## Why
Link the spec or issue (e.g. `specs/features/dunning.md`, closes #123).

## Checklist
- [ ] Tenant isolation: every new query is tenant-scoped (TenantRepository + RLS)
- [ ] No secrets committed (`.env.example` only, real values in Vault)
- [ ] HITL: any action that sends a message or contacts an external party creates a `hitl_actions` record
- [ ] Outbox: enrichment result + embedding event written atomically (one transaction)
- [ ] Specs updated if API contract or behavior changed
- [ ] Tests added or updated (unit for logic, integration for DB/Redis)
- [ ] CI green (all applicable gates pass)

## Risk
Anything reviewers should look at extra carefully (e.g. migration, auth change, payment path).
