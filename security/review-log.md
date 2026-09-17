# Review Log

Append one dated entry per review run. Newest first. Keeps a history of *how the posture
changed* over time, independent of the per-finding tracker.

---

## 2026-09-17 — Weekly scheduled review

- **Method / scope:** 14-dimension multi-agent Workflow (find → adversarial verification → synthesize),
  **34 agents**, 0 errors, ~1.9M subagent tokens. Reconciled all open/needs-decision/accepted-risk
  findings + ran one finder per dimension focused on the **37 commits since the 2026-06-07 baseline**.
- **Since last review (new code scanned):** the **SEO/GEO** feature (`routers/seo.py`,
  `services/seo_repo.py`, `models/seo_schemas.py`, `translation/seo_translate.py`,
  `migrations/2026_06_14_seo_geo.sql`, `agents/SEO-GEO Optimizer/`); **per-staff dynamic booking**
  (booking router/repos/availability/tenant + blocks/service-price/resource-image migrations);
  **branded booking emails** (per-text color customization, `email_layout.py`, `booking_email.py`,
  i18n copy overrides); **CMS Connector** branch-protection stripping + 429 backoff (`github.py`,
  `vercel.py`, `scan.py`); the **"admins see all projects"** change (`projects.py`); the **CI/CD
  overhaul** (deleted `ci.yml`/`e2e.yml`/`auto-merge-dev-to-master.yml`/`post-deploy-smoke.yml`/
  `scraper-ci.yml`/`dependabot-auto-merge.yml`; Dependabot disabled; new manual `promote.yml`);
  marketing i18n (EN/NL/RO).
- **New findings (8):** **SEC-057 (high)** CMS Connector cross-tenant admin write via prompt-injected
  `project_slug`; **SEC-058 (medium)** legacy unauth booking `/availability`+`/slots` no rate limit +
  unbounded range CPU DoS; **SEC-061 (medium)** `promote.yml` gitleaks binary no checksum in a
  privileged job; **SEC-059 (low)** SEO `/translate` no rate limit (paid DeepL); **SEC-060 (low)**
  `accent_color` unescaped in `_cta_block` (SEC-045 bypass); **SEC-062 (low)** `vercel.json` headers
  dropped by legacy `routes` schema; **SEC-063 (low)** SEO-GEO `render_check.fetch_raw` unsafe URL
  fetch (latent SSRF); **SEC-064 (info)** SEO tables omit anon/authenticated REVOKE.
- **Status changes:** SEC-046 → **fixed** (b6ca3bb — bearer path now returns `UserOut`);
  SEC-047 → **fixed** (fresh session minted post-password-change); SEC-007/023/026 → **obsolete**
  (files deleted in 7ae1b07); SEC-025 → **obsolete** (Dependabot disabled entirely — residual: no
  automated vuln bumps for any component); SEC-006 → materially mitigated (force-push removed, prod
  promote now manual) but kept **open** for the unreviewed auto-push to staging; SEC-024 → residual
  narrowed to `checkout@v4`/`setup-python@v5` in `solver-agent.yml` (scraper-ci deleted; harden-runner
  SHA-pinned). **SEC-050 correction:** its "edge config covers CSP" premise is **wrong** — see SEC-062
  (the `vercel.json` header block is inert under the legacy `routes` schema); kept open.
- **Regression check (Supabase anon surface):** re-read all migrations 2026_06_09 → 2026_06_14 —
  **no regression** of SEC-004/013/033/042/053. No `CREATE OR REPLACE` on the `claim_*` functions, no
  re-GRANT to anon/authenticated, no RLS disabled on the hardened tables. The four new `rate_limit_*`
  SECURITY DEFINER functions all pin `search_path=''`. SEC-054 (inert tenant RLS owner policies)
  confirmed still true — accepted-risk unchanged.
- **AuthZ posture on new code — clean.** Every new project-scoped endpoint proves ownership:
  `seo.py` applies `require_project_access` on all mutations; the `projects.py` admin-visibility change
  gates on server-side `is_admin` (non-admins still filter by `user_id`); `deps.py`
  `require_project_access` enforces `user_id == caller or is_admin`. Dimensions authz-idor, admin-priv,
  public-tokens, injection, and scraper returned **zero** new findings after adversarial verification.
- **MCP gaps:** Supabase (`get_advisors`, `list_tables`, `execute_sql`) and Vercel (`get_project`) MCP
  servers were **unavailable** in this headless cloud run (confirmed via tool search). DB/RLS/GRANT
  analysis is from the SQL migration files only; live advisors were not re-pulled and Vercel env/
  deployment-protection posture was reviewed from repo config (`vercel.json`, workflows). Recommend a
  local run with MCP to re-pull advisors and confirm the SEC-062 header behavior against the live edge.
- **Headline + remaining top risks:** the agentic/CI automation layer remains the dominant theme —
  SEC-057 (new high) is the clearest cross-tenant vector; the internet-facing app edges (auth, public
  booking/forms, PostgREST) stayed fail-closed with the new features. Remaining priority order:
  SEC-057 → SEC-058/SEC-061 → SEC-005/SEC-006/SEC-016 (agent hardening) → the low/info sweep.

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
