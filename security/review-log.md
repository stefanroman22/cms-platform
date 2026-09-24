# Review Log

Append one dated entry per review run. Newest first. Keeps a history of *how the posture
changed* over time, independent of the per-finding tracker.

---

## 2026-09-24 — Weekly scheduled review

- **Method / scope:** 12-dimension multi-agent workflow (find → adversarial verification), **19 agents**, ~1.27M subagent tokens, run headless in the cloud. Every candidate finding was independently re-read by a skeptical verifier defaulting to false-positive. Prioritized (per methodology) IDOR/tenant-ownership → authN → admin gating → public tokens → XSS/SSRF/injection/CI/agents/DB/deps/rate-limit. Focus weighted to **code added since 2026-06-07** (highest-yield).
- **Since last review (new code scanned):** brand-new **SEO router** (`routers/seo.py`, `services/seo_repo.py`, `models/seo_schemas.py`, `translation/seo_translate.py`) + **SEO-GEO Optimizer agent** (`agents/SEO-GEO Optimizer/`); **per-staff dynamic booking** + booking blocks + service prices + customer-name snapshot (`booking_admin.py`, `booking_admin_repo.py`, `booking_repo.py`, migrations `2026_06_09_booking_blocks` / `2026_06_10_booking_service_price` / `2026_06_11_*` / `2026_06_08_booking_customer_name_snapshot`); **client-branded booking emails** with per-text color customization; **`admins see all projects`** in `projects.py`; **CMS-Connector branch-protection stripping** (`agents/CMS Connector - Website/github.py`, `vercel.py`) + `github_merge` PR fallback; **bearer-auth/service-key fix** (`deps.py`, `admin_keys.py`); **i18n middleware rewrite** (`frontend/src/middleware.ts`); **CI overhaul aftermath** (only `codeql.yml`/`promote.yml`/`solver-agent.yml` remain); `2026_06_14_seo_geo.sql` migration.
- **New findings (7, all adversarially confirmed; 0 dismissed this round):**
  - **SEC-058 (medium, xss-html)** — SEC-045 regression: raw tenant `accent_color` into visitor confirmation-email `<a>` style attrs (`booking_email.py:51,70`); `safe_hex` computed but not used at those sites.
  - **SEC-061 (medium, agents)** — SEO-GEO Optimizer feeds untrusted scraped competitor HTML into LLM analyst/planner/content prompts with no data/instruction separation, then autonomously publishes to the live client site (`prompts.py:58-76`); same systemic gap the Solver already fixed.
  - **SEC-057 (low, ratelimit-dos)** — per-account login-lockout DoS (`auth.py:78-96`).
  - **SEC-059 (low, deps)** — Solver installs Claude CLI from `@latest` (`solver-agent.yml:96`).
  - **SEC-060 (low, ci)** — promote gitleaks binary over curl, no checksum (`promote.yml:42`).
  - **SEC-062 (low, ratelimit-dos)** — `POST /seo/translate` unthrottled paid-DeepL amplification (`seo.py:247-251`).
  - **SEC-063 (low, ratelimit-dos)** — unauth public SEO reads unthrottled (`seo.py:168-181`).
- **Status changes:**
  - **Newly verified fixed:** SEC-046 (bearer→UserOut, `b6ca3bb`), SEC-047 (session rotation on password change, `90f576a`), SEC-050 (edge CSP in `backend/vercel.json`, `4bddb7f`).
  - **Obsolete → fixed-by-removal:** SEC-007, SEC-023, SEC-026 (workflows deleted in the 2026-06 CI overhaul). This clears the "reconcile at next review" note from 2026-06-09.
  - **Partially-fixed, kept open:** SEC-006 (force-push removed; auto-commit + blind single-approve promote remain, now *weakened* by the new Connector branch-protection strip), SEC-015 (expiry + read-time revocation now enforced; listing/rotation tooling absent), SEC-024 (promote/codeql SHA-pinned; `solver-agent.yml` still `@v4`/`@v5`).
  - **Still-present (broader):** SEC-025 — there is now **no `.github/dependabot.yml` at all**, so Dependabot covers nothing.
  - **Still-present, unchanged:** SEC-005, SEC-008, SEC-016, SEC-017, SEC-027, SEC-029, SEC-036, SEC-037, SEC-039 (needs-decision), SEC-040, SEC-048, SEC-049, SEC-052, SEC-055; SEC-054 remains accepted-risk. SEC-051 (historical DB password) **cannot-determine** from code — a `git filter-repo` history audit + rotation confirmation is still needed.
- **MCP state deltas:** **none pulled — Supabase and Vercel MCP servers were BOTH ABSENT in this headless cloud run** (only Gmail/Calendar/Drive/Kiwi/Slack/Spotify/Uber/github were connected). Live RLS/GRANT/advisor state on `xeluydwpgiddbamysgyu` and Vercel env-scoping/deployment-protection on `cms-backend-roman` could **not** be verified this week; all DB findings are from migration SQL only. **Carry-forward for the next run with MCP:** (a) re-run `get_advisors` security+performance; (b) confirm the new `seo_*` tables (`2026_06_14_seo_geo.sql:159-167`) have RLS enabled *and* — unlike the `rate_limits` / anon-surface-hardening migrations — they do **not** additionally `REVOKE`/`ALTER DEFAULT PRIVILEGES` against anon/authenticated (defense-in-depth only, since RLS-with-no-policy already denies, but worth aligning to the SEC-004 discipline); (c) confirm the booking `resource_id`/`service_id` FKs and the GiST no-overlap exclusion constraint (`2026_06_09_booking_blocks.sql`) are tenant-composite; (d) confirm `GITHUB_TOKEN`/`SOLVER_GITHUB_TOKEN` scope backing `ensure_branch_unprotected`.
- **Headline + top risks:** Posture **improved** — the sole critical (SEC-001) and all four highs (SEC-002/003/004/056) remain fixed, and this review found **no new critical or high**. The dominant theme is unchanged and now recurs in new code: **the agentic/automation layer lacks data/instruction separation and machine-checked diff/content gates** (SEC-061 repeats on the new SEO agent the exact pattern the Solver already hardened; SEC-006's blind-approve promote is now weakened by the Connector stripping GitHub branch protection). Second cluster: the **new SEO surface shipped without the rate-limiting / email-escaping discipline** the rest of the backend already adopted (SEC-058/062/063). Recommended focus: (1) nonce-fence + diff-gate the SEO-GEO publish path (SEC-061) and re-instate a diff/content gate before prod promote (SEC-006); (2) fix the SEC-045 regression in booking CTA emails (SEC-058); (3) add rate limits to the SEO router (SEC-062/063); (4) supply-chain pins (SEC-059/060/024) and re-introduce Dependabot (SEC-025).

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
