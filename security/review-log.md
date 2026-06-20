# Review Log

Append one dated entry per review run. Newest first. Keeps a history of *how the posture
changed* over time, independent of the per-finding tracker.

---

## 2026-06-20 — Weekly full review (multi-agent, 14 dimensions)

- **Method:** ultra-effort Workflow — one finder agent per dimension → independent adversarial verification (default false-positive) → synthesis/reconciliation against `FINDINGS.md`. **43 agents**; 28 candidates, **26 survived verification, 2 dismissed**.
- **Live MCP state pulled:** Supabase `get_advisors` (security + performance) + `list_tables` + `list_extensions` on `xeluydwpgiddbamysgyu`. All 34 public tables RLS-enabled; the "RLS enabled, no policy" tables are deny-by-default (safe under the service-role model). No DB-side egress extensions installed (`http`/`pg_net`/`dblink`/`postgres_fdw` absent); `pg_cron` present. Remaining advisor WARNs unchanged (`extension_in_public` btree_gist; `auth_leaked_password_protection` — a Supabase-Auth feature, app uses custom auth). The new `seo_*` tables got their first DB-layer review (SEC-067).
- **New findings (12):** SEC-057 (med, booking `_cta_block` accent HTML-injection — missed SEC-045 sink), SEC-058 (med, booking write-path rate limits in-memory only), SEC-059 (med, marketing `/forms/contact` rate limit in-memory only), SEC-060 (low, `str.format` injection via tenant email copy), SEC-061 (info, bearer limiter process-local + 128-vs-192-bit docstring), SEC-062 (low, scraped URL href without scheme allowlist in admin), SEC-063 (low, Solver installs `@anthropic-ai/claude-code@latest` unpinned), SEC-064 (low, Solver action tags not SHA-pinned), SEC-065 (low, `promote.yml` gitleaks binary unverified), SEC-066 (low, admin-key `scopes` stored but never enforced), SEC-067 (info, `seo_*` default-ACL grants safe only via RLS), SEC-068 (low, per-account login lockout fails open on DB error).
- **Status changes:** SEC-050 open→**fixed** (backend now emits a strict edge CSP via `vercel.json`); SEC-007/SEC-025/SEC-026 (Dependabot) and SEC-023 (post-deploy-smoke) open→**obsolete** (infra removed 2026-06-09). Many open items re-confirmed still present (SEC-005/006/008/015/016/024/027/029/036/039/040/046/047/049) — re-verified, not re-IDed. SEC-006 broadened: `Write`/`Edit` are unrestricted during the untrusted Solver step, enabling a `package.json`-poisoning RCE via an allowlisted `npm run` — kept medium because harden-runner egress-block + credential teardown contain the blast radius.
- **Headline + top risks:** No new critical/high — the internet-facing edges held. The live class-of-risk is serverless rate-limiting on the unauthenticated booking write paths + the marketing contact form (Resend cost/DoS amplification), plus the one missed tenant→email HTML-injection sink. Everything else is operator/upstream-gated or defense-in-depth.
- **Automation update:** the weekly review now runs **Friday 00:00 Berlin** (cloud routine `trig_014vxyf4JSNpvucdjNKUSUgH`, repurposed from the old Saturday slot), and a new **Saturday 06:00 Berlin Solver routine** (`trig_01EsPjxVZGJciYRDYhZq8d9G`) auto-branches → plans → fixes (TDD) → tests → regression-tests dependents for open critical/high/medium, opening a PR per fix and auto-merging to `dev` only on all-green (never prod).
- **MCP gaps:** none in this local run. Cloud routine runs may lack the Supabase/Vercel MCP plugins — the prompts tell them to note it and continue with code review.

## 2026-06-08 — Notes: password policy + leaked-password protection

- **Leaked-password protection (advisor `auth_leaked_password_protection`) — deferred (accepted-risk).** It is a Supabase **Pro-plan** Auth feature (Authentication → Attack Protection) and the project is on the Free plan, so it cannot be enabled. Revisit on upgrade.
- **8-character password minimum — already enforced, no change needed.** Confirmed both client-side (`frontend/src/app/dashboard/account/page.tsx` change-password handler rejects `newPw.length < 8`) and server-side (`models/schemas.py` `ChangePasswordRequest.new_password = Field(min_length=8)`). The account page is the only new-password entry point on the frontend; the login form intentionally has no minimum (it submits an existing password).

## 2026-06-08 — Remediation: Postgres shared rate limiter + login lockout (SEC-010/011/012/020/030/034/035)

- **New shared store** — `migrations/2026_06_08_rate_limits.sql` adds a `rate_limits` table + atomic `rate_limit_hit/over/reset/gc` RPCs (SECURITY DEFINER, `search_path=''`, service_role-only — applied via MCP, validated live). `core/pg_rate_limit.py` wraps them (fail-open on DB error).
- **SEC-011 + SEC-020 (login lockout)** — `/auth/login` now refuses after 10 failed attempts per account / 15 min (shared across instances); cleared on success. 2 new tests.
- **SEC-010 (serverless reset)** — the highest-value limits now use the shared store: login lockout, the public booking reads, the multi-locale save (DeepL cost), and the public forms submission. Residual: a few low-risk slowapi limits (admin-bearer key attempts — infeasible to brute-force by entropy; change-password — authenticated) remain per-instance; acceptable.
- **SEC-012 + SEC-030 + SEC-035** — `_public_read_limit` dependency (120/min per IP, shared) on the public booking `config`/`services`/`availability`/`manage` GETs (expensive compute + manage-token enumeration).
- **SEC-034** — per-project limit (120/min) on multi-locale `save_service` to bound paid translation.
- **Verification:** full backend suite **446 passed, 5 skipped**; new lockout tests; live RPC behaviour validated (allow/allow/deny at limit).

