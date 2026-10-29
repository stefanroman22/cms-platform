# Security Findings — Live Tracker

**Last full review:** 2026-10-29 · **Reviewer:** multi-agent workflow (13 finders + reconciliation, adversarial verification; 31 agents) · **Supabase:** xeluydwpgiddbamysgyu (live MCP UNAVAILABLE this run — code-only) · **Confirmed:** 76 · **Dismissed (false-positive):** 16

This table is the **source of truth for status**. Detail for each finding lives in [`findings/`](./findings/) by severity. IDs are stable and never reused (see [`methodology.md`](./methodology.md) §5–6). Status: `open` · `in-progress` · `fixed` · `accepted-risk` · `false-positive` · `wont-fix`.

> **2026-10-29 — Weekly full review (multi-agent, 13 finders + reconciliation, 31 agents).** **No new critical/high.**
> +8 new findings (**1 medium, 4 low, 3 info**), all `open`; 7 verifier "dismissals" were all dedup
> re-confirmations of already-tracked findings (not new false positives). This review's **highest-yield new
> surfaces** — file uploads (SVG/font + MIME allow/deny), rich text (ADR-0010/0011), project theme/CSS, and
> the Google Places lead-import pipeline (ADR-0012) — were deeply audited and found **sound** (allow-list
> SVG sanitizer, default-deny rich-text canonicalizer, charset-restricted theme, tenant-derived upload keys
> on the isolated storage origin). The live risk theme shifted from the internet-facing edges (which held)
> to the **agent/automation guardrail layer**:
> - **SEC-071 (medium, new)** — the `guard.mjs` PreToolUse hooks never cover GitHub MCP write tools, so
>   H1 "never push to `main`" is unenforced for `mcp__github__push_files/create_or_update_file/merge_pull_request`
>   (while Bash `git push origin main` is blocked), and `main` has no server-side branch protection (ADR-0007).
>   Reachable by chaining the open `SEC-016` prompt-injection surface in the CMS Connector agent.
> - **SEC-072/073/075/076 (low, new)** — `upload_logo` SVG-sanitizer bypass (isolated-origin stored XSS);
>   `website_enrich` SSRF TOCTOU/DNS-rebind (admin-gated); `guard.mjs` command-reshaping bypass; Design-Prompt
>   Phase 6 dollar-quote SQL-breakout (human-approval gated).
> - **SEC-074/077/078 (info, new)** — `expand_short_link` redirect without re-validation; sessions renew to
>   full lifetime with no absolute cap; upload endpoints have no per-user frequency limit.
>
> **Status changes this run:** `SEC-024` → **fixed** (unpinned `gitleaks-action@v2` gone; promote.yml now
> fetches the binary via curl — that residual is `SEC-065`); `SEC-027` → **obsolete** (stale duplicate
> `requirements.txt` deleted); `SEC-046` → **fixed** (bearer dict normalized to `UserOut` at `deps.py:67`);
> `SEC-034` → **partial/reopened** (the rate limit landed on `save_service` only; `retranslate_service`
> and `set_project_locales` remain uncapped — owner/admin-gated and DeepL dormant in prod, so low/info);
> `SEC-067` → stays **open**, **re-scoped** to `public.google_import_usage` (the `seo_*` tables were dropped
> 2026-09-27, but the same default-ACL-without-REVOKE pattern recurs in `2026_10_11_lead_google_import.sql`);
> `SEC-051` → **cannot-verify** this run (shallow clone; the cited history commit is absent — rotation needs
> out-of-band confirmation). `SEC-028` re-confirmed fixed (`_SORTABLE_COLUMNS` allowlist present). All other
> open low/info rows re-read and **re-confirmed still present**, unchanged.
> **MCP gap:** this was a headless cloud run — the Supabase (`get_advisors`, `execute_sql`) and Vercel
> (`get_project`) MCP servers were **not available**, so live DB advisor/RLS/GRANT state and Vercel env
> posture could not be pulled; the DB dimension was reviewed code-only (migrations). Items needing live
> confirmation are flagged in [`review-log.md`](./review-log.md).
> **Remediation order:** SEC-071 → SEC-072 → SEC-073 → SEC-075 → SEC-076 → SEC-034(finish) → SEC-029 → SEC-060 → SEC-068 → SEC-067.

