Show current CI gate status across all 9 gates.

Run `git status` and `git log --oneline -5` to understand the current branch state, then check each gate:

**Gate 1 — ruff lint (every push)**
Run: `uv run ruff check .`
- [ ] Zero lint errors

**Gate 2 — mypy strict (every push)**
Run: `uv run mypy --strict .`
- [ ] Zero type errors

**Gate 3 — Unit tests (every push, < 3 min)**
Run: `uv run pytest tests/unit/ --tb=short -q`
- [ ] All pass
- [ ] Total runtime < 3 minutes
- [ ] LLM is mocked — no real API calls

**Gate 4 — Integration tests (PR to master)**
Run: `uv run pytest tests/integration/ --tb=short -q`
- [ ] All pass (requires real DB + Redis — run `docker compose up -d` first)

**Gate 5 — Cross-tenant red-team (PR to master)**
Run: `uv run pytest tests/integration/test_cross_tenant.py -v`
- [ ] 15/15 attack vectors blocked
- [ ] Zero cross-tenant leaks

**Gate 6 — Agent trajectory snapshots (PR to master)**
Run: `uv run pytest tests/integration/test_agent_snapshots.py -v`
- [ ] All 20 golden sequences match expected node paths

**Gate 7 — RAGAS eval (nightly only)**
Run: `uv run pytest tests/evals/test_rag_quality.py`
- [ ] All 4 metrics above thresholds in `backend/ml_config/eval_thresholds.yaml`
- [ ] NOTE: Uses real LLM calls — do NOT run on every push

**Gate 8 — Intent classifier F1 (nightly only)**
Run: `uv run pytest tests/evals/test_intent_classifier.py`
- [ ] Macro F1 ≥ 0.85 on held-out test set

**Gate 9 — Drift detection (nightly only)**
Run: `uv run pytest tests/evals/test_drift.py`
- [ ] PSI < 0.10 → normal
- [ ] PSI 0.10–0.20 → watch
- [ ] PSI ≥ 0.25 → alarm (CI fails)

**Security Checks (run on every PR)**
- [ ] No hardcoded secrets: `grep -r "password\s*=\s*['\"]" backend/app/` → zero results
- [ ] No raw SQL bypassing RLS: `grep -r "session.execute(text(" backend/app/` → only in migration files
- [ ] argon2id used for password hashing: `grep -r "bcrypt\|md5\|sha256.*password" backend/app/` → zero results
- [ ] JWT algorithm is RS256: `grep -r "HS256\|HS512" backend/app/` → zero results
- [ ] Webhook HMAC verification present: every webhook handler calls `verify_signature()` before processing
- [ ] CORS wildcard absent: `grep -r "allow_origins.*\*" backend/app/` → zero results
- [ ] Product hash uses SHA-256 with colon delimiter: check `core/catalog/services.py`

**Summary**
Report which gates are: ✅ PASS / ❌ FAIL / ⬜ NOT_YET_BUILT
Merge to master requires Gates 1–6 green on current commit + Gates 7–9 passed within 24h.
