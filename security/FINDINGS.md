# Security Findings — Live Tracker

**Last full review:** 2026-06-07 · **Reviewer:** multi-agent workflow (14 dimensions, adversarial verification) · **Supabase:** xeluydwpgiddbamysgyu · **Confirmed:** 56 · **Dismissed (false-positive):** 14

This table is the **source of truth for status**. Detail for each finding lives in [`findings/`](./findings/) by severity. IDs are stable and never reused (see [`methodology.md`](./methodology.md) §5–6). Status: `open` · `in-progress` · `fixed` · `accepted-risk` · `false-positive` · `wont-fix`.

> **Remediation 2026-06-07** — `SEC-001` (critical), `SEC-002` (high, same chain), and the residual
> `SEC-056` (high) are remediated in code; awaiting one CI validation run. **Closed:** cross-tenant
> `SOLVER_GITHUB_TOKEN` theft (token stripped from `.git/config` during the untrusted run + a pre-push
> secret-scan gate), the `node -e` RCE (removed from the agent allowlist + explicit deny), nonce-fenced
> untrusted-data separation, and control-char input hardening. **Egress isolation** (the chosen full
> closure for SEC-056) is implemented: `step-security/harden-runner` (SHA-pinned, `block` mode) on the
> Solver job allows only the hosts it needs, so an injected agent cannot exfiltrate the Claude OAuth
> token. **Validation pending:** one `workflow_dispatch` run with `egress_policy=audit` to confirm the
> allowlist is complete, then all three flip to `fixed`. Verified: 29 Solver-agent + 436 backend tests
> green; workflow YAML valid.

## Counts by severity

| Critical | High | Medium | Low | Info | Total |
|---|---|---|---|---|---|
| 1 | 4 | 10 | 31 | 10 | 56 |

_Status: 3 in-progress (SEC-001, SEC-002, SEC-056 — code-complete, pending one CI validation run), 53 open._

## Open findings