> **Note 2026-08-26 — Feature removals.** The auto-fix pipeline (issues API + Slack S1/S1.5 +
> Solver Agent + `solver-agent.yml`) and the lead scraper (`scraper/` + `admin_scrape_jobs`) were
> deleted entirely. This obsoletes **SEC-005, SEC-006, SEC-008, SEC-017, SEC-036, SEC-037,
> SEC-049, SEC-052, SEC-063, SEC-064** (their code no longer exists). Already-`fixed` findings in
> that code (SEC-001/002/004/013/033/056) keep their status as historical record. **SEC-024 stays
> open** — its live remainder is the unpinned `gitleaks-action@v2` in `promote.yml`. DB objects
> (`project_issues`, `slack_processed_events`, `scrape_jobs`, solver RPCs) are dropped by
> `backend/migrations/2026_08_26_drop_removed_feature_tables.sql` once applied.

> **2026-06-20 — Weekly full review.** +12 new findings (**0 critical, 0 high, 3 medium, 7 low, 2 info**), all `open`;
> 2 candidates adversarially dismissed. No new critical/high — the internet-facing edges held. Headline live
> risks: the unauthenticated **booking write-path** and **marketing `/forms/contact`** rate limits still use the
> per-instance in-memory limiter (cost/DoS + Resend email-spam amplification — `SEC-058`/`SEC-059`), and a
> **tenant accent-color HTML-injection sink** in `booking_email._cta_block` that the `SEC-045` hardening missed
> (`SEC-057`). Status reconciliation: **`SEC-050` → fixed** (backend now emits a strict edge CSP via `vercel.json`);
> **`SEC-007`/`SEC-025`/`SEC-026` (Dependabot) and `SEC-023` (post-deploy-smoke) → obsolete** (infra removed
> 2026-06-09). Remediation order: SEC-058 → SEC-059 → SEC-057 → SEC-029 → SEC-060 → SEC-006 → SEC-066 → SEC-063.
> See [`review-log.md`](./review-log.md).