## 2026-06-08 — Remediation: config/injection hardening (SEC-028/031/038/041)

- **SEC-028 (low)** — `admin_leads` list `sort` is now allowlisted to `_SORTABLE_COLUMNS` before `.order()` (falls back to `created_at`), closing the PostgREST column/filter injection.
- **SEC-031 + SEC-038 (low)** — `booking.py /cron/reminders` secret check uses `hmac.compare_digest` (constant-time).
- **SEC-041 (low)** — both public form 502 paths now log the upstream error server-side and return a generic message (no raw exception text to the submitter).
- **SEC-039 (low) → needs-decision** — credentialed CORS + broad `*.vercel.app` regex. NOT changed: the public booking widget on client `*.vercel.app` sites depends on that origin being allowed, and it's partly mitigated by the SameSite=Lax session cookie. Proper fix = split CORS (credentialed allowlist for the dashboard; credential-less wildcard for the public booking/forms endpoints). Flagged for a decision.
- **Verification:** full backend suite **444 passed, 5 skipped**; targeted admin-leads/booking/forms tests green.

## 2026-06-08 — Remediation: outbound-email HTML injection cluster (SEC-009/014/032/044/045)

- **SEC-009 + SEC-014 (medium)** — `forms.py _build_email_html` now `html.escape()`s the form field keys/values + `form_key` + `project_name` (closes stored XSS / HTML injection in the project owner's inbox).
- **SEC-032 (low)** — form `reply_to` is validated against a single-address regex (`_EMAIL_RE`); CRLF/comma header-injection and malformed values are dropped.
- **SEC-045 (low)** — `email_layout.header/footer` escape `business_name`/subtitle, `safe_url()` the logo + canonical URL, and restrict the tenant `accent` to a hex literal so it can't break out of the `style` attribute.
- **SEC-044 (low)** — `booking_i18n.tt()` HTML-escapes tenant `email_copy` overrides by default before placeholder substitution; the 4 plain-text subject sites opt out (`html_escape=False`). Built-in defaults (trusted, via `t()`) are untouched, so existing output is byte-identical.
- **Verification:** new `test_email_escaping.py` (6 tests: form key/value escaping, reply-to header-injection regex, malicious-brand neutralisation, default-brand no-op, tenant-override escaping vs. subject opt-out). Full backend suite **444 passed, 5 skipped**. DEFAULT_BRAND / default-copy output unchanged (existing 60 email/forms tests still green).

## 2026-06-08 — Remediation: booking cross-tenant IDOR (SEC-003 high + SEC-022 low)

- **SEC-003 (high)** — `create_appointment` now rejects a caller-supplied `resource_id` that isn't in `load_eligible_resources(tenant_id, service_id)` (tenant-scoped) → 422, before any insert. Closes the cross-tenant booking write + silent calendar-DoS.
- **SEC-022 (low)** — `create_service` / `patch_service` now validate every `resource_ids` entry against `list_resources(tenant_id)` via a shared `_validate_resource_ids` helper → 422 on a foreign resource. Covers all callers of `set_service_resources`.
- **Deps/services check:** public booking flow (`routers/booking.py`) was already safe — it ignores client `resource_id` and auto-picks via tenant-scoped `_free_resource_for`. DB-level defense-in-depth (composite tenant FK + tenant-scoped GiST exclusion) deferred: rewriting a live exclusion constraint is risky and the app-layer check fully closes the hole.
- **Verification:** 2 new tests (foreign-resource rejection for both appointment + service-link); full backend suite **438 passed, 5 skipped**.

## 2026-06-08 — Remediation batch: Supabase anon-surface cluster + SEC-001 marked fixed

- **SEC-001 / SEC-002 / SEC-056 → fixed** after the `egress_policy=audit` validation run came back clean; egress is now `block`.
- **Supabase anon-surface migration** `backend/migrations/2026_06_08_security_anon_surface_hardening.sql` (written + applied via MCP, validated against live):
  - **SEC-004 (high)** — `REVOKE EXECUTE` on `claim_next_solver_issue` / `claim_specific_solver_issue` from anon/authenticated/PUBLIC (service_role only); re-created both with `search_path=''` + schema-qualified refs; captured the previously-untracked `claim_specific` so repo == live.
  - **SEC-013 (medium) + SEC-033 (low)** — enabled RLS on `slack_processed_events` + revoked anon/authenticated grants.
  - **SEC-042 (low)** — `tenant_rls_status` view set to `security_invoker=true` + anon/authenticated revoked.
  - **SEC-053 (info)** — pinned `search_path` on the two `*_set_updated_at` trigger functions.
  - **SEC-054 (info) → accepted-risk** — inert tenant RLS owner policies (app uses service-role, not Supabase Auth JWTs); authZ is enforced in app code by design.
- **Verification:** live `has_function_privilege`/`pg_class` checks confirm anon/authenticated EXECUTE = false, service_role = true, RLS on, view `security_invoker=true`, search_path pinned. `get_advisors(security)` re-run: the `security_definer_view`, `rls_disabled_in_public`, anon/authenticated-executable-definer, and `function_search_path_mutable` lints are all **cleared**. Affected services unaffected: Solver claim RPC + Slack dedup both use the service-role client (bypasses RLS).
- **Remaining advisor WARNs (not in our findings / low value):** `extension_in_public` (btree_gist — risky to move; backs the booking exclusion constraint) and `auth_leaked_password_protection` (a Supabase Auth dashboard toggle — see SEC-04x / enable in dashboard).

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
