# Security Findings — Live Tracker

**Last full review:** 2026-09-03 · **Reviewer:** multi-agent workflow (13-dimension finders + reconciliation, adversarial verification; 37 agents) · **Supabase:** xeluydwpgiddbamysgyu · **Confirmed:** 68 · **Dismissed (false-positive):** 17

> **2026-09-03 weekly review — headline.** No open **critical**. **12 new findings** (2 high, 3 medium,
> 6 low, 1 info), all concentrated in the code shipped since 2026-06-09: the new **SEO/GEO feature**
> (router/repo/migration) and especially the new **`agents/SEO-GEO Optimizer/`** agent. Top new risks:
> **SEC-058 (high)** — untrusted competitor/client site content flows into the SEO agent's LLM reasoning
> with **no data/instruction separation** while the orchestrator holds pre-authorized, never-pausing
> **service-role Supabase SQL + CMS-admin write** tools (the Solver's SEC-001/056 hardening was never
> applied here); and **SEC-057 (high)** — the agent's competitor-intel phase spec string-interpolates
> untrusted competitor text into a service-role `execute_sql` INSERT (**second-order SQL injection**,
> RLS-bypassing/cross-tenant worst case). Also **SEC-059/060 (medium)** — a regression of the SEC-045
> email-injection class: tenant `accent_color` is emitted **raw** into booking-email button `style`
> attributes in `_cta_block`/`_button` (the `header()`/`accent_rule()` paths were fixed, these new
> button helpers bypass `safe_hex`); and **SEC-061 (medium)** — the new `/seo/translate` endpoint
> re-opens the SEC-034 paid-DeepL amplification class with **no rate limit**. The new SEO DB tables were
> verified **correctly hardened** (RLS enabled, no anon policies/grants — mirrors booking). **MCP note:**
> the Supabase and Vercel MCP servers were **absent** in this headless run — DB posture was reviewed from
> the migration SQL as source of truth; live advisor/GRANT confirmation is deferred to a run with MCP.

