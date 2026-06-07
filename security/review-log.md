# Review Log

Append one dated entry per review run. Newest first. Keeps a history of *how the posture
changed* over time, independent of the per-finding tracker.

---

## 2026-06-07 — Remediation: SEC-001 (critical) + SEC-002 (high)

- **Worked the one critical end-to-end** (analyze → plan → dependency map → fix → re-check → verify).
- **Closed:** cross-tenant `SOLVER_GITHUB_TOKEN` theft (stripped from `.git/config` during the untrusted run + pre-push secret-scan gate) and the trivial `node -e` RCE (removed from the agent allowlist + explicit deny). Added nonce-fenced untrusted-data separation in the Solver prompt, C0 control-char input hardening on issue title/description, and an `always()` credentials-wipe step.
- **Files:** `.github/workflows/solver-agent.yml`, `agents/Solver - Issues/{repo.py,claim_issue.py}`, `backend/auth_service/models/schemas.py`, + tests (`tests/test_repo.py`, `tests/test_claim_issue.py`, `backend/.../test_issue_schema.py`).
- **Dependency re-check:** Solver pipeline (claim → clone → run → finalize/push) preserved — clone/fetch unchanged, push re-auths `origin` transiently, finalize signature unchanged, agent retains lint/typecheck/test. Backend issue-creation flow unchanged behaviourally. No frontend/scraper/connector code touched.
- **Verification:** 29 Solver-agent tests + 436 backend unit tests green; ruff/black/yaml hooks pass.
- **Residual filed as `SEC-056` (high):** OAuth-token exfil via the agent's remaining `npm run` execution; needs egress isolation **or** removing agent command execution (security-vs-capability decision).
- **SEC-056 — chosen control implemented (egress isolation):** added `step-security/harden-runner` (v2.19.4, SHA-pinned) as the first Solver job step in `block` mode with an exact `allowed-endpoints` allowlist, so an injected agent cannot exfiltrate the Claude OAuth token to any non-allowlisted host. Added a `workflow_dispatch` `egress_policy` input (`block` default, `audit` for a one-off validation run). Workflow YAML validated. **SEC-001/SEC-002/SEC-056 stay `in-progress` pending one `egress_policy=audit` run** to confirm the allowlist is complete, then they flip to `fixed`.

## 2026-06-07 — Baseline full review

- **Method:** 14-dimension multi-agent workflow (find → adversarial verification → synthesize), 84 agents.
- **Scope:** full codebase — frontend (incl. embeddable booking widget), backend (15 routers, 30+ services, core auth/session/limiter), 26 SQL migrations, 8 GitHub Actions workflows, 4 AI agents, the scraper, dependencies, and live Supabase + Vercel state via MCP.
- **Live MCP state pulled:** Supabase security advisors on `xeluydwpgiddbamysgyu` (RLS-disabled `slack_processed_events`, `SECURITY DEFINER` view `tenant_rls_status`, anon/authenticated-executable `claim_*_solver_issue` RPCs, mutable function search_path, leaked-password protection disabled); Vercel project `cms-backend-roman` confirmed.
- **Result:** 55 confirmed findings (1 critical, 3 high, 10 medium, 31 low, 10 info); 14 candidates adversarially dismissed as false positives (see [`dismissed.md`](./dismissed.md)).
- **Headline:** `SEC-001` critical — client issue text → prompt-injection → RCE on the Solver CI runner with live write tokens. Dominant theme: the agentic/CI automation layer + public Supabase `anon` surface, not the internet-facing edges.
- **Status:** baseline — all findings `open`, none fixed yet.
- **Notes / gaps:** Vercel `list_projects` returned empty for the team scope (project reachable directly via `get_project`); frontend project env-scoping reviewed from repo config. The prior 109-finding audit (`docs/superpowers/specs/2026-05-07-security-audit.md`) predates the booking/multi-language/scraper/marketing code, which was the newly-audited surface here.

<!-- Next entry template:

## YYYY-MM-DD — Weekly scheduled review
- Method / scope:
- Since last review (new code scanned):
- New findings: SEC-NNN …
- Status changes: SEC-NNN open→fixed (commit …), …
- MCP state deltas (advisors resolved/new):
- Headline + remaining top risks:
-->