| ID | Sev | Title | Location | Dimension | Status |
|---|---|---|---|---|---|
| [SEC-001](findings/critical.md#sec-001) | critical | Client-controlled issue text reaches an LLM with arbitrary-code-execution tools (Bash node) — prompt injection → RCE on the runner with write tokens | `.github/workflows/solver-agent.yml:91-100; agents/Solver - Issues/clai…` | ci-workflows | **in-progress** |
| [SEC-002](findings/high.md#sec-002) | high | Solver Agent: client-submitted issue text is injected verbatim into an autonomous code-fixing prompt that runs with a cross-tenant GitHub write token and node/npm shell access (prompt-injection → token exfiltration) | `agents/Solver - Issues/claim_issue.py:144-150; agents/Solver - Issues/…` | agents | **in-progress** |
| [SEC-003](findings/high.md#sec-003) | high | Owner can create a booking against another tenant's resource (cross-tenant write + silent DoS) via unvalidated resource_id | `backend/auth_service/routers/booking_admin.py:382-416` | authz-idor | open |
| [SEC-004](findings/high.md#sec-004) | high | anon/authenticated can EXECUTE SECURITY DEFINER solver-claim RPCs — dequeue/poison the auto-fix queue + cross-tenant issue disclosure | `backend/migrations/2026_05_16_solver_agent_columns.sql:27-80 (repo) vs…` | supabase-db | open |
| [SEC-056](findings/high.md#sec-056) | high | Solver agent retains command execution (`npm run`) while the Claude OAuth token is present on the runner — residual exfil path after SEC-001 hardening | `.github/workflows/solver-agent.yml` (harden-runner egress block) | agents | **in-progress** |
| [SEC-005](findings/medium.md#sec-005) | medium | Admin issue-status update endpoint lets the Solver mark ANY issue done cross-project, decoupled from whether the agent actually fixed it | `backend/auth_service/routers/issues.py:276-344; agents/Solver - Issues…` | agents | open |
| [SEC-006](findings/medium.md#sec-006) | medium | Solver Agent auto-commits and force-pushes attacker-influenced file changes to cms-preview, which a single Slack ✅ promotes to client production | `agents/Solver - Issues/finalize.py:42-49; agents/Solver - Issues/repo.…` | agents | open |
| [SEC-007](findings/medium.md#sec-007) | medium | Dependabot auto-merge self-approves and merges minor/major-range bumps without independent review; a compromised dependency can reach master/prod | `.github/workflows/dependabot-auto-merge.yml:36-50` | ci-workflows | open |
| [SEC-008](findings/medium.md#sec-008) | medium | Scraper dependencies are not hash-pinned and have no lockfile (DEP-009 standard not applied) | `scraper/pyproject.toml:6-16; .github/workflows/scraper-ci.yml:27-31` | deps-supplychain | open |
| [SEC-009](findings/medium.md#sec-009) | medium | Unauthenticated HTML/email injection in multi-tenant form submissions (stored XSS in owner inbox) | `backend/auth_service/routers/forms.py:23-41, 169-212` | public-tokens | open |
| [SEC-010](findings/medium.md#sec-010) | medium | In-memory rate limiter resets per serverless invocation and is not shared across instances on Vercel, neutering every slowapi limit (login, forms, booking, admin bearer) | `backend/auth_service/core/limiter.py:21; backend/auth_service/core/bea…` | ratelimit-dos | open |
| [SEC-011](findings/medium.md#sec-011) | medium | No per-account lockout or throttle on /auth/login (only forgeable per-IP limit) | `backend/auth_service/routers/auth.py:54-77; backend/auth_service/servi…` | ratelimit-dos | open |
| [SEC-012](findings/medium.md#sec-012) | medium | Unauthenticated booking availability endpoints have no rate limit despite expensive per-day computation and DB I/O | `backend/auth_service/routers/booking.py:337-351 (/booking/{slug}/avail…` | ratelimit-dos | open |
| [SEC-013](findings/medium.md#sec-013) | medium | slack_processed_events has RLS disabled and full anon DML grants — idempotency table is readable, writable and truncatable via PostgREST | `backend/migrations/2026_05_15_slack_inbound_s1_5.sql:33-39; live pg_cl…` | supabase-db | open |
| [SEC-014](findings/medium.md#sec-014) | medium | HTML/email-template injection: form submission field keys AND values interpolated raw (unescaped) into the email sent to the project owner | `backend/auth_service/routers/forms.py:30-41 (also :44-87, used by both…` | xss-html | open |
| [SEC-015](findings/low.md#sec-015) | low | admin_api_keys have no rotation, listing, or revocation endpoint and no enforced expiry | `backend/auth_service/services/admin_keys.py:53-82; backend/auth_servic…` | admin-priv | open |
| [SEC-016](findings/low.md#sec-016) | low | CMS Connector concatenates untrusted client-website source files into the scan prompt with no data/instruction separation | `agents/CMS Connector - Website/prompts.py:201-214; agents/CMS Connecto…` | agents | open |
| [SEC-017](findings/low.md#sec-017) | low | Client-controlled issue title/description reflected into Slack mrkdwn notifications (limited injection) | `backend/auth_service/services/slack_notify.py:92-103,141` | agents | open |
| [SEC-018](findings/low.md#sec-018) | low | Design Prompt agent writes model-generated HTML (derived from untrusted scraped lead data) to leads.design_prompt, rendered in the admin dashboard via dangerouslySetInnerHTML with no sanitizer | `agents/Design Prompt creator/phases/6-writeback.md:9-41; agents/Design…` | agents | open |
| [SEC-019](findings/low.md#sec-019) | low | Middleware fast-path serves authenticated pages for up to 13 min after server-side session revocation | `frontend/src/middleware.ts:56-61, 19-28` | authn-session | open |
| [SEC-020](findings/low.md#sec-020) | low | No per-account login throttling or lockout — only per-IP rate limiting | `backend/auth_service/routers/auth.py:62-68` | authn-session | open |
| [SEC-021](findings/low.md#sec-021) | low | Session cookie missing Secure flag and uses SameSite=lax on HTTPS preview deployments | `backend/auth_service/routers/auth.py:27, 30-40` | authn-session | open |
| [SEC-022](findings/low.md#sec-022) | low | Owner can link another tenant's resource into their own service (cross-tenant association write) via unvalidated resource_ids | `backend/auth_service/services/booking_admin_repo.py:166-177 (set_servi…` | authz-idor | open |
| [SEC-023](findings/low.md#sec-023) | low | Auto-rollback pushes a revert to protected master using GITHUB_TOKEN and opens issues from operator-influenced commit subjects | `.github/workflows/post-deploy-smoke.yml:32-34,118-145,148-171` | ci-workflows | open |
| [SEC-024](findings/low.md#sec-024) | low | Two workflows use unpinned (mutable-tag) third-party actions while the rest are SHA-pinned | `.github/workflows/solver-agent.yml:29,31; .github/workflows/scraper-ci…` | ci-workflows | open |
| [SEC-025](findings/low.md#sec-025) | low | Dependabot does not cover the scraper or the Solver agent (no automated security PRs) | `.github/dependabot.yml:8-66; scraper/pyproject.toml; agents/Solver - I…` | deps-supplychain | open |
| [SEC-026](findings/low.md#sec-026) | low | Dependabot patch/minor PRs auto-approve + auto-merge with no human review, chaining into auto-merge dev→master to prod | `.github/workflows/dependabot-auto-merge.yml:36-50` | deps-supplychain | open |
| [SEC-027](findings/low.md#sec-027) | low | Stale, unpinned legacy backend/auth_service/requirements.txt drifted far behind the deployed manifest | `backend/auth_service/requirements.txt:1-13` | deps-supplychain | open |
| [SEC-028](findings/low.md#sec-028) | low | Unsanitized user-controlled `sort` column passed to PostgREST `.order()` (filter/column injection) | `backend/auth_service/routers/admin_leads.py:34,69` | injection | open |
| [SEC-029](findings/low.md#sec-029) | low | Cancelled-booking manage token remains valid and continues to expose customer details indefinitely | `backend/auth_service/routers/booking.py:522-571` | public-tokens | open |
| [SEC-030](findings/low.md#sec-030) | low | Public booking GET endpoints (manage/availability/config) have no rate limiting | `backend/auth_service/routers/booking.py:534-571, 305-351, 805-839` | public-tokens | open |
| [SEC-031](findings/low.md#sec-031) | low | Reminder cron endpoint uses non-constant-time secret comparison | `backend/auth_service/routers/booking.py:745-749` | public-tokens | open |
| [SEC-032](findings/low.md#sec-032) | low | Unvalidated user-controlled Reply-To on multi-tenant form email | `backend/auth_service/routers/forms.py:182, 214-220` | public-tokens | open |
| [SEC-033](findings/low.md#sec-033) | low | slack_processed_events dedup table is anon-reachable (RLS disabled) — event suppression / poisoning surface | `backend/auth_service/services/slack_events_dedup.py:20-47` | public-tokens | open |
| [SEC-034](findings/low.md#sec-034) | low | Authenticated translation endpoints trigger paid DeepL work with no rate limit (cost/DoS amplification) | `backend/auth_service/routers/workspace.py:211-323 (save_service auto-t…` | ratelimit-dos | open |
| [SEC-035](findings/low.md#sec-035) | low | Public booking manage-token GET endpoint is unauthenticated and unlimited, enabling token-enumeration / scraping attempts | `backend/auth_service/routers/booking.py:534-571 (GET /booking/manage/{…` | ratelimit-dos | open |
| [SEC-036](findings/low.md#sec-036) | low | Country-code path component in region loader allows directory traversal (operator-gated) | `scraper/src/scraper/regions/__init__.py:29-32 (load_country)` | scraper | open |
| [SEC-037](findings/low.md#sec-037) | low | Scraped third-party PII (business names, mobile phone numbers, addresses) committed to the git repository in scraper output dumps | `scraper/plumbers-nl.json, scraper/leads-dry-run.json, scraper/lead-sin…` | scraper | open |
| [SEC-038](findings/low.md#sec-038) | low | Booking cron-secret comparison is not constant-time | `backend/auth_service/routers/booking.py:747-749` | secrets-config | open |
| [SEC-039](findings/low.md#sec-039) | low | Credentialed CORS reflects Access-Control-Allow-Origin to any attacker-registered *.vercel.app subdomain | `backend/auth_service/main.py:59-90` | secrets-config | open |
| [SEC-040](findings/low.md#sec-040) | low | Frontend CSP permits 'unsafe-inline' and 'unsafe-eval' on script-src and broad connect-src https: | `frontend/next.config.ts:41,49` | secrets-config | open |
| [SEC-041](findings/low.md#sec-041) | low | Public forms endpoints leak raw upstream exception text in 502 responses | `backend/auth_service/routers/forms.py:224-228, 308-312` | secrets-config | open |
| [SEC-042](findings/low.md#sec-042) | low | SECURITY DEFINER view tenant_rls_status is anon-readable and exposes RLS posture of tenant tables | `backend/migrations/2026_05_09_tenant_tables_rls.sql:168-185; live pg_c…` | supabase-db | open |
| [SEC-043](findings/low.md#sec-043) | low | Design-prompt agent writeback bypasses the bleach sanitizer that protects the admin dangerouslySetInnerHTML sink | `agents/Design Prompt creator/phases/6-writeback.md:37 (raw SQL UPDATE …` | xss-html | open |
| [SEC-044](findings/low.md#sec-044) | low | Tenant email_copy overrides inserted unescaped into booking emails (headings/subtitles) | `backend/auth_service/services/booking_i18n.py:59-70 (tt) consumed at b…` | xss-html | open |
| [SEC-045](findings/low.md#sec-045) | low | Tenant-controlled booking brand fields (accent color, business_name, logo_url) interpolated raw into email HTML with no validation | `backend/auth_service/services/email_layout.py:64-74 (header), 79-84 (f…` | xss-html | open |
| [SEC-046](findings/info.md#sec-046) | info | Bearer auth path returns a plain dict while the rest of the codebase assumes a UserOut object, creating an authZ-shape fragility | `backend/auth_service/routers/deps.py:60-75,86-91; backend/auth_service…` | admin-priv | open |
| [SEC-047](findings/info.md#sec-047) | info | Session cookie not rotated to a stronger lifetime on remember-me users after password change | `backend/auth_service/routers/auth.py:117-125` | authn-session | open |
| [SEC-048](findings/info.md#sec-048) | info | Public booking slug allows tenant existence enumeration via config endpoint | `backend/auth_service/routers/booking.py:305-320` | public-tokens | open |
| [SEC-049](findings/info.md#sec-049) | info | Short-link expansion follows redirects without re-validating the resolved host (limited SSRF surface) | `scraper/src/scraper/urls.py:84-95 (expand_if_short)` | scraper | open |
| [SEC-050](findings/info.md#sec-050) | info | Backend application security-headers middleware omits Content-Security-Policy by design (relies on edge config) | `backend/auth_service/core/security_headers.py:9,13-30` | secrets-config | open |
| [SEC-051](findings/info.md#sec-051) | info | Historical Supabase Postgres DB password was committed in .env.example files (rotated; remains in git history) | `docs/superpowers/plans/2026-04-30-env-config-hygiene.md:19-20,182` | secrets-config | open |
| [SEC-052](findings/info.md#sec-052) | info | Short-link redirect expansion validates only a substring of the resolved URL, not its host | `scraper/src/scraper/urls.py:84-95` | ssrf-outbound | open |
| [SEC-053](findings/info.md#sec-053) | info | SECURITY DEFINER claim functions have mutable search_path (function_search_path_mutable) | `backend/migrations/2026_05_16_solver_agent_columns.sql:27-77; live pg_…` | supabase-db | open |
| [SEC-054](findings/info.md#sec-054) | info | Tenant-table RLS owner policies are inert because the app does not use Supabase Auth JWTs (auth.uid() always NULL) | `backend/migrations/2026_05_09_tenant_tables_rls.sql:35-159 (and 2026_0…` | supabase-db | open |
| [SEC-055](findings/info.md#sec-055) | info | Widget posts resize messages with wildcard target origin | `frontend/src/app/(widget)/w/[slug]/page.tsx:18-19` | xss-html | open |

## Dismissed (adversarially verified as false positives / non-issues)

Recorded so future reviews don't re-litigate them. See [`dismissed.md`](./dismissed.md).