> **Reconciliation 2026-09-03.** `SEC-046` (info) → **fixed** (bearer path now returns a proper user
> object at the dependency boundary). `SEC-007`, `SEC-023`, `SEC-025`, `SEC-026` → **obsolete** (the
> `dependabot-auto-merge.yml` / `post-deploy-smoke.yml` workflows and `.github/dependabot.yml` were
> deleted in the 2026-06-09 CI overhaul; Dependabot is off entirely — the residual "no automated dep
> updates" posture is now tracked as `SEC-068`). All other open findings re-verified **still-present**
> (`SEC-005/006/008/015/016/017/024/027/029/036/037/040/047/048/049/050/051/052/055`), `SEC-039`
> re-affirmed **needs-decision**, `SEC-054` re-affirmed **accepted-risk**. The prior remediation cluster
> (`SEC-001/002/003/004/009–014/018–022/028/030–035/038/041–045/053/056`) remains **fixed** — no
> regressions detected in the changed code (the new `seo_repo` mirrors the hardened booking scoping).

> **Remediation 2026-09-05 (Saturday automated solver).** Processed the 5 highest-priority open
> findings from this review (both highs + the three new mediums). **Fixed → dev:** `SEC-059` (PR #61),
> `SEC-060` (PR #62) — tenant `accent` now allowlisted via `safe_hex` in the booking-email button
> helpers; `SEC-061` (PR #63) — `/seo/translate` now rate-limited per project (SEC-034 parity). Each
> auto-merged to `dev` with full backend suite green (573 passed) + a vuln-driving regression test.
> **In-progress (PRs left OPEN for human review — they alter privileged SEO-GEO agent semantics):**
> `SEC-057` (PR #64) — competitor persistence moved off raw string-interpolated SQL onto deterministic,
> unit-tested `apply.build_competitor_insert_sql`/`sql_str` + phase-spec/AGENTS.md guards; `SEC-058`
> (PR #65) — scraped text now nonce-fenced with an `UNTRUSTED_DATA_POLICY` in the analyst/planner
> prompts (mirrors the Solver's SEC-001). Systemic follow-up for both: constrain the agent to a
> parameterized, `project_id`-scoped repo layer instead of raw service-role `execute_sql`, and gate any
> cross-project write. **Flagged for humans, NOT auto-fixed this run:** `SEC-005` — the real, live part
> (anon/authenticated EXECUTE on the `claim_*` RPCs) already has its REVOKE in
> `backend/migrations/2026_06_08_security_anon_surface_hardening.sql:94-97`; it needs **live MCP/GRANT
> verification against prod** (deferred here — no MCP, and prod DB changes are human-only). `SEC-006`
> (Solver diff-policy gate) and `SEC-008` (scraper hash-pinning) are deferred to next week (needing a
> design decision / lockfile generation, respectively). NB: `dev`'s own `security/` tree is the older
> **2026-06-20** lineage with different ID assignments; this tracker (the 2026-09-03 review branch) is
> authoritative, so the fix PRs deliberately do not edit dev's divergent tracker — these status rows are
> the canonical record and ride into `dev` when the review PR merges.

This table is the **source of truth for status**. Detail for each finding lives in [`findings/`](./findings/) by severity. IDs are stable and never reused (see [`methodology.md`](./methodology.md) §5–6). Status: `open` · `in-progress` · `fixed` · `accepted-risk` · `false-positive` · `wont-fix`.

> **Remediation 2026-06-07 — `SEC-001` (critical) + `SEC-002` + `SEC-056` (high): FIXED.** The full
> Solver hardening shipped (commits `fix(security): SEC-001` + `SEC-056`) and the egress allowlist was
> validated by a `workflow_dispatch` `egress_policy=audit` run (clean). Closed: cross-tenant
> `SOLVER_GITHUB_TOKEN` theft, the `node -e` RCE, prompt-injection break-out (nonce-fenced untrusted
> data), control-char input, and OAuth-token exfil (harden-runner egress block, now in `block` mode).
> Verified: 29 Solver-agent + 436 backend tests green.

> **Note 2026-06-09 — CI/CD overhaul.** The auto-gated pipeline was removed: deleted
> `ci.yml`, `e2e.yml`, `auto-merge-dev-to-master.yml`, `post-deploy-smoke.yml`,
> `scraper-ci.yml`, `dependabot-auto-merge.yml`, and Dependabot was disabled entirely.
> This obsoletes **SEC-007** (Dependabot auto-merge) and **SEC-023** (auto-rollback revert
> to protected master), plus the `scraper-ci` locations in **SEC-008/SEC-024**. Production
> now moves only via the manual **Promote dev → main** action (`promote.yml`), which
> currently uses an unpinned `gitleaks-action@v2` — track under the SEC-024 SHA-pin
> standard. `master` was renamed to `main`. Status rows below to be reconciled at the next
> security review.

## Counts by severity

| Critical | High | Medium | Low | Info | Total |
|---|---|---|---|---|---|
| 1 | 6 | 13 | 37 | 11 | 68 |

_Status (updated 2026-09-03): **29 fixed** (+SEC-046), **33 open** (+12 new SEC-057…068), **4 obsolete** (SEC-007/023/025/026 — CI overhaul), **1 accepted-risk** (SEC-054), **1 needs-decision** (SEC-039). The single critical (SEC-001) is fixed; no open critical. Remediation ongoing._

> **Note (FINDINGS.md is canonical for status).** Per-finding detail files may still show their
> original `open` status inline; this table is the source of truth.

## Open findings

| ID | Sev | Title | Location | Dimension | Status |
|---|---|---|---|---|---|
| [SEC-001](findings/critical.md#sec-001) | critical | Client-controlled issue text reaches an LLM with arbitrary-code-execution tools (Bash node) — prompt injection → RCE on the runner with write tokens | `.github/workflows/solver-agent.yml; agents/Solver - Issues/` | ci-workflows | ✅ fixed |
| [SEC-002](findings/high.md#sec-002) | high | Solver Agent: client-submitted issue text is injected verbatim into an autonomous code-fixing prompt that runs with a cross-tenant GitHub write token and node/npm shell access (prompt-injection → token exfiltration) | `agents/Solver - Issues/claim_issue.py; repo.py` | agents | ✅ fixed |
| [SEC-003](findings/high.md#sec-003) | high | Owner can create a booking against another tenant's resource (cross-tenant write + silent DoS) via unvalidated resource_id | `backend/auth_service/routers/booking_admin.py` (eligible-resource check) | authz-idor | ✅ fixed |
| [SEC-004](findings/high.md#sec-004) | high | anon/authenticated can EXECUTE SECURITY DEFINER solver-claim RPCs — dequeue/poison the auto-fix queue + cross-tenant issue disclosure | `migrations/2026_06_08_security_anon_surface_hardening.sql` | supabase-db | ✅ fixed |
| [SEC-056](findings/high.md#sec-056) | high | Solver agent retains command execution (`npm run`) while the Claude OAuth token is present on the runner — residual exfil path after SEC-001 hardening | `.github/workflows/solver-agent.yml` (harden-runner egress block) | agents | ✅ fixed |
| [SEC-005](findings/medium.md#sec-005) | medium | Admin issue-status update endpoint lets the Solver mark ANY issue done cross-project, decoupled from whether the agent actually fixed it | `backend/auth_service/routers/issues.py:276-344; agents/Solver - Issues…` | agents | open |
| [SEC-006](findings/medium.md#sec-006) | medium | Solver Agent auto-commits and force-pushes attacker-influenced file changes to cms-preview, which a single Slack ✅ promotes to client production | `agents/Solver - Issues/finalize.py:42-49; agents/Solver - Issues/repo.…` | agents | open |
| [SEC-007](findings/medium.md#sec-007) | medium | Dependabot auto-merge self-approves and merges minor/major-range bumps without independent review; a compromised dependency can reach master/prod | `.github/workflows/dependabot-auto-merge.yml:36-50` | ci-workflows | 🗑️ obsolete (file deleted 2026-06-09) |
| [SEC-008](findings/medium.md#sec-008) | medium | Scraper dependencies are not hash-pinned and have no lockfile (DEP-009 standard not applied) | `scraper/pyproject.toml:6-16; .github/workflows/scraper-ci.yml:27-31` | deps-supplychain | open |
| [SEC-009](findings/medium.md#sec-009) | medium | Unauthenticated HTML/email injection in multi-tenant form submissions (stored XSS in owner inbox) | `backend/auth_service/routers/forms.py` (html.escape) | public-tokens | ✅ fixed |
| [SEC-010](findings/medium.md#sec-010) | medium | In-memory rate limiter resets per serverless invocation and is not shared across instances on Vercel, neutering every slowapi limit (login, forms, booking, admin bearer) | `backend/auth_service/core/pg_rate_limit.py + rate_limits migration` | ratelimit-dos | ✅ fixed |
| [SEC-011](findings/medium.md#sec-011) | medium | No per-account lockout or throttle on /auth/login (only forgeable per-IP limit) | `backend/auth_service/routers/auth.py (Postgres login lockout)` | ratelimit-dos | ✅ fixed |
| [SEC-012](findings/medium.md#sec-012) | medium | Unauthenticated booking availability endpoints have no rate limit despite expensive per-day computation and DB I/O | `backend/auth_service/routers/booking.py (_public_read_limit)` | ratelimit-dos | ✅ fixed |
| [SEC-013](findings/medium.md#sec-013) | medium | slack_processed_events has RLS disabled and full anon DML grants — idempotency table is readable, writable and truncatable via PostgREST | `migrations/2026_06_08_security_anon_surface_hardening.sql` | supabase-db | ✅ fixed |
| [SEC-014](findings/medium.md#sec-014) | medium | HTML/email-template injection: form submission field keys AND values interpolated raw (unescaped) into the email sent to the project owner | `backend/auth_service/routers/forms.py` (html.escape) | xss-html | ✅ fixed |
| [SEC-015](findings/low.md#sec-015) | low | admin_api_keys have no rotation, listing, or revocation endpoint and no enforced expiry | `backend/auth_service/services/admin_keys.py:53-82; backend/auth_servic…` | admin-priv | open |
| [SEC-016](findings/low.md#sec-016) | low | CMS Connector concatenates untrusted client-website source files into the scan prompt with no data/instruction separation | `agents/CMS Connector - Website/prompts.py:201-214; agents/CMS Connecto…` | agents | open |
| [SEC-017](findings/low.md#sec-017) | low | Client-controlled issue title/description reflected into Slack mrkdwn notifications (limited injection) | `backend/auth_service/services/slack_notify.py:92-103,141` | agents | open |
| [SEC-018](findings/low.md#sec-018) | low | Design Prompt agent writes model-generated HTML (derived from untrusted scraped lead data) to leads.design_prompt, rendered in the admin dashboard via dangerouslySetInnerHTML with no sanitizer | `frontend/.../DesignPromptSection.tsx` (DOMPurify on render) | agents | ✅ fixed |
| [SEC-019](findings/low.md#sec-019) | low | Middleware fast-path serves authenticated pages for up to 13 min after server-side session revocation | `frontend/src/middleware.ts` (TTL 13min→60s) | authn-session | ✅ fixed |
| [SEC-020](findings/low.md#sec-020) | low | No per-account login throttling or lockout — only per-IP rate limiting | `backend/auth_service/routers/auth.py (Postgres login lockout)` | authn-session | ✅ fixed |
| [SEC-021](findings/low.md#sec-021) | low | Session cookie missing Secure flag and uses SameSite=lax on HTTPS preview deployments | `backend/auth_service/routers/auth.py` (Secure on prod+preview) | authn-session | ✅ fixed |
| [SEC-022](findings/low.md#sec-022) | low | Owner can link another tenant's resource into their own service (cross-tenant association write) via unvalidated resource_ids | `backend/auth_service/routers/booking_admin.py` (_validate_resource_ids) | authz-idor | ✅ fixed |
| [SEC-023](findings/low.md#sec-023) | low | Auto-rollback pushes a revert to protected master using GITHUB_TOKEN and opens issues from operator-influenced commit subjects | `.github/workflows/post-deploy-smoke.yml:32-34,118-145,148-171` | ci-workflows | 🗑️ obsolete (file deleted 2026-06-09) |
| [SEC-024](findings/low.md#sec-024) | low | Two workflows use unpinned (mutable-tag) third-party actions while the rest are SHA-pinned | `.github/workflows/solver-agent.yml:29,31; .github/workflows/scraper-ci…` | ci-workflows | open |
| [SEC-025](findings/low.md#sec-025) | low | Dependabot does not cover the scraper or the Solver agent (no automated security PRs) | `.github/dependabot.yml:8-66; scraper/pyproject.toml; agents/Solver - I…` | deps-supplychain | 🗑️ obsolete (dependabot.yml deleted; superseded by SEC-068) |
| [SEC-026](findings/low.md#sec-026) | low | Dependabot patch/minor PRs auto-approve + auto-merge with no human review, chaining into auto-merge dev→master to prod | `.github/workflows/dependabot-auto-merge.yml:36-50` | deps-supplychain | 🗑️ obsolete (file deleted 2026-06-09) |
| [SEC-027](findings/low.md#sec-027) | low | Stale, unpinned legacy backend/auth_service/requirements.txt drifted far behind the deployed manifest | `backend/auth_service/requirements.txt:1-13` | deps-supplychain | open |
| [SEC-028](findings/low.md#sec-028) | low | Unsanitized user-controlled `sort` column passed to PostgREST `.order()` (filter/column injection) | `backend/auth_service/routers/admin_leads.py` (_SORTABLE_COLUMNS) | injection | ✅ fixed |
| [SEC-029](findings/low.md#sec-029) | low | Cancelled-booking manage token remains valid and continues to expose customer details indefinitely | `backend/auth_service/routers/booking.py:522-571` | public-tokens | open |
| [SEC-030](findings/low.md#sec-030) | low | Public booking GET endpoints (manage/availability/config) have no rate limiting | `backend/auth_service/routers/booking.py (_public_read_limit)` | public-tokens | ✅ fixed |
| [SEC-031](findings/low.md#sec-031) | low | Reminder cron endpoint uses non-constant-time secret comparison | `backend/auth_service/routers/booking.py` (hmac.compare_digest) | public-tokens | ✅ fixed |
| [SEC-032](findings/low.md#sec-032) | low | Unvalidated user-controlled Reply-To on multi-tenant form email | `backend/auth_service/routers/forms.py` (_EMAIL_RE) | public-tokens | ✅ fixed |
| [SEC-033](findings/low.md#sec-033) | low | slack_processed_events dedup table is anon-reachable (RLS disabled) — event suppression / poisoning surface | `migrations/2026_06_08_security_anon_surface_hardening.sql` | public-tokens | ✅ fixed |
| [SEC-034](findings/low.md#sec-034) | low | Authenticated translation endpoints trigger paid DeepL work with no rate limit (cost/DoS amplification) | `backend/auth_service/routers/workspace.py (save_translate limit)` | ratelimit-dos | ✅ fixed |
| [SEC-035](findings/low.md#sec-035) | low | Public booking manage-token GET endpoint is unauthenticated and unlimited, enabling token-enumeration / scraping attempts | `backend/auth_service/routers/booking.py (_public_read_limit)` | ratelimit-dos | ✅ fixed |
| [SEC-036](findings/low.md#sec-036) | low | Country-code path component in region loader allows directory traversal (operator-gated) | `scraper/src/scraper/regions/__init__.py:29-32 (load_country)` | scraper | open |
| [SEC-037](findings/low.md#sec-037) | low | Scraped third-party PII (business names, mobile phone numbers, addresses) committed to the git repository in scraper output dumps | `scraper/plumbers-nl.json, scraper/leads-dry-run.json, scraper/lead-sin…` | scraper | open |
| [SEC-038](findings/low.md#sec-038) | low | Booking cron-secret comparison is not constant-time | `backend/auth_service/routers/booking.py` (hmac.compare_digest) | secrets-config | ✅ fixed |
| [SEC-039](findings/low.md#sec-039) | low | Credentialed CORS reflects Access-Control-Allow-Origin to any attacker-registered *.vercel.app subdomain | `backend/auth_service/main.py:59-90` | secrets-config | needs-decision |
| [SEC-040](findings/low.md#sec-040) | low | Frontend CSP permits 'unsafe-inline' and 'unsafe-eval' on script-src and broad connect-src https: | `frontend/next.config.ts:41,49` | secrets-config | open |
| [SEC-041](findings/low.md#sec-041) | low | Public forms endpoints leak raw upstream exception text in 502 responses | `backend/auth_service/routers/forms.py` (generic 502 + log) | secrets-config | ✅ fixed |
| [SEC-042](findings/low.md#sec-042) | low | SECURITY DEFINER view tenant_rls_status is anon-readable and exposes RLS posture of tenant tables | `migrations/2026_06_08_security_anon_surface_hardening.sql` | supabase-db | ✅ fixed |
| [SEC-043](findings/low.md#sec-043) | low | Design-prompt agent writeback bypasses the bleach sanitizer that protects the admin dangerouslySetInnerHTML sink | `frontend/.../DesignPromptSection.tsx` (DOMPurify on render) | xss-html | ✅ fixed |
| [SEC-044](findings/low.md#sec-044) | low | Tenant email_copy overrides inserted unescaped into booking emails (headings/subtitles) | `backend/auth_service/services/booking_i18n.py` (tt html_escape) | xss-html | ✅ fixed |
| [SEC-045](findings/low.md#sec-045) | low | Tenant-controlled booking brand fields (accent color, business_name, logo_url) interpolated raw into email HTML with no validation | `backend/auth_service/services/email_layout.py` (escape + hex accent) | xss-html | ✅ fixed |
| [SEC-046](findings/info.md#sec-046) | info | Bearer auth path returns a plain dict while the rest of the codebase assumes a UserOut object, creating an authZ-shape fragility | `backend/auth_service/routers/deps.py:60-75,86-91; backend/auth_service…` | admin-priv | ✅ fixed (2026-09-03 recon: proper object at dep boundary) |
| [SEC-047](findings/info.md#sec-047) | info | Session cookie not rotated to a stronger lifetime on remember-me users after password change | `backend/auth_service/routers/auth.py:117-125` | authn-session | open |
| [SEC-048](findings/info.md#sec-048) | info | Public booking slug allows tenant existence enumeration via config endpoint | `backend/auth_service/routers/booking.py:305-320` | public-tokens | open |
| [SEC-049](findings/info.md#sec-049) | info | Short-link expansion follows redirects without re-validating the resolved host (limited SSRF surface) | `scraper/src/scraper/urls.py:84-95 (expand_if_short)` | scraper | open |
| [SEC-050](findings/info.md#sec-050) | info | Backend application security-headers middleware omits Content-Security-Policy by design (relies on edge config) | `backend/auth_service/core/security_headers.py:9,13-30` | secrets-config | open |
| [SEC-051](findings/info.md#sec-051) | info | Historical Supabase Postgres DB password was committed in .env.example files (rotated; remains in git history) | `docs/superpowers/plans/2026-04-30-env-config-hygiene.md:19-20,182` | secrets-config | open |
| [SEC-052](findings/info.md#sec-052) | info | Short-link redirect expansion validates only a substring of the resolved URL, not its host | `scraper/src/scraper/urls.py:84-95` | ssrf-outbound | open |
| [SEC-053](findings/info.md#sec-053) | info | SECURITY DEFINER claim functions have mutable search_path (function_search_path_mutable) | `migrations/2026_06_08_security_anon_surface_hardening.sql` | supabase-db | ✅ fixed |
| [SEC-054](findings/info.md#sec-054) | info | Tenant-table RLS owner policies are inert because the app does not use Supabase Auth JWTs (auth.uid() always NULL) | `backend/migrations/2026_05_09_tenant_tables_rls.sql` | supabase-db | accepted-risk |
| [SEC-055](findings/info.md#sec-055) | info | Widget posts resize messages with wildcard target origin | `frontend/src/app/(widget)/w/[slug]/page.tsx:18-19` | xss-html | open |

## New findings — 2026-09-03 review

| ID | Sev | Title | Location | Dimension | Status |
|---|---|---|---|---|---|
| [SEC-057](findings/high.md#sec-057) | high | SEO-GEO agent competitor-intel phase string-interpolates untrusted competitor site content into a service-role `execute_sql` INSERT — second-order SQL injection (RLS-bypassing / cross-tenant worst case) | `agents/SEO-GEO Optimizer/phases/2-competitor-intel.md:54-57 (also phases 1/3/4/5)` | injection | 🚧 in-progress (PR #64 — awaiting human review) |
| [SEC-058](findings/high.md#sec-058) | high | Untrusted competitor/client site content fed into the SEO-GEO agent's LLM reasoning with no data/instruction separation while the orchestrator holds pre-authorized, never-pausing service-role Supabase SQL + CMS-admin write tools (prompt-injection → privileged cross-tenant writes) | `agents/SEO-GEO Optimizer/competitor.py:77-122; prompts.py; AGENTS.md (Autonomy)` | agents | 🚧 in-progress (PR #65 — awaiting human review) |
| [SEC-059](findings/medium.md#sec-059) | medium | Tenant `accent_color` interpolated raw into booking confirmation email button `style` attributes in `_cta_block` (missing `safe_hex` — SEC-045 class regression in new per-color code) | `backend/auth_service/services/booking_email.py:51,70` | xss-html | ✅ fixed (PR #61 → dev) |
| [SEC-060](findings/medium.md#sec-060) | medium | Tenant `accent` interpolated raw into reschedule/cancel client email button `_button()` (same SEC-045 class; sibling addcal button is sanitized, `_button` is not) | `backend/auth_service/services/booking_manage_email.py:48,155` | xss-html | ✅ fixed (PR #62 → dev) |
| [SEC-061](findings/medium.md#sec-061) | medium | New `POST /projects/{slug}/seo/translate` triggers a paid-DeepL amplification loop (O(rows×locales×fields) billable calls) with no rate limit — SEC-034 regression on the new endpoint | `backend/auth_service/routers/seo.py:247-250` | ratelimit-dos | ✅ fixed (PR #63 → dev) |
| [SEC-062](findings/low.md#sec-062) | low | `pg_rate_limit` fails open on any DB error, silently dropping the per-account login lockout + shared login counter during a Postgres brownout (brute-force window) | `backend/auth_service/core/pg_rate_limit.py:35-37,53-55` | authn-session | open |
| [SEC-063](findings/low.md#sec-063) | low | Public SEO consumer endpoints (`/seo/public/meta`, `/seo/public/articles`) are unauthenticated with no rate limiting — route/locale enumeration + unmetered scraping of published SEO content | `backend/auth_service/routers/seo.py:168-181` | ratelimit-dos | open |
| [SEC-064](findings/low.md#sec-064) | low | SEO-GEO `site_change_spec.route` is not path-validated before the Website Builder writes `app/[locale]/<route>/page.tsx` (LLM-authored route influenced by untrusted input; traversal defense-in-depth gap) | `agents/SEO-GEO Optimizer/site_change_spec.py:52-62` | agents | open |
| [SEC-065](findings/low.md#sec-065) | low | SEO-GEO `render_check.fetch_raw()` does an unrestricted `urllib` request (no scheme allowlist / redirect confinement / private-IP guard) on a tenant/lead-controlled URL (limited SSRF / local-file read on the agent host) | `agents/SEO-GEO Optimizer/render_check.py:18-23` | ssrf-outbound | open |
| [SEC-066](findings/low.md#sec-066) | low | `promote.yml` downloads and executes the gitleaks release tarball with no SHA256/integrity check, in the privileged promote job (holds `PROMOTE_TOKEN` to fast-forward protected `main` + prod deploy hooks) | `.github/workflows/promote.yml:42-43` | ci-workflows | open |
| [SEC-067](findings/low.md#sec-067) | low | Multi-tenant public form-submission access control relies on the client-forgeable `Origin` header (bounded by rate limiter; owner's own inbox is the only recipient) | `backend/auth_service/routers/forms.py:135-140` | public-tokens | open |
| [SEC-068](findings/info.md#sec-068) | info | No `.github/dependabot.yml` anywhere and no CI dependency scan → no automated mechanism surfaces vulnerable deps as PRs (posture note superseding the obsolete SEC-025) | `.github/dependabot.yml (absent)` | deps-supplychain | open |

## Dismissed (adversarially verified as false positives / non-issues)

Recorded so future reviews don't re-litigate them. See [`dismissed.md`](./dismissed.md).