> **⚠ Saturday Solver 2026-09-26 — ID-collision + reconciliation notice (needs a human to de-dupe the trackers).**
> This dev tracker (2026-06-20 review) and the unmerged `origin/security/weekly-review-2026-09-24` branch use
> **the same `SEC-057…` numbers for different findings**, and several *fix commits* used yet a third labelling
> (e.g. the booking-write-limit fix landed as "SEC-057" in PR #69's title but is **SEC-058** here; the accent-XSS
> fix landed as "SEC-059" in PR #61's title but is **SEC-057** here; and this run's `/forms/contact` fix — dev
> **SEC-059** — merged as PR #80, reusing an ID that PR #61's title also used). **IDs are unreliable; trust the
> file location + concrete vuln.** A human should collapse the two trackers into one numbering scheme.
> This run reconciled by verifying against the actual dev code:
> **`SEC-057` (accent XSS in `_cta_block`) → fixed** (commit `d18d7f2`/PR #61); **`SEC-058` (booking write-path
> rate limit) → fixed** (commit `a982d97`/PR #69); **`SEC-059` (`/forms/contact` rate limit) → fixed** (PR #80,
> this run). Still `open`: **SEC-005** (admin issue-status is cross-project *by design* — needs a scoping/token
> redesign, not a surgical patch) and **SEC-006** (Solver auto-commit needs a machine-checked diff gate) — both
> architecturally significant, left for a human. **Untracked here:** the `weekly-review-2026-09-24` branch reports
> a **medium "SEO-GEO Optimizer indirect-prompt-injection → autonomous publish"** finding
> (`agents/SEO-GEO Optimizer/prompts.py` + `phases/`) that postdates this tracker's 2026-06-20 review and is NOT
> a row here. It is a real open medium: the fix (nonce-fence scraped HTML as data, mirroring the Solver, + a
> pre-publish diff gate) is a prompt/design change on an autonomous-publish path with no unit-testable seam, so it
> is **deferred to a human**, not auto-fixed.

> **Saturday Solver 2026-10-03 — no open critical/high/medium remain; status-only run.**
> This week's run selected against the C/H/M fix threshold and verified every candidate against the
> **actual current dev tree** (HEAD `fa7796a`, 2026-10-01), not the trackers. Result: **zero open
> critical/high/medium vulnerabilities exist in the dev codebase** — so no fix PRs were shipped.
> Verification:
> - The freshest Friday-review branch, `origin/security/weekly-review-2026-09-24`, is **stale**: it was
>   cut against a tree that still contained the Solver agent, the scraper, the SEO router and the
>   SEO-GEO Optimizer agent. On current dev **all of these are removed** — `agents/Solver - Issues/`,
>   `agents/SEO-GEO Optimizer/`, `scraper/`, `backend/auth_service/routers/seo.py`,
>   `backend/auth_service/routers/issues.py`, `backend/auth_service/services/slack_notify.py`,
>   `.github/workflows/solver-agent.yml`, `.github/workflows/scraper-ci.yml` and
>   `.github/workflows/dependabot-auto-merge.yml` are all **absent**. Its new mediums map to:
>   **SEC-058 (accent XSS in `booking_email._cta_block`) → already fixed** on dev — `_cta_block` runs
>   `accent = email_layout.safe_hex(accent, "#18181b")` before both style sinks (this tracker's SEC-057,
>   PR #61); **SEC-061 (SEO-GEO indirect-prompt-injection) → obsolete** (agent code removed).
> - Every C/H/M row in **this** tracker is already `fixed` or `obsolete` (Solver/scraper/issues/dependabot
>   code removed 2026-08-26 and in the 2026-06-09 CI teardown). A grep for open/in-progress C/H/M rows
>   returns none.
> - **Needs a human (unchanged):** the `SEC-057…`/`SEC-058…` **ID collision** between this tracker and the
>   two unmerged review branches (`weekly-review-2026-09-17`, `-2026-09-24`) still wants a single
>   renumbering pass — see the 2026-09-26 note above. **SEC-039** (credentialed-CORS reflects any
>   `*.vercel.app`) remains `needs-decision`. **SEC-054** stays `accepted-risk`.
> - Remaining genuinely-open work is all **low/info** (below this routine's C/H/M threshold): SEC-015,
>   SEC-016, SEC-024(remnant), SEC-027, SEC-029, SEC-040, SEC-046, SEC-047, SEC-048, SEC-051, SEC-055,
>   SEC-060, SEC-061(info), SEC-062, SEC-065, SEC-066, SEC-067, SEC-068. These are left for a future
>   run or a human; none was modified this week.

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
| 1 | 4 | 14 | 42 | 15 | 76 |

_2026-10-29: +8 confirmed (SEC-071 medium; SEC-072/073/075/076 low; SEC-074/077/078 info) vs. the 68 baseline. No critical/high added._

_Status (updated 2026-06-20): the 2026-06-07 baseline reached **28 fixed**, **1 accepted-risk** (SEC-054), **1 needs-decision** (SEC-039 credentialed-CORS). The 2026-06-20 review added **12 new findings** (all open), flipped **SEC-050 → fixed** and **SEC-007/023/025/026 → obsolete** (infra removed), and re-confirmed the remaining open items still present. Remediation ongoing — the **Saturday Solver routine** now drains open critical/high/medium automatically via tested PRs._

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
| [SEC-005](findings/medium.md#sec-005) | medium | Admin issue-status update endpoint lets the Solver mark ANY issue done cross-project, decoupled from whether the agent actually fixed it | `backend/auth_service/routers/issues.py:276-344; agents/Solver - Issues…` | agents | obsolete |
| [SEC-006](findings/medium.md#sec-006) | medium | Solver Agent auto-commits and force-pushes attacker-influenced file changes to cms-preview, which a single Slack ✅ promotes to client production | `agents/Solver - Issues/finalize.py:42-49; agents/Solver - Issues/repo.…` | agents | obsolete |
| [SEC-007](findings/medium.md#sec-007) | medium | Dependabot auto-merge self-approves and merges minor/major-range bumps without independent review; a compromised dependency can reach master/prod | `.github/workflows/dependabot-auto-merge.yml:36-50` | ci-workflows | obsolete |
| [SEC-008](findings/medium.md#sec-008) | medium | Scraper dependencies are not hash-pinned and have no lockfile (DEP-009 standard not applied) | `scraper/pyproject.toml:6-16; .github/workflows/scraper-ci.yml:27-31` | deps-supplychain | obsolete (scraper removed 2026-08-26; the #70 lockfiles were removed with it) |
| [SEC-009](findings/medium.md#sec-009) | medium | Unauthenticated HTML/email injection in multi-tenant form submissions (stored XSS in owner inbox) | `backend/auth_service/routers/forms.py` (html.escape) | public-tokens | ✅ fixed |
| [SEC-010](findings/medium.md#sec-010) | medium | In-memory rate limiter resets per serverless invocation and is not shared across instances on Vercel, neutering every slowapi limit (login, forms, booking, admin bearer) | `backend/auth_service/core/pg_rate_limit.py + rate_limits migration` | ratelimit-dos | ✅ fixed |
| [SEC-011](findings/medium.md#sec-011) | medium | No per-account lockout or throttle on /auth/login (only forgeable per-IP limit) | `backend/auth_service/routers/auth.py (Postgres login lockout)` | ratelimit-dos | ✅ fixed |
| [SEC-012](findings/medium.md#sec-012) | medium | Unauthenticated booking availability endpoints have no rate limit despite expensive per-day computation and DB I/O | `backend/auth_service/routers/booking.py (_public_read_limit)` | ratelimit-dos | ✅ fixed |
| [SEC-013](findings/medium.md#sec-013) | medium | slack_processed_events has RLS disabled and full anon DML grants — idempotency table is readable, writable and truncatable via PostgREST | `migrations/2026_06_08_security_anon_surface_hardening.sql` | supabase-db | ✅ fixed |
| [SEC-014](findings/medium.md#sec-014) | medium | HTML/email-template injection: form submission field keys AND values interpolated raw (unescaped) into the email sent to the project owner | `backend/auth_service/routers/forms.py` (html.escape) | xss-html | ✅ fixed |
| [SEC-015](findings/low.md#sec-015) | low | admin_api_keys have no rotation, listing, or revocation endpoint and no enforced expiry | `backend/auth_service/services/admin_keys.py:53-82; backend/auth_servic…` | admin-priv | open |
| [SEC-016](findings/low.md#sec-016) | low | CMS Connector concatenates untrusted client-website source files into the scan prompt with no data/instruction separation | `agents/CMS Connector - Website/prompts.py:201-214; agents/CMS Connecto…` | agents | open |
| [SEC-017](findings/low.md#sec-017) | low | Client-controlled issue title/description reflected into Slack mrkdwn notifications (limited injection) | `backend/auth_service/services/slack_notify.py:92-103,141` | agents | obsolete |
| [SEC-018](findings/low.md#sec-018) | low | Design Prompt agent writes model-generated HTML (derived from untrusted scraped lead data) to leads.design_prompt, rendered in the admin dashboard via dangerouslySetInnerHTML with no sanitizer | `frontend/.../DesignPromptSection.tsx` (DOMPurify on render) | agents | ✅ fixed |
| [SEC-019](findings/low.md#sec-019) | low | Middleware fast-path serves authenticated pages for up to 13 min after server-side session revocation | `frontend/src/middleware.ts` (TTL 13min→60s) | authn-session | ✅ fixed |
| [SEC-020](findings/low.md#sec-020) | low | No per-account login throttling or lockout — only per-IP rate limiting | `backend/auth_service/routers/auth.py (Postgres login lockout)` | authn-session | ✅ fixed |
| [SEC-021](findings/low.md#sec-021) | low | Session cookie missing Secure flag and uses SameSite=lax on HTTPS preview deployments | `backend/auth_service/routers/auth.py` (Secure on prod+preview) | authn-session | ✅ fixed |
| [SEC-022](findings/low.md#sec-022) | low | Owner can link another tenant's resource into their own service (cross-tenant association write) via unvalidated resource_ids | `backend/auth_service/routers/booking_admin.py` (_validate_resource_ids) | authz-idor | ✅ fixed |
| [SEC-023](findings/low.md#sec-023) | low | Auto-rollback pushes a revert to protected master using GITHUB_TOKEN and opens issues from operator-influenced commit subjects | `.github/workflows/post-deploy-smoke.yml:32-34,118-145,148-171` | ci-workflows | obsolete |
| [SEC-024](findings/low.md#sec-024) | low | Two workflows use unpinned (mutable-tag) third-party actions while the rest are SHA-pinned | `.github/workflows/promote.yml (was solver/scraper, removed)` | ci-workflows | ✅ fixed (2026-10-29 — unpinned `gitleaks-action@v2` remnant gone; promote.yml SHA-pins all actions; the curl-fetched gitleaks binary residual is now SEC-065) |
| [SEC-025](findings/low.md#sec-025) | low | Dependabot does not cover the scraper or the Solver agent (no automated security PRs) | `.github/dependabot.yml:8-66; scraper/pyproject.toml; agents/Solver - I…` | deps-supplychain | obsolete |
| [SEC-026](findings/low.md#sec-026) | low | Dependabot patch/minor PRs auto-approve + auto-merge with no human review, chaining into auto-merge dev→master to prod | `.github/workflows/dependabot-auto-merge.yml:36-50` | deps-supplychain | obsolete |
| [SEC-027](findings/low.md#sec-027) | low | Stale, unpinned legacy backend/auth_service/requirements.txt drifted far behind the deployed manifest | `backend/auth_service/requirements.txt (deleted)` | deps-supplychain | obsolete (2026-10-29 — stale duplicate manifest deleted; no drift remnant) |
| [SEC-028](findings/low.md#sec-028) | low | Unsanitized user-controlled `sort` column passed to PostgREST `.order()` (filter/column injection) | `backend/auth_service/routers/admin_leads.py` (_SORTABLE_COLUMNS) | injection | ✅ fixed |
| [SEC-029](findings/low.md#sec-029) | low | Cancelled-booking manage token remains valid and continues to expose customer details indefinitely | `backend/auth_service/routers/booking.py:522-571` | public-tokens | open |
| [SEC-030](findings/low.md#sec-030) | low | Public booking GET endpoints (manage/availability/config) have no rate limiting | `backend/auth_service/routers/booking.py (_public_read_limit)` | public-tokens | ✅ fixed |
| [SEC-031](findings/low.md#sec-031) | low | Reminder cron endpoint uses non-constant-time secret comparison | `backend/auth_service/routers/booking.py` (hmac.compare_digest) | public-tokens | ✅ fixed |
| [SEC-032](findings/low.md#sec-032) | low | Unvalidated user-controlled Reply-To on multi-tenant form email | `backend/auth_service/routers/forms.py` (_EMAIL_RE) | public-tokens | ✅ fixed |
| [SEC-033](findings/low.md#sec-033) | low | slack_processed_events dedup table is anon-reachable (RLS disabled) — event suppression / poisoning surface | `migrations/2026_06_08_security_anon_surface_hardening.sql` | public-tokens | ✅ fixed |
| [SEC-034](findings/low.md#sec-034) | low | Authenticated translation endpoints trigger paid DeepL work with no rate limit (cost/DoS amplification) | `backend/auth_service/routers/workspace.py:1166 (retranslate_service), :1108 (set_project_locales)` | ratelimit-dos | partial (2026-10-29 — reopened: limit landed on `save_service` only; `retranslate_service` + `set_project_locales` still uncapped; owner/admin-gated + DeepL dormant in prod → low/info) |
| [SEC-035](findings/low.md#sec-035) | low | Public booking manage-token GET endpoint is unauthenticated and unlimited, enabling token-enumeration / scraping attempts | `backend/auth_service/routers/booking.py (_public_read_limit)` | ratelimit-dos | ✅ fixed |
| [SEC-036](findings/low.md#sec-036) | low | Country-code path component in region loader allows directory traversal (operator-gated) | `scraper/src/scraper/regions/__init__.py:29-32 (load_country)` | scraper | obsolete |
| [SEC-037](findings/low.md#sec-037) | low | Scraped third-party PII (business names, mobile phone numbers, addresses) committed to the git repository in scraper output dumps | `scraper/plumbers-nl.json, scraper/leads-dry-run.json, scraper/lead-sin…` | scraper | obsolete |
| [SEC-038](findings/low.md#sec-038) | low | Booking cron-secret comparison is not constant-time | `backend/auth_service/routers/booking.py` (hmac.compare_digest) | secrets-config | ✅ fixed |
| [SEC-039](findings/low.md#sec-039) | low | Credentialed CORS reflects Access-Control-Allow-Origin to any attacker-registered *.vercel.app subdomain | `backend/auth_service/main.py:59-90` | secrets-config | needs-decision |
| [SEC-040](findings/low.md#sec-040) | low | Frontend CSP permits 'unsafe-inline' and 'unsafe-eval' on script-src and broad connect-src https: | `frontend/next.config.ts:41,49` | secrets-config | open |
| [SEC-041](findings/low.md#sec-041) | low | Public forms endpoints leak raw upstream exception text in 502 responses | `backend/auth_service/routers/forms.py` (generic 502 + log) | secrets-config | ✅ fixed |
| [SEC-042](findings/low.md#sec-042) | low | SECURITY DEFINER view tenant_rls_status is anon-readable and exposes RLS posture of tenant tables | `migrations/2026_06_08_security_anon_surface_hardening.sql` | supabase-db | ✅ fixed |
| [SEC-043](findings/low.md#sec-043) | low | Design-prompt agent writeback bypasses the bleach sanitizer that protects the admin dangerouslySetInnerHTML sink | `frontend/.../DesignPromptSection.tsx` (DOMPurify on render) | xss-html | ✅ fixed |
| [SEC-044](findings/low.md#sec-044) | low | Tenant email_copy overrides inserted unescaped into booking emails (headings/subtitles) | `backend/auth_service/services/booking_i18n.py` (tt html_escape) | xss-html | ✅ fixed |
| [SEC-045](findings/low.md#sec-045) | low | Tenant-controlled booking brand fields (accent color, business_name, logo_url) interpolated raw into email HTML with no validation | `backend/auth_service/services/email_layout.py` (escape + hex accent) | xss-html | ✅ fixed |
| [SEC-046](findings/info.md#sec-046) | info | Bearer auth path returns a plain dict while the rest of the codebase assumes a UserOut object, creating an authZ-shape fragility | `backend/auth_service/routers/deps.py:67` | admin-priv | ✅ fixed (2026-10-29 — `admin_user_via_bearer_or_sid` normalizes the verify dict to `UserOut`; no path receives the bare dict) |
| [SEC-047](findings/info.md#sec-047) | info | Session cookie not rotated to a stronger lifetime on remember-me users after password change | `backend/auth_service/routers/auth.py:117-125` | authn-session | open |
| [SEC-048](findings/info.md#sec-048) | info | Public booking slug allows tenant existence enumeration via config endpoint | `backend/auth_service/routers/booking.py:305-320` | public-tokens | open |
| [SEC-049](findings/info.md#sec-049) | info | Short-link expansion follows redirects without re-validating the resolved host (limited SSRF surface) | `scraper/src/scraper/urls.py:84-95 (expand_if_short)` | scraper | obsolete |
| [SEC-050](findings/info.md#sec-050) | info | Backend application security-headers middleware omits Content-Security-Policy by design (relies on edge config) | `backend/auth_service/core/security_headers.py:9,13-30` | secrets-config | ✅ fixed |
| [SEC-051](findings/info.md#sec-051) | info | Historical Supabase Postgres DB password was committed in .env.example files (rotated; remains in git history) | `docs/superpowers/plans/2026-04-30-env-config-hygiene.md:19-20,182` | secrets-config | open |
| [SEC-052](findings/info.md#sec-052) | info | Short-link redirect expansion validates only a substring of the resolved URL, not its host | `scraper/src/scraper/urls.py:84-95` | ssrf-outbound | obsolete |
| [SEC-053](findings/info.md#sec-053) | info | SECURITY DEFINER claim functions have mutable search_path (function_search_path_mutable) | `migrations/2026_06_08_security_anon_surface_hardening.sql` | supabase-db | ✅ fixed |
| [SEC-054](findings/info.md#sec-054) | info | Tenant-table RLS owner policies are inert because the app does not use Supabase Auth JWTs (auth.uid() always NULL) | `backend/migrations/2026_05_09_tenant_tables_rls.sql` | supabase-db | accepted-risk |
| [SEC-055](findings/info.md#sec-055) | info | Widget posts resize messages with wildcard target origin | `frontend/src/app/(widget)/w/[slug]/page.tsx:18-19` | xss-html | open |
| [SEC-057](findings/medium.md#sec-057) | medium | Tenant accent color injected unsanitized into booking confirmation email style attribute (`_cta_block` missed the SEC-045 sink) | `backend/auth_service/services/booking_email.py:51,70` | xss-html | ✅ fixed (commit `d18d7f2`, PR #61 — `_cta_block` now `safe_hex(accent, …)` before both style sinks; verified 2026-09-26) |
| [SEC-058](findings/medium.md#sec-058) | medium | Unauthenticated booking create/cancel/reschedule write paths use only the in-memory slowapi limiter (per-instance reset) → email/booking-spam amplification | `backend/auth_service/routers/booking.py:462-463,691-692,753-754,989-990` | ratelimit-dos | ✅ fixed (commit `a982d97`, PR #69 — `_public_write_limit` shared Postgres cap on create/manage-cancel/reschedule/legacy-create; verified 2026-09-26) |
| [SEC-059](findings/medium.md#sec-059) | medium | Marketing `/forms/contact` endpoint protected only by in-memory slowapi limiter → cross-instance Resend email-spam amplification | `backend/auth_service/routers/forms.py:282-345` | ratelimit-dos | ✅ fixed (PR `security/fix-SEC-059-2026-09-26` — shared Postgres per-IP limit added to `submit_contact`, mirroring `submit_form`/SEC-010) |
| [SEC-060](findings/low.md#sec-060) | low | Python `str.format()` injection: tenant-controlled booking email copy override used as the format string | `backend/auth_service/services/booking_i18n.py:86-95` | injection | open |
| [SEC-061](findings/info.md#sec-061) | info | Admin Bearer brute-force limiter is process-local (per serverless instance); threat-model comment miscites a 192-bit (actually 128-bit) secret | `backend/auth_service/core/bearer_limiter.py:6-10,23-61` | ratelimit-dos | open |
| [SEC-062](findings/low.md#sec-062) | low | Scraped business `website_url`/`source_url` rendered as anchor href in admin dashboard without scheme allowlist | `frontend/src/components/admin/leads/sections/ContactSection.tsx:215-223; LeadDetailDrawer.tsx:214-216,480-487` | xss-html | open |
| [SEC-063](findings/low.md#sec-063) | low | Solver Agent installs `@anthropic-ai/claude-code@latest` unpinned on a runner holding the live OAuth credential and untrusted input | `.github/workflows/solver-agent.yml:91-96` | deps-supplychain | obsolete |
| [SEC-064](findings/low.md#sec-064) | low | `solver-agent.yml` pins `actions/checkout`/`actions/setup-python` to mutable major tags instead of commit SHAs | `.github/workflows/solver-agent.yml:64,66` | ci-workflows | obsolete |
| [SEC-065](findings/low.md#sec-065) | low | `promote.yml` fetches the gitleaks secret-scanner binary without checksum/signature verification | `.github/workflows/promote.yml:42` | ci-workflows | open |
| [SEC-066](findings/low.md#sec-066) | low | Admin API key `scopes` are stored but never enforced — every key is full-admin | `backend/auth_service/services/admin_keys.py:106; routers/deps.py:42-81` | admin-priv | open |
| [SEC-067](findings/info.md#sec-067) | info | Public table inherits full anon/authenticated DML grants from Supabase default ACLs; safe only because RLS is enabled (no explicit REVOKE) | `backend/migrations/2026_10_11_lead_google_import.sql:34-38 (re-scoped to google_import_usage; seo_* dropped 2026-09-27)` | supabase-db | open (re-scoped 2026-10-29) |
| [SEC-068](findings/low.md#sec-068) | low | Per-account login lockout fails open on any Postgres error, leaving only per-instance in-memory throttling | `backend/auth_service/core/pg_rate_limit.py:40-55; routers/auth.py:79-96` | authn-session | open |
| [SEC-070](findings/medium.md#sec-070) | medium | Public booking `/{slug}/availability` omits the shared rate limiter; URL-keyed edge cache is trivially cache-busted → DB + external-calendar amplification DoS | `backend/auth_service/routers/booking.py:436-445,239-317` | ratelimit-dos | ✅ fixed (PR `security/fix-SEC-070-2026-10-10` → dev — `/{slug}/availability` now carries `Depends(_public_read_limit)` like every sibling public read; regression test added) |
| [SEC-071](findings/medium.md#sec-071) | medium | PreToolUse guard hooks never run for GitHub MCP write tools, so H1 "never push to main" is unenforced for `mcp__github__push_files/create_or_update_file/merge_pull_request` (Bash `git push origin main` is blocked); no branch protection on `main` (ADR-0007) | `.claude/settings.json:3-33; .claude/hooks/guard.mjs` | agents-guardrails | open |
| [SEC-072](findings/low.md#sec-072) | low | Booking `upload_logo` never sanitizes SVG and its deny-list is bypassable via content-type params/case → raw script-bearing SVG stored & served inline (isolated storage origin) | `backend/auth_service/routers/booking_admin.py:788-810` | uploads | open |
| [SEC-073](findings/low.md#sec-073) | low | Website-enrichment SSRF guard is TOCTOU-bypassable (DNS rebinding): validates one DNS resolution, urllib re-resolves and connects on a second (admin-gated Google-import path) | `backend/auth_service/services/google_places/website_enrich.py:129-171` | ssrf-outbound | open |
| [SEC-074](findings/info.md#sec-074) | info | `resolve.expand_short_link` follows redirects with no SSRF guard / no resolved-host re-validation (Google-shortener-gated, blind GET) | `backend/auth_service/services/google_places/resolve.py:68-75,90` | ssrf-outbound | open |
| [SEC-075](findings/low.md#sec-075) | low | `guard.mjs` PreToolUse hook bypassable by command re-shaping (env prefix, absolute path, `$(...)`, `$VAR`) → defeats H1/H2/H4 (requires a prompt-injected agent, SEC-016) | `.claude/hooks/guard.mjs:58-84,127-153,170-211` | agents-guardrails | open |
| [SEC-076](findings/low.md#sec-076) | low | Design-Prompt Phase 6 writes model/lead-derived content into a `$$…$$` UPDATE with only `&<>` escaped → dollar-quote breakout into service-role SQL (human-approval gated) | `agents/Design Prompt creator/phases/6-writeback.md:28-45` | agents-guardrails | open |
| [SEC-077](findings/info.md#sec-077) | info | Sessions renewed to full 30/60-day lifetime on every use with no absolute cap → a touched (or leaked) session token never self-expires | `backend/auth_service/services/sessions.py:91-100` | authn-session | open |
| [SEC-078](findings/info.md#sec-078) | info | Authenticated file-upload endpoints have per-file size caps but no per-user upload-frequency limit (storage-cost abuse within own tenant) | `backend/auth_service/routers/workspace.py:505; booking_admin.py:792` | ratelimit-dos | open |

> **⚠ Saturday Solver 2026-10-10 — note on SEC-069/070 provenance.** SEC-069 and SEC-070 are
> findings from the **2026-10-08 weekly review**, which lives on the unmerged
> `origin/security/weekly-review-2026-10-08` branch (its tracker, not this dev tracker, is the
> authoritative 2026-10-08 source). This dev tracker is still at the 2026-06-20 header. The rows
> added here record the Saturday-Solver fix status so it is not lost; a human reconciling the two
> trackers should keep both the authoritative review-branch rows and these fix-status rows.

## 2026-09-17 weekly review — fixes applied 2026-09-19 (⚠ ID reconciliation needed)

> **Heads-up for a human maintainer.** The unmerged `origin/security/weekly-review-2026-09-17`
> branch was cut from an older dev tip (`91d625b`) and its new-finding IDs (`SEC-057…SEC-064`)
> **collide** with this tracker's own `SEC-057…SEC-068` from the 2026-06-20 review — same numbers,
> different findings. The 2026-09-19 automated solver fixed the genuinely-present, still-open items
> from that review below, keeping the **2026-09-17 review IDs** in branch/PR/commit names. Please
> rebase + renumber the 2026-09-17 review branch onto current dev to remove the collision.
> (Independent security PRs from this run each touch this section — expect a trivial merge conflict;
> keep every row.)

| ID (2026-09-17) | Sev | Title | Location | Status |
|---|---|---|---|---|
| SEC-058 | medium | Legacy unauth booking `/availability` & `/slots` lacked the shared per-IP read limit; `/availability` range was unbounded (single-request CPU DoS) | `backend/auth_service/routers/booking.py` (legacy shims + `_availability_for_range`) | ✅ fixed (2026-09-19, PR `security/fix-SEC-058-2026-09-19`) |

_Also reconciled this run: **SEC-008** (scraper hash-pinned lockfile) — fixed on dev by #70
(`scraper/requirements.lock` + `requirements-dev.lock`; the `scraper-ci.yml` install path cited in the
finding was already deleted in the CI teardown). Row above updated to `fixed`._

## Dismissed (adversarially verified as false positives / non-issues)

Recorded so future reviews don't re-litigate them. See [`dismissed.md`](./dismissed.md).
