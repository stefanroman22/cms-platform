# Roman Technologies CMS — Full Security Audit

**Audit date:** 2026-05-07
**Scope:** entire repo at `stefanroman22/cms-platform` (master + dev) — frontend (Next.js 16), backend (FastAPI), agent (`CMS Connector — Website`), tests, GitHub Actions, Vercel hosting, Supabase migrations + config, dependencies, dev guidelines.
**Method:** seven independent read-only scans (secrets, backend code, frontend code, CI/CD, infra, dependencies, process/docs, tests) merged into this document.
**Output purpose:** drive a future implementation plan. Each finding has a concrete remediation that can be turned into a task.

---

## Executive summary

109 findings across 8 domains.

| Severity | Count |
|---|---|
| Critical | 1 |
| High | 15 |
| Medium | 28 |
| Low | 38 |
| Info | 27 |

| Domain | Critical | High | Medium | Low | Info | Total |
|---|---|---|---|---|---|---|
| Secrets | 0 | 3 | 1 | 1 | 1 | 6 |
| Backend (FastAPI) | 0 | 1 | 5 | 6 | 3 | 15 |
| Frontend (Next.js) | 0 | 1 | 1 | 6 | 3 | 11 |
| CI/CD (GH Actions + scripts) | 0 | 1 | 6 | 9 | 2 | 18 |
| Infra (Vercel + Supabase) | 0 | 2 | 4 | 6 | 3 | 15 |
| Dependencies | 0 | 4 | 5 | 2 | 5 | 16 |
| Process / Docs | 1 | 2 | 4 | 4 | 2 | 13 |
| Tests | 0 | 1 | 2 | 4 | 8 | 15 |

### Top 10 priorities (by severity + blast radius)

1. **PROC-001 (Critical)** — Public GitHub repo, secret scanning + push protection + Dependabot all disabled. History contains rotated leaks. Internet-grep-able.
2. **PROC-002 (High)** — Live Supabase PAT (`sbp_…`) in `.mcp.json` on disk, no documented rotation cadence.
3. **DEP-001 (High)** — Next.js 16.1.6: 6 advisories incl. CVSS 7.5 DoS via Server Components. Single non-major bump fixes.
4. **DEP-002 / DEP-003 (High)** — starlette 0.41.3 + python-multipart 0.0.20: 5 unauthenticated DoS / path-traversal CVEs. Bump FastAPI floor.
5. **CI-009 (High)** — `dev` branch is unprotected (no required checks, force-push allowed). Dev feeds master via Friday auto-merge.
6. **BE-002 (High)** — `/auth/login` has no rate limit. Argon2 cost is the only barrier vs credential stuffing.
7. **TEST-005 (High)** — `E2E_ADMIN_API_KEY` is a production-DB-scoped admin Bearer token used in CI integration tests. Mutates real `users`/`projects` rows every push.
8. **PROC-003 (High)** — No secret-scanning / SAST hooks in `.pre-commit-config.yaml`. Repeat of historical leak pattern is structurally unprevented.
9. **INFRA-002 (High)** — `frontend/next.config.ts` is empty: no HSTS, no CSP, no `X-Frame-Options`, no `Permissions-Policy` on the public CMS dashboard. Dashboard is currently click-jackable.
10. **INFRA-003 (High)** — `get_supabase()` and `get_supabase_admin()` are functionally identical: both use the service-role key. RLS is collapsed to a no-op for defense-in-depth.

### Suggested implementation phasing (for the future plan)

- **Phase S1 — Stop the bleeding (2–3 days):** PROC-001, PROC-002, PROC-003, DEP-001, DEP-002, DEP-003, CI-009, BE-002.
- **Phase S2 — Browser hardening (3–4 days):** INFRA-001, INFRA-002, FE-001, BE-008, FE-002, FE-003, FE-007, FE-008.
- **Phase S3 — Privilege boundary repair (5–7 days):** INFRA-003, BE-009, BE-010, INFRA-006, INFRA-007, BE-014, BE-015.
- **Phase S4 — Supply-chain + CI hardening (3–5 days):** DEP-004 through DEP-008, DEP-009, DEP-010, CI-002, CI-003, CI-010, CI-011, CI-013, CI-014, CI-018.
- **Phase S5 — Process + tests (3–4 days):** PROC-004 through PROC-013, TEST-002, TEST-003, TEST-005, TEST-010, BE-001, BE-003, BE-004, BE-005, BE-006.

---

## Format

Every finding follows the same shape so the implementation plan can scan them programmatically:

```
### [ID] one-line title
- Area:        domain
- Severity:    Critical | High | Medium | Low | Info
- Location:    path/to/file:line  OR  repo-config / git-history(<sha>) / repo-process
- Description: what was found
- Impact:      what an attacker (or operator slip) can do
- Remediation: concrete fix
- References:  CWE / OWASP / vendor link
```

---

## Critical findings

### [PROC-001] Public GitHub repo with secret scanning + push protection + Dependabot disabled

- **Area:** Process / Repo settings
- **Severity:** Critical
- **Location:** `repo-process` (`gh api repos/stefanroman22/cms-platform`)
- **Description:** `visibility: public`. `security_and_analysis` returns `secret_scanning: disabled`, `secret_scanning_push_protection: disabled`, `dependabot_security_updates: disabled`, `secret_scanning_validity_checks: disabled`. `vulnerability-alerts` and `automated-security-fixes` are also disabled. The repo's git history contains documented past leaks of a Supabase service_role JWT, the database password, and a Resend API key (per `docs/SECURITY.md` and `docs/superpowers/plans/2026-04-30-env-config-hygiene.md`).
- **Impact:** Anyone on the internet can grep the public history for credentials. Push-protection off means any future leak lands in the repo with no friction. No Dependabot means CVE patches don't auto-PR. The historical leaks are rotated, but the lack of scanning means the **next** one is a matter of time.
- **Remediation:** Either flip the repo to private (preferred for a B2B CMS holding client data) OR enable the four `security_and_analysis` flags + vulnerability alerts + automated security fixes. Do today.
  ```bash
  gh api -X PATCH repos/stefanroman22/cms-platform \
    -f security_and_analysis.secret_scanning.status=enabled \
    -f security_and_analysis.secret_scanning_push_protection.status=enabled \
    -f security_and_analysis.dependabot_security_updates.status=enabled \
    -f security_and_analysis.secret_scanning_validity_checks.status=enabled
  gh api -X PUT repos/stefanroman22/cms-platform/vulnerability-alerts
  gh api -X PUT repos/stefanroman22/cms-platform/automated-security-fixes
  ```
- **References:** OWASP SAMM Operations: Operational Management; NIST SSDF PO.5; GitHub docs — Securing your repository.

---

## High-severity findings (15 total — listed below)

### [SEC-001] Rotated Supabase `service_role` JWT in git history

- **Area:** Secrets
- **Severity:** High
- **Location:** `git history (SHA 21e1e2e3...)`, file `backend/auth_service/.env.example` (deleted at `e9dc5061`)
- **Description:** Commit `21e1e2e3` (2026-04-16) added a real Supabase `service_role` JWT for project `xeluydwpgiddbamysgyu`. Removed at `e9dc5061` (2026-04-30) and rotated per `docs/SECURITY.md`. The plain JWT is still in the history.
- **Impact:** Any clone of the public repo grants pre-rotation read/write to the whole Supabase instance, bypassing RLS. Mitigated by rotation.
- **Remediation:** Verify the legacy JWT secret has been rolled in Supabase dashboard so the historical token cannot be re-validated. Combined with PROC-001's repo-private flip, exposure is contained. History rewrite (`git filter-repo`) is documented as out of scope in `docs/SECURITY.md` — accept that decision but pair with PROC-001.
- **References:** CWE-798; OWASP A07:2021.

### [SEC-002] Rotated Postgres database password in git history + still inlined verbatim in a tracked plan doc

- **Area:** Secrets
- **Severity:** High
- **Location:** `git history (SHA 21e1e2e3...)` and `docs/superpowers/plans/2026-04-30-env-config-hygiene.md:19-20, 134, 182, 322`
- **Description:** Commit `21e1e2e3` embedded a literal Postgres password in `SUPABASE_DB_URL`. The same literal is also still inlined at four call sites in the env-hygiene plan markdown (committed to master). Rotated per `docs/SECURITY.md`.
- **Impact:** Password style + length leaks even though the value is dead — useful for credential-stuffing against other services Stefan uses with the same pattern.
- **Remediation:** Redact the literal in the plan doc to `Stefan**********!`. Add a standing rule in `docs/SECURITY.md`: "Plans, RFCs, post-mortems must redact secret values to ≤6-char prefix even after rotation." See PROC-013.
- **References:** CWE-200; CWE-256.

### [SEC-003] Rotated Resend API key in git history + tracked plan doc

- **Area:** Secrets
- **Severity:** High
- **Location:** `git history (SHA 21e1e2e3...)` and `docs/superpowers/plans/2026-04-30-env-config-hygiene.md:23, 153, 183`
- **Description:** Commit `21e1e2e3` added `RESEND_API_KEY=re_cENrXnX5_…` in `backend/auth_service/.env.example`. The literal key is also still in three places in the plan doc. Rotated.
- **Impact:** Pre-rotation, an attacker could send mail from `roman-technologies.dev`. Phishing potential.
- **Remediation:** Redact the literal to `re_cENrXnX5_*` in the plan doc (matching `docs/SECURITY.md`'s redaction discipline).
- **References:** CWE-798; OWASP A02:2021.

### [PROC-002] Live Supabase PAT in `.mcp.json`

- **Area:** Process / Onboarding
- **Severity:** High
- **Location:** `.mcp.json:9` (gitignored — verified via `git log -- .mcp.json` returns nothing)
- **Description:** `.mcp.json` contains a literal `sbp_867b69**REDACTED**` Supabase PAT. Gitignored, so not in git history. But sits plaintext on developer disk, reachable via MCP tool runs, screenshots, screen-sharing. No rotation entry for `sbp_*` in `docs/SECURITY.md`.
- **Impact:** Supabase PAT grants Management API access (project create / SQL / branches). One accidental upload, screenshot, or `cat` to chat = full Supabase account control.
- **Remediation:** (1) Rotate the PAT now; log the rotation in `docs/SECURITY.md`. (2) Document `.mcp.json` in `docs/ENVIRONMENTS.md` with rotation cadence (90 days). (3) Add `.mcp.json` to a pre-commit secret scanner (PROC-003).
- **References:** OWASP ASVS V14.1.

### [PROC-003] No secret-scanning / SAST hooks in `.pre-commit-config.yaml`

- **Area:** Process / Tooling
- **Severity:** High
- **Location:** `.pre-commit-config.yaml`
- **Description:** Hooks: ruff, ruff-format, black, generic file-hygiene, frontend lint-staged. No `gitleaks`, `detect-secrets`, `trufflehog`, `bandit` (Python SAST), `eslint-plugin-security`. Given the historical leak record (Pass A of the env-hygiene plan), this gap directly enables the recurrence pattern.
- **Impact:** A future contributor pasting a `re_*`, `sbp_*`, `cmsk_*`, `eyJ*` JWT, or DB password into a tracked file will not be stopped at commit time.
- **Remediation:** Add `gitleaks` (or `detect-secrets`) and `bandit -lll -r backend agents` as pre-commit hooks. Add `eslint-plugin-security` to the frontend ESLint config. Mirror the gitleaks scan in `.github/workflows/ci.yml` so PRs are gated.
  ```yaml
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.2
    hooks: [{ id: gitleaks }]
  ```
  Configure `.gitleaks.toml` to also flag the project-internal `cmsk_(dev|prod)_*` admin-key format.
- **References:** OWASP ASVS V14.3; OWASP SAMM Implementation: Secure Build; NIST SSDF PW.7.

### [BE-002] No rate limit on `/auth/login` — credential stuffing

- **Area:** Backend (FastAPI)
- **Severity:** High
- **Location:** `backend/auth_service/routers/auth.py:53-68`
- **Description:** `/auth/login` calls `authenticate_user(email, password)` with no `@limiter.limit(...)`. The only rate-limited route in the entire codebase is `/forms/<slug>/<form_key>`. argon2 cost provides ~300 ms of CPU per attempt — slows but does not stop a small distributed attack.
- **Impact:** Credential stuffing, password brute force, account enumeration via timing differences (the argon2 verify only runs on a hit; a missing email returns much faster).
- **Remediation:** Add `@limiter.limit("10/minute")` and a stricter per-email bucket (e.g. 5/hour keyed on `body.email`). Equalise timing for found-vs-not-found by always running an argon2 dummy verify on miss.
  ```python
  @router.post("/login", response_model=TokenResponse)
  @limiter.limit("10/minute")
  async def login(...): ...
  ```
- **References:** OWASP A07:2021; CWE-307.

### [FE-001] No HTTP security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)

- **Area:** Frontend (Next.js)
- **Severity:** High
- **Location:** `frontend/next.config.ts:1-7`, `frontend/src/middleware.ts:34-89`
- **Description:** No `headers()` block in `next.config.ts`, no header emission in middleware, no `frontend/vercel.json`. Default Vercel headers only.
- **Impact:** Without CSP, any future XSS sink (or compromised third-party script) executes with full privilege. Without `frame-ancestors` / `X-Frame-Options`, the dashboard can be framed by any origin and click-jacked into one-click admin actions (publish, delete, issue-edit) since `sid` cookie is sent on top-level POSTs in `SameSite=Lax` browsers. Without HSTS, downgrade attacks are possible.
- **Remediation:** Add a `headers()` async function to `next.config.ts`:
  ```ts
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "Strict-Transport-Security",   value: "max-age=63072000; includeSubDomains; preload" },
        { key: "X-Content-Type-Options",      value: "nosniff" },
        { key: "X-Frame-Options",             value: "DENY" },
        { key: "Referrer-Policy",             value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy",          value: "camera=(), microphone=(), geolocation=()" },
        { key: "Content-Security-Policy",     value: "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; frame-src https://www.youtube.com https://player.vimeo.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" },
      ],
    }];
  }
  ```
- **References:** OWASP Secure Headers; Next.js Headers config; CWE-1021; MDN HSTS.

### [INFRA-002] Frontend `next.config.ts` is empty — no security headers (related to FE-001)

- **Area:** Infra (Vercel)
- **Severity:** High
- **Location:** `frontend/next.config.ts:1-7`
- **Description:** Same root cause as FE-001 but called out separately because the fix touches the Vercel build config and may be deployed separately as part of an infra hardening pass.
- **Impact:** Same as FE-001.
- **Remediation:** See FE-001.
- **References:** OWASP ASVS 14.4.

### [INFRA-003] `get_supabase()` and `get_supabase_admin()` both use service-role key

- **Area:** Infra (Supabase)
- **Severity:** High
- **Location:** `backend/auth_service/services/supabase_client.py:9-26`
- **Description:** Both factories fall back to `SUPABASE_SERVICE_ROLE_KEY` first, anon key second. Across ~60 call sites in routers and `services/sessions.py`, every Supabase call bypasses RLS. The naming implies a privilege boundary that does not exist in code.
- **Impact:** Defense-in-depth is collapsed: any logic bug skipping a `require_project_access` check (e.g. INFRA-006) gives the attacker service-role-equivalent reach. RLS is enabled per the security spec, but provides zero protection because no caller ever uses the anon role.
- **Remediation:** Make `get_supabase()` use the anon key by default; reserve `get_supabase_admin()` for explicit admin operations. Audit every call site. At minimum, rename the factories so the privilege model is unambiguous.
  ```python
  def get_supabase() -> Client:
      return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

  def get_supabase_admin() -> Client:
      key = settings.SUPABASE_SERVICE_ROLE_KEY
      if not key:
          raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY required for admin client")
      return create_client(settings.SUPABASE_URL, key)
  ```
- **References:** Supabase RLS docs; CWE-272; OWASP A04:2021.

### [CI-009] `dev` branch unprotected — direct push / force-push possible

- **Area:** CI/CD
- **Severity:** High
- **Location:** `repo-config` (`gh api repos/.../branches/dev/protection` returns 404)
- **Description:** `dev` is the integration branch and the sole source of truth fed into `master` by the scheduled-merge workflow. No protection means any collaborator (or stolen PAT) can force-push, delete, or land arbitrary code on `dev`. After the next Friday merge (or manual `workflow_dispatch`) it reaches `master`.
- **Impact:** Tampered code in `dev` propagates to `master` after CI/E2E goes green. Workflow files themselves can be edited on `dev` (the scheduled-merge job runs from `master` so it's not immediately hijacked, but the tampered code reaches master next cycle).
- **Remediation:** Mirror master's protection on `dev`:
  ```bash
  gh api -X PUT repos/stefanroman22/cms-platform/branches/dev/protection \
    -f required_status_checks.strict=false \
    -f required_status_checks.contexts[]='Backend (FastAPI)' \
    -f required_status_checks.contexts[]='Agent (CMS Connector — Website)' \
    -f required_status_checks.contexts[]='Frontend (Next.js)' \
    -f required_status_checks.contexts[]='Backend integration (httpx → deployed FastAPI)' \
    -f required_status_checks.contexts[]='Frontend E2E (Playwright → deployed Next.js)' \
    -f enforce_admins=false \
    -f required_pull_request_reviews=null \
    -f restrictions=null \
    -f allow_force_pushes=false \
    -f allow_deletions=false
  ```
  Set `enforce_admins=false` on dev so emergency hotfixes by Stefan still flow.
- **References:** OWASP CI/CD Top 10 — CICD-SEC-1.

### [DEP-001] Next.js 16.1.6: 6 advisories (CVSS 7.5 DoS via Server Components + 5 more)

- **Area:** Dependencies
- **Severity:** High
- **Location:** `frontend/package.json:30`
- **Description:** Pinned `next@16.1.6`. `npm audit` flags six advisories on this exact version: GHSA-q4gf-8mx6-v5v3 (DoS, CVSS 7.5), GHSA-mq59-m269-xvcx (null-origin Server Actions CSRF bypass), GHSA-ggv3-7p47-pfv8 (HTTP request smuggling in rewrites), GHSA-3x4c-7xq6-9pq8 (unbounded next/image disk cache), GHSA-h27x-g6w4-24gq (postpone resume buffering), GHSA-jcc7-9wpm-mj36 (HMR websocket CSRF, dev only). Also drags vulnerable `postcss<8.5.10` (XSS GHSA-qx2v-qp2m-jg93).
- **Impact:** Public unauthenticated DoS against the production frontend; CSRF bypass on Server Actions; smuggling shenanigans; dev-time XSS. Anything on a public production frontend is high.
- **Remediation:** `cd frontend && npm install next@16.2.5 eslint-config-next@16.2.5`. Non-major bump per `npm audit`. Update `package.json` direct pins.
- **References:** GHSA-q4gf-8mx6-v5v3; GHSA-mq59-m269-xvcx; GHSA-ggv3-7p47-pfv8; GHSA-qx2v-qp2m-jg93.

### [DEP-002] starlette 0.41.3 — Range-header DoS + UploadFile blocking I/O

- **Area:** Dependencies
- **Severity:** High
- **Location:** `backend/requirements.txt:8` (transitive via `fastapi==0.115.6`)
- **Description:** Resolved `starlette==0.41.3`. CVE-2025-62727 (quadratic Range header parsing in `FileResponse`, fixed 0.49.1) and CVE-2025-54121 (multipart UploadFile blocks event loop on disk rollover, fixed 0.47.2). FastAPI 0.115.6 caps starlette `<0.42`, so the floor is stuck.
- **Impact:** Single crafted request pins a backend worker at 100% CPU. Multipart upload halts all concurrent traffic in the same worker.
- **Remediation:** Bump `fastapi==0.118.0` (or newer) in `backend/requirements.txt` so the starlette floor moves to ≥0.49.1. Re-run `pip-audit` to confirm.
- **References:** GHSA-7f5h-v6xp-fcq8; GHSA-2c2j-9gv5-cj73.

### [DEP-003] python-multipart 0.0.20 — 3 CVEs (path traversal + 2 DoS)

- **Area:** Dependencies
- **Severity:** High
- **Location:** `backend/requirements.txt:16`
- **Description:** Three advisories on the pinned version: CVE-2026-24486 (path traversal via `os.path.join` when `UPLOAD_DIR + UPLOAD_KEEP_FILENAME=True`, fixed 0.0.22), CVE-2026-40347 (preamble/epilogue parser DoS, fixed 0.0.26), CVE-2026-42561 (unbounded part-header count/size DoS, fixed 0.0.27).
- **Impact:** Unauthenticated CPU exhaustion on any FastAPI multipart endpoint; arbitrary file write if non-default options are set later.
- **Remediation:** Pin `python-multipart==0.0.27`. Must ship paired with the FastAPI bump (DEP-002), since FastAPI 0.115.x requires `<0.0.21`.
- **References:** GHSA-wp53-j4wj-2cfg; GHSA-mj87-hwqh-73pj; GHSA-pp6c-gr5w-3c5g.

### [DEP-005] minimatch / picomatch / flatted ReDoS chain (frontend transitives)

- **Area:** Dependencies
- **Severity:** High
- **Location:** `frontend/package-lock.json` (transitive)
- **Description:** Transitive dev/runtime deps flagged by `npm audit`: `minimatch <=3.1.3 || 9.0.0-9.0.6` (two ReDoS, CVSS 7.5), `picomatch <=2.3.1 || 4.0.0-4.0.3` (ReDoS GHSA-c2c7-rcm5-vvqj high; method-injection GHSA-3v7f-55p6-f55p moderate), `flatted <=3.4.1` (DoS GHSA-25h7-pfq9-p65f + prototype pollution GHSA-rf6f-7fwh-wjgh). All `fixAvailable: true`.
- **Impact:** Build-time DoS; not directly user-facing but matters for CI hygiene and developer machines.
- **Remediation:** `cd frontend && npm audit fix`. Lockfile updates only, no major bumps.
- **References:** GHSA-c2c7-rcm5-vvqj; GHSA-23c5-xmqv-rm74; GHSA-rf6f-7fwh-wjgh.

### [TEST-005] `E2E_ADMIN_API_KEY` is a production-DB-scoped admin Bearer token used by CI tests

- **Area:** Tests
- **Severity:** High
- **Location:** `backend/auth_service/tests_integration/test_admin_keys.py:13`, `test_admin_delegation.py:13`
- **Description:** `ADMIN_KEY = os.environ.get("E2E_ADMIN_API_KEY")` is a *production*-Supabase-bound admin token. Tests mutate the live DB: `test_create_then_delete_throwaway_project` creates real `projects` rows, `test_transfer_round_trip_on_e2e_test_project` actually transfers ownership, `test_create_client_writes_public_users_row` creates real `users` rows that are intentionally left behind. `e2e.yml` exposes the secret to any code running in `working-directory: backend`, including future tests not yet audited.
- **Impact:** Full admin scope. If the GitHub secret leaks (forked-PR exfil, malicious workflow modification, dependency postinstall reading env), an attacker has admin write to the production DB.
- **Remediation:** (1) Mint a least-privileged admin key scoped only to the e2e project. Today `scopes: ["agent"]` is unenforced — the backend doesn't check scopes. Add scope enforcement (BE-NEW finding) and limit this key. (2) Add cleanup for `test_create_client_writes_public_users_row` (build a `DELETE /admin/clients/{id}` if missing). (3) Restrict `E2E_ADMIN_API_KEY` to `environment: e2e` in GitHub so PR forks can't read it. (4) Verify integration suite runs only on `push` (not `pull_request`) — `e2e.yml:8-10` confirms this; document in the secret's metadata.
- **References:** GitHub Actions security hardening — secrets in `pull_request` events; OWASP ASVS V1.10.

---

## Medium-severity findings (28)

### [SEC-004] No automated secret-scanning hook (related to PROC-003)

- **Area:** Secrets
- **Severity:** Medium
- **Location:** `.pre-commit-config.yaml:1-39`
- **Description:** Pre-commit runs ruff/black/file-hygiene but no secret scanner. Repo history shows a real incident (SEC-001/002/003); that exact failure mode is unprevented today.
- **Impact:** Future contributor can re-introduce a live key into `.env.example` / a test / a doc and pre-commit passes. Detection then waits for GitHub secret scanning (currently disabled per PROC-001), which is too late.
- **Remediation:** See PROC-003. Add a `gitleaks` hook with `.gitleaks.toml` covering the project-internal `cmsk_(dev|prod)_*` format.
- **References:** OWASP ASVS V14.3.

### [BE-001] `submit_form` rate limit bypassable behind a proxy + not bound to project

- **Area:** Backend (FastAPI)
- **Severity:** Medium
- **Location:** `backend/auth_service/routers/forms.py:78-86`, `backend/auth_service/core/limiter.py:1-4`
- **Description:** Limiter `key_func=get_remote_address` reads `request.client.host` (immediate peer). Behind Vercel/Cloudflare this is the proxy IP; all submissions share one bucket. Limit also per-IP, not per `(project_slug, form_key)` — one attacker exhausts a victim project's quota.
- **Impact:** Either form-spam DoS for honest clients sharing an egress proxy, or unlimited submissions because the proxy IP rotates. Resend cost + spam.
- **Remediation:** Use X-Forwarded-For-aware key extraction, key bucket by `(project_slug, form_key, ip)`.
  ```python
  def _form_key(r: Request) -> str:
      ip = (r.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or get_remote_address(r))
      return f"{r.path_params['project_slug']}:{r.path_params['form_key']}:{ip}"
  @limiter.limit("5/10minutes", key_func=_form_key)
  ```
- **References:** OWASP API4; CWE-770; slowapi docs.

### [BE-003] No rate limit on `/auth/change-password`, all admin write endpoints, or `/project-requests`

- **Area:** Backend (FastAPI)
- **Severity:** Medium
- **Location:** `backend/auth_service/routers/auth.py:88-115`; `backend/auth_service/routers/workspace.py:429,467,496,640`; `backend/auth_service/routers/projects.py:66-101`
- **Description:** Every write endpoint except `/forms/{slug}/{form_key}` is unlimited. `/project-requests` floods admin inbox via Resend (PROC tie-in: project-request notification). `/admin/clients` POST issues argon2 hashes (CPU). `/auth/change-password` lets a session-holder brute-force the current password.
- **Impact:** Email spam, DB bloat, server CPU, current-password guessing.
- **Remediation:** `@limiter.limit("3/minute")` on every write touching email or argon2.
- **References:** OWASP API4; CWE-799.

### [BE-004] Mass assignment: `AdminProjectPatchIn` lets admin overwrite `preview_token`

- **Area:** Backend (FastAPI)
- **Severity:** Medium
- **Location:** `backend/auth_service/models/schemas.py:241-247`, `backend/auth_service/routers/workspace.py:415-426`
- **Description:** `AdminProjectPatchIn.preview_token: str | None`. `admin_patch_project` does `update_data = {k: v for k, v in body.model_dump().items() if v is not None}` then `.update()`. An admin (or stolen Bearer key) can set the preview token to a chosen value, bypassing the rotate flow's audit trail.
- **Impact:** Token fixation; `/content/{slug}/draft` exposed via attacker-known token. Also `production_url` / `preview_url` overwritable to phishing host that the welcome email links to.
- **Remediation:** Drop `preview_token` from the patch schema (rotate has its own endpoint). Validate URL fields as `AnyHttpUrl`.
- **References:** OWASP API6; CWE-915.

### [BE-005] Pydantic schemas accept unbounded strings in user-controlled fields

- **Area:** Backend (FastAPI)
- **Severity:** Medium
- **Location:** `backend/auth_service/models/schemas.py:4-7,22-28,54-59,101-109,149-151,261-275`
- **Description:** `LoginRequest.password`, `ChangePasswordRequest.new_password/current_password`, `ChangeNameRequest.full_name`, `ProjectRequestIn.name/description/budget_range/timeline`, `ServiceCreateRequest.service_type_slug/service_key/label/page_name`, `AdminProjectCreateIn.slug/name/github_repo`, `ProjectSettingsIn.website_url/allowed_origins[]`, `WelcomeEmailIn.project_slug/project_name/website_url` — bare `str` with no `max_length` or `pattern`. `service_key` regex enforced inside the route, not at schema layer. `AdminProjectCreateIn.slug` has zero validation despite being a URL/storage path component.
- **Impact:** (1) DoS via giant request bodies (argon2 still computes on multi-MB passwords); (2) `..` / `/` / NUL injection into slug paths reaching Supabase storage; (3) HTML injection in `WelcomeEmailIn.project_name` reaching the unescaped welcome template (BE-006).
- **Remediation:** Add `Field(max_length=…, pattern=r"…")` everywhere. Slugs `pattern=r"^[a-z0-9-]{1,64}$"`. Passwords `Field(min_length=8, max_length=256)`.
- **References:** OWASP API8; CWE-20; CWE-22.

### [BE-006] Welcome email template renders unescaped HTML

- **Area:** Backend (FastAPI)
- **Severity:** Medium
- **Location:** `backend/auth_service/services/welcome_email.py:18-35`, called from `routers/workspace.py:496-518`
- **Description:** `render_welcome_html` interpolates `full_name`, `project_name`, `website_url` directly. Compare `project_request_email.py:56-57` which has `_escape_html`. `website_url` and `project_name` come from admin-controlled `WelcomeEmailIn` (unvalidated); `full_name` is user-set on profile.
- **Impact:** User puts `"><script>` into `full_name` → renders verbatim in admin's email. Admin can put `javascript:` URL in `website_url` → "Open the dashboard" CTA becomes XSS in webmail clients that render `javascript:`.
- **Remediation:** Reuse `_escape_html` from `project_request_email.py` (or `markupsafe.escape`). Validate `website_url` at schema layer (BE-005).
- **References:** OWASP A03; CWE-79; CWE-80.

### [FE-002] Proxy route forwards client-controlled HTTP method without an allow-list

- **Area:** Frontend (Next.js)
- **Severity:** Medium
- **Location:** `frontend/src/app/api/[...path]/route.ts:6-31` (line 24: `method: request.method`)
- **Description:** Catch-all proxy exports GET/POST/PUT/PATCH/DELETE bound to one handler that forwards `request.method` verbatim. No per-route allow-list. Backend role checks are the only gate.
- **Impact:** Defense-in-depth gap. Removes a layer of "what can hit FastAPI from where". Not an immediate exploit since backend gates all admin routes.
- **Remediation:** Document this as deliberate, OR add per-route method allow-listing. Minimum: ensure tests cover that backend is the sole gate (TEST-006).
- **References:** OWASP API5:2023; Next.js Route Handlers.

### [INFRA-001] Backend Vercel project lacks security headers

- **Area:** Infra (Vercel)
- **Severity:** Medium
- **Location:** `backend/vercel.json`, `backend/auth_service/core/security_headers.py:1-31`
- **Description:** `backend/vercel.json` has no `headers` section. Middleware emits only `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff`. The middleware comment claims "HSTS is emitted by Vercel's edge layer" — but Vercel does NOT add HSTS automatically for serverless function responses on `*.vercel.app`. Backend hosted on the default subdomain (`cms-backend-roman.vercel.app`).
- **Impact:** No HSTS, no Permissions-Policy, no Referrer-Policy, no CSP on API responses. MITM downgrade possible on first connection; cookie-hijack surface widens.
- **Remediation:** Add `headers` to `backend/vercel.json` OR extend `SecurityHeadersMiddleware` to emit HSTS, Referrer-Policy, Permissions-Policy, and a baseline CSP `default-src 'none'; frame-ancestors 'none'` for API responses.
- **References:** OWASP Secure Headers; MDN HSTS; CWE-693.

### [INFRA-004] Public Supabase Storage bucket `cms-files` — no upload limits at storage layer

- **Area:** Infra (Supabase)
- **Severity:** Medium
- **Location:** `backend/auth_service/routers/workspace.py:35-269`, design ref `docs/superpowers/specs/2026-04-15-supabase-security-hardening-design.md:62-72`
- **Description:** Bucket `cms-files` is public; 50 MB cap and MIME allowlist enforced only in app code. No bucket-level `file_size_limit` or `allowed_mime_types`. Service-role-key paths could bypass app checks.
- **Impact:** If service-role leaks, oversize / wrong-type uploads land. `image/svg+xml` is in the MIME→ext map and served from a public URL → potential XSS via SVG.
- **Remediation:** Configure bucket-level `file_size_limit` and `allowed_mime_types` in Supabase. Exclude `image/svg+xml` or serve with `Content-Disposition: attachment`. Document the bucket config in a migration.
- **References:** Supabase Storage policies; OWASP File Upload; CWE-79 via SVG.

### [INFRA-006] `project_requests` insert via service role; future SELECT could be IDOR

- **Area:** Infra (Supabase)
- **Severity:** Medium
- **Location:** `backend/auth_service/routers/projects.py:66-101`
- **Description:** Inserts via service-role per INFRA-003. RLS enabled on `project_requests` per the hardening spec but no policies — anon role gets zero rows, fine. No "list my requests" endpoint today, so benign. Risk surfaces when a future endpoint adds `GET /project-requests` with app-layer-only `user_id` filter — a forgotten `.eq("user_id", user.id)` returns every client's submission.
- **Impact:** Future regression risk: client free-text descriptions, budgets, timelines exposable.
- **Remediation:** Add CHECK / RLS policy enforcing `user_id = auth.uid()` even though anon doesn't reach today — fail-closed on future code that uses anon.
- **References:** OWASP A01:2021; CWE-639.

### [INFRA-014] Public deployment URL `cms-backend-roman.vercel.app` exposes admin endpoints

- **Area:** Infra (Vercel)
- **Severity:** Medium
- **Location:** `backend/auth_service/main.py:110-115`, `backend/auth_service/routers/workspace.py:275-692`, `backend/auth_service/routers/publish.py:177-202`
- **Description:** All routers (`/admin/clients`, `/admin/projects/{slug}/rotate-preview-token`, etc.) on the public `cms-backend-roman.vercel.app`. Auth via session cookie or `cmsk_…` Bearer. No IP allowlist or VPN gate. `disable_vercel_auth.py` skips infra projects but doesn't verify deployment-protection is currently ON for them.
- **Impact:** If admin Bearer key leaks, the public endpoint accepts it globally with no second factor.
- **Remediation:** Defense-in-depth: confirm Vercel deployment-protection is ON for `cms-backend-roman` (read-only API check). Document in `docs/SECURITY.md`. Consider IP allowlisting `/admin/*` via Vercel firewall.
- **References:** OWASP A07:2021.

### [CI-002] First-party actions floating major-tag pinned, not SHA-pinned

- **Area:** CI/CD
- **Severity:** Medium
- **Location:** `.github/workflows/ci.yml:29,30,54,55,73,74`; `.github/workflows/e2e.yml:30,31,57,58,68`; `.github/workflows/scheduled-merge.yml:37`
- **Description:** Every `uses:` references `actions/checkout@v4` etc. — floating major tags. GitHub's hardening guidance recommends SHA-pinning even first-party actions because tag-overwrites are technically possible (March 2025 `tj-actions/changed-files` incident).
- **Impact:** Compromised maintainer / tag overwrite silently exfiltrates `secrets.GITHUB_TOKEN` and E2E secrets on next CI run.
- **Remediation:** Replace tags with full 40-char SHA + inline comment with the version: `uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1`. Pair with Dependabot `package-ecosystem: github-actions` (CI-010).
- **References:** GitHub docs — Security hardening for GitHub Actions; OWASP CI/CD Top 10 — CICD-SEC-3.

### [CI-003] No explicit top-level `permissions:` block on `ci.yml` and `e2e.yml`

- **Area:** CI/CD
- **Severity:** Medium
- **Location:** `.github/workflows/ci.yml`, `.github/workflows/e2e.yml`
- **Description:** Neither workflow declares `permissions:`. `GITHUB_TOKEN` defaults to repo-level "Workflow permissions" setting. Older repos default to read+write.
- **Impact:** A successful prompt-/script-injection in CI (e.g. malicious dep in `npm ci` / `pip install`) pushes commits, opens PRs, modifies releases under the Actions identity.
- **Remediation:** Add `permissions: contents: read` at top of both. Job-level overrides only if needed.
- **References:** GitHub docs — automatic-token-authentication.

### [CI-004] Pip installs without `--require-hashes`

- **Area:** CI/CD
- **Severity:** Medium
- **Location:** `.github/workflows/ci.yml:37,62`; `.github/workflows/e2e.yml:38`
- **Description:** `pip install -r requirements.txt -r requirements-dev.txt` resolves from public PyPI without hash pinning. Versions pinned, artefact hashes not.
- **Impact:** Compromised PyPI artefact runs in CI with full token scope and access to E2E secrets.
- **Remediation:** Generate hashed lockfiles via `pip-compile --generate-hashes` (pip-tools or uv). Run `pip install --require-hashes -r requirements.lock`. Pair with Dependabot.
- **References:** pip-secure-installs docs.

### [CI-010] No `.github/dependabot.yml` — security patches don't auto-PR

- **Area:** CI/CD
- **Severity:** Medium
- **Location:** `repo-config`
- **Description:** No Dependabot/Renovate config. CVE patches to `requirements.txt`, `package-lock.json`, GitHub Actions only land via manual `npm audit fix` / `pip install -U`. Combined with no hash pinning (CI-004), the attack window widens.
- **Impact:** Vuln deps linger; team must remember manual audits.
- **Remediation:** Add `.github/dependabot.yml`:
  ```yaml
  version: 2
  updates:
    - package-ecosystem: pip
      directory: "/backend"
      schedule: { interval: weekly }
    - package-ecosystem: pip
      directory: "/agents/CMS Connector - Website"
      schedule: { interval: weekly }
    - package-ecosystem: npm
      directory: "/frontend"
      schedule: { interval: weekly }
    - package-ecosystem: npm
      directory: "/e2e"
      schedule: { interval: weekly }
    - package-ecosystem: github-actions
      directory: "/"
      schedule: { interval: weekly }
  ```
- **References:** GitHub Dependabot docs.

### [CI-011] No secret-scanning hook in `.pre-commit-config.yaml` (duplicate of PROC-003)

- **Area:** CI/CD
- **Severity:** Medium
- **Location:** `.pre-commit-config.yaml`
- **Description:** Same as PROC-003 / SEC-004. Listed here for cross-domain visibility.
- **Remediation:** See PROC-003.

### [CI-013] `E2E_ADMIN_API_KEY` secret exists but is not referenced by any workflow

- **Area:** CI/CD
- **Severity:** Medium
- **Location:** `repo-secrets`; not found in any `.github/workflows/*.yml`
- **Description:** `gh secret list` shows `E2E_ADMIN_API_KEY` exists. Grep across `.github/workflows/` finds zero references. Integration tests in `backend/auth_service/tests_integration/` reference it via `os.environ` but the workflow `e2e.yml:23-28` env block doesn't plumb it through. Either tests run without admin coverage, or the secret is dead.
- **Impact:** Either part of the test surface is silently disabled, or an unused admin-power secret sits in repo settings inflating the rotation list.
- **Remediation:** Add `E2E_ADMIN_API_KEY: ${{ secrets.E2E_ADMIN_API_KEY }}` to the `backend-integration` env block in `e2e.yml`. Long-term replace with a least-privileged scoped key (TEST-005).
- **References:** OWASP CI/CD Top 10 — CICD-SEC-6.

### [DEP-004] python-dotenv 1.0.1 — symlink-following file overwrite

- **Area:** Dependencies
- **Severity:** Medium
- **Location:** `backend/requirements.txt:15`
- **Description:** CVE-2026-28684. `set_key()`/`unset_key()` follow symlinks via `shutil.move()` cross-device fallback. Local attacker with write to `.env` directory overwrites any file the process can write. Fixed 1.2.2.
- **Impact:** Local-only file overwrite. Limited on Vercel single-tenant containers.
- **Remediation:** Bump `python-dotenv==1.2.2`.
- **References:** GHSA-mf9w-mj56-hr94.

### [DEP-006] lint-staged 15.2.10 → vulnerable yaml 2.x stack-overflow (transitive)

- **Area:** Dependencies
- **Severity:** Medium
- **Location:** `frontend/package.json:47`
- **Description:** `lint-staged@15.2.10` pulls `yaml@2.0.0-2.8.2`, vulnerable to stack-overflow on deeply nested YAML (CVSS 4.3). Fix from `lint-staged@15.5.2`.
- **Impact:** Dev/precommit-time DoS.
- **Remediation:** Bump `"lint-staged": "15.5.2"`.
- **References:** GHSA-48c2-rrv3-qjmp.

### [DEP-007] black 24.10.0 — cache-path injection via --python-cell-magics

- **Area:** Dependencies
- **Severity:** Medium
- **Location:** `backend/requirements-dev.txt:12`, `.pre-commit-config.yaml:14-16`
- **Description:** CVE-2026-32274. `--python-cell-magics` value used unsanitized in cache filename. Fixed 26.3.1. Requires attacker-controlled black CLI args; nearly untriggerable in this repo's flow.
- **Impact:** Low real-world risk.
- **Remediation:** Bump to 26.3.1. Verify formatting drift with `make format` before merge (major version bump).
- **References:** GHSA-3936-cmfr-pm3m.

### [DEP-009] No hash-pinning on any Python requirements file (related to CI-004)

- **Area:** Dependencies
- **Severity:** Medium
- **Location:** All four `requirements*.txt` files
- **Description:** Exact `==` pins (good) but no `--require-hashes` or per-package `--hash=sha256:…`. Vercel `@vercel/python` resolves these on every deploy. `agents/CMS Connector - Website/requirements.txt:6` is non-exact: `python-dotenv>=1.0.0`.
- **Impact:** Supply-chain — poisoned upstream silently accepted.
- **Remediation:** `pip-compile --generate-hashes -o backend/requirements.lock backend/requirements.txt`. Tighten agent's `python-dotenv>=1.0.0` to `==1.2.2`.
- **References:** pip-secure-installs.

### [PROC-004] `dev` branch has no branch-protection (duplicate of CI-009)

- **Area:** Process / Branch protection
- **Severity:** Medium
- **Location:** `repo-process`
- **Description:** Same as CI-009. Listed here for process-doc visibility.
- **Remediation:** See CI-009.

### [PROC-005] `docs/SECURITY.md` lacks disclosure policy, threat model, incident-response runbook

- **Area:** Docs
- **Severity:** Medium
- **Location:** `docs/SECURITY.md`
- **Description:** Contains rotation log + 3-step "report a leak" stub. Missing: coordinated-disclosure policy with response SLA, threat model (assets, trust boundaries, STRIDE/abuse cases), incident-response runbook (severity ladder, communication plan, containment, post-mortem template), key-inventory matrix, rotation cadence. No root-level `SECURITY.md` (where GitHub auto-discovers).
- **Impact:** Reporter sees no "Security policy" tab on GitHub. On-call has no runbook during an incident — every step improvised. Long-lived credentials likely without cadence.
- **Remediation:** (1) Symlink `docs/SECURITY.md` to a root `SECURITY.md`. (2) Add Disclosure Policy + Threat Model + Incident Response + Rotation Cadence sections. (3) Cross-reference `docs/ENVIRONMENTS.md` per-tier secret matrix.
- **References:** ISO 27035; NIST SSDF PO.5; CVD ISO/IEC 30111.

### [PROC-006] No `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, or `LICENSE`

- **Area:** Docs
- **Severity:** Medium
- **Location:** `repo root`
- **Description:** Public repo without a license = default copyright; third parties can't reuse. No `CONTRIBUTING.md` = no documented onboarding for outside contributors.
- **Impact:** Legal ambiguity for forkers; security-sensitive guidance has no canonical home outside `docs/SECURITY.md`.
- **Remediation:** Add `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`. Low priority for security but matters for repo maturity.
- **References:** OpenSSF Best Practices.

### [PROC-007] Phase 6 instructs agent to handle plaintext credentials in chat

- **Area:** Docs / Agent process
- **Severity:** Medium
- **Location:** `agents/CMS Connector - Website/phases/6-confirmation.md:21-23, 8`
- **Description:** Step 6.2: "If created: true, capture `generated_password` — this is the **one and only chance** to read it. Never log it to disk." But no instruction on how the agent surfaces it without it landing in the conversation transcript (which is on disk in the agent runtime). Step 6.0 says `RESEND_API_KEY` may be prompted from the user inline if missing. `LEARNINGS.md:41` documents `curl --data-binary @file.json` to bypass Cloudflare — credentials in `/tmp/*.json` with no documented secure-temp-file practice.
- **Impact:** Generated client passwords land in agent transcripts and (for the curl flow) in `/tmp/*.json` files that may persist after Phase 6.5 cleanup if cleanup errors. Inline Resend key prompt lands in shell history.
- **Remediation:** (1) Phase 6 should rely on welcome email for password delivery (already implemented) — surface only "password sent via email" in chat. (2) `tempfile.NamedTemporaryFile(delete=True)` + explicit shred/wipe on cleanup. (3) Disallow inline secret prompts; halt with "set the env var and re-run".
- **References:** OWASP ASVS V2.1.6; NIST SP 800-63B.

### [TEST-001] E2E tests share single user/admin in `cms-test.dev` — no per-spec isolation

- **Area:** Tests
- **Severity:** Medium
- **Location:** `e2e/tests/02-login.spec.ts`, `e2e/tests/05-cms-edit.spec.ts`, `e2e/tests/06-publish.spec.ts`, `e2e/helpers/cleanup.ts`
- **Description:** All Playwright + integration specs share two long-lived users + one project. `playwright.config.ts` has `fullyParallel: false` + `workers: 1` but every push runs the same login → save → publish loop against the live deployment.
- **Impact:** Shared fixture means flaky test or renamed seed key leaves project broken (publicly visible). Knowing the workflow file = knowing the test domain → can spam `/auth/login` with that email or submit forms. No data-layer concurrency lock — two simultaneous workflows clobber `resetSeedState`.
- **Remediation:** Either spin up a separate test-tier backend, or document a per-run UUID suffix for write-heavy specs, or add `concurrency: e2e-shared, cancel-in-progress: false` to `e2e.yml`.
- **References:** OWASP Testing Guide WSTG-IDNT-04.

### [TEST-002] Integration tests fire real Resend emails on every push

- **Area:** Tests
- **Severity:** Medium
- **Location:** `backend/auth_service/tests_integration/test_forms.py:6-17`, `test_admin_delegation.py:120-132`
- **Description:** `/forms/e2e-test-project/e2e_contact_form` POSTs against the live backend; seed routes the submission to `e2e-user@cms-test.dev` → real Resend send. `test_welcome_email_send` also fires real Resend send (gated only on `E2E_ADMIN_API_KEY`).
- **Impact:** Each merge fires real emails. `workflow_dispatch` reachable → attacker can spam test inbox or burn Resend monthly quota.
- **Remediation:** Backend recognises `[E2E-TEST]` prefix in body and short-circuits Resend in `ENVIRONMENT=preview`. Or `pytest.mark.skipif(os.environ.get("E2E_ALLOW_EMAIL") != "1", ...)`.
- **References:** Resend rate-limit docs; OWASP ASVS V11.1.4.

---

## Low-severity findings (38)

Each entry is compressed: one paragraph + remediation. Same `[ID]` scheme.

### [SEC-005] Plan doc reproduces full historical secret literals (rotated)
- Location: `docs/superpowers/plans/2026-04-30-env-config-hygiene.md:19-23, 134, 153, 182-183, 322`
- Plan inlines literal rotated secrets (`Stefan…`, `re_cENrXnX5_…`, `eyJhbG…`). `docs/SECURITY.md` already redacts to a prefix. Inconsistency with security-log discipline.
- **Fix:** Redact to first-6-chars + `*`. Add standing rule in `docs/SECURITY.md`: "Plans must redact secret values to ≤6-char prefix even after rotation." See PROC-013 (the same finding from process scope).
- Refs: CWE-200.

### [BE-007] `list_services` 500 leaks raw exception text
- Location: `backend/auth_service/routers/workspace.py:122-124`, `forms.py:195`
- `raise HTTPException(500, detail=str(exc))` returns supabase-py / network error verbatim. Internal table names, SQL constraints, Resend error JSON leak to client.
- **Fix:** Log exception (already done) but return `HTTPException(500, "Internal error") from exc`.
- Refs: OWASP A05; CWE-209.

### [BE-008] Session cookie `SameSite=Lax` + `secure=False` in dev/preview
- Location: `backend/auth_service/routers/auth.py:29-39`
- `samesite="strict" if IS_PROD else "lax"`, `secure=IS_PROD`. Combined with permissive dev CORS regex (`*.vercel.app`) and `IS_PROD = ENVIRONMENT == "production"`, **preview** environment gets dev cookie semantics. Cookies travel over plain HTTP if any preview is reached via `http://`.
- **Fix:** `secure=settings.ENVIRONMENT in ("production", "preview")`. Consider `samesite="strict"` for preview too. Stop conflating production with everything-else via `IS_PROD`.
- Refs: OWASP A07; CWE-614.

### [BE-009] `_admin_client` cache shares state with `_client`; service-role key always used (related to INFRA-003)
- Location: `backend/auth_service/services/supabase_client.py:9-26`
- Same root cause as INFRA-003. Two factories, no actual privilege separation. Listed here for backend-domain visibility.
- **Fix:** See INFRA-003.

### [BE-010] No RLS policies on `users` / `sessions` / `projects` / `content_entries`
- Location: `backend/migrations/*.sql`
- Only `admin_api_keys` has `ENABLE ROW LEVEL SECURITY` (with no `CREATE POLICY` — default-deny for non-service roles). All other tables have no RLS. App-layer is sole defense.
- **Fix:** Apply RLS + per-table policies:
  ```sql
  ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
  CREATE POLICY p_owner ON projects FOR SELECT USING (user_id = auth.uid());
  -- repeat for sessions, content_entries, project_issues, etc.
  ```
- Refs: Supabase RLS docs; OWASP A01:2021.

### [BE-011] Admin Bearer auth not rate-limited; format-validity timing leak
- Location: `backend/auth_service/services/admin_keys.py:69-110`
- Lookup is fast + argon2-verify is constant time on the lookup row (good). But (a) no rate limiting on `admin_user_via_bearer_or_sid` — attacker can hammer guesses, and (b) malformed-key fast-path returns 401 visibly faster than a properly-formatted-but-wrong key, leaking format validity. ~2^192 brute-force is infeasible regardless.
- **Fix:** Rate-limit the bearer path. Optional: dummy argon2 verify on parse-fail to normalise timing.
- Refs: OWASP A07; CWE-208.

### [BE-012] CORS regex allows `192.168/16` LAN range in dev
- Location: `backend/auth_service/main.py:38, 55-57`
- Dev regex `http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})` allows ANY `192.168.x.y` — including a malicious LAN neighbour on the same Wi-Fi. Combined with `samesite=lax` in dev (BE-008), credentialed cross-origin requests succeed.
- **Fix:** Drop the LAN range. Allow only `localhost` / `127.0.0.1`.
- Refs: OWASP A05; CWE-942.

### [FE-003] Proxy doesn't normalise/strip path-traversal segments
- Location: `frontend/src/app/api/[...path]/route.ts:7-10`
- `path: string[]` from catch-all + `path.join("/")` + `request.nextUrl.search`. Raw `..` is normalised by Next.js routing, but URL-encoded `%2e%2e` may survive into `path[]`. fetch later normalises, but the upstream path may not match what FastAPI authorisation expects.
- **Fix:** Reject path segments containing `..`, `.`, or that decode to those. Build upstream URL with `new URL(targetPath, FASTAPI_URL)` and assert no `..`.
- Refs: OWASP — Path Traversal; CWE-22.

### [FE-004] `FASTAPI_URL` defaults to `http://localhost:8001` in production code paths
- Location: `frontend/src/app/api/[...path]/route.ts:4`, `frontend/src/middleware.ts:5`
- `FASTAPI_URL ?? "http://localhost:8001"`. If env unset in prod, app silently issues calls to `http://localhost:8001`. Not currently SSRF-vulnerable (server-only, not user-controlled), but operationally a footgun.
- **Fix:** Throw at startup if unset in production: `if (process.env.NODE_ENV === "production" && !process.env.FASTAPI_URL) throw …`.
- Refs: OWASP SSRF; 12-factor config.

### [FE-005] Proxy forwards `cookie` + `content-type` only — no `X-Forwarded-For` plumbed through
- Location: `frontend/src/app/api/[...path]/route.ts:12-17`
- Only `cookie` + `content-type` forwarded (good — strips host/x-forwarded-* injection surface). But `X-Forwarded-For` is not forwarded either, so backend sees Vercel edge IP; future per-IP rate limit at backend won't see real client.
- **Fix:** When backend rate-limit is added (BE-002, BE-003), forward a single trusted `X-Forwarded-For` derived from `request.ip`. Reject any client-supplied value.
- Refs: OWASP Proxies cheat-sheet.

### [FE-007] Dynamic `<a href={url}>` accepts admin-controlled URLs without scheme validation
- Location: `frontend/src/components/dashboard/editors/FileDownloadEditor.tsx:42-46`, `frontend/src/app/dashboard/page.tsx:118-127`, `frontend/src/app/dashboard/[projectSlug]/page.tsx:170-194`
- Several CMS-controlled `url` fields rendered as `<a href={url}>` (and `iframe src={embedUrl}` in `VideoEditor`) without checking scheme. A malicious admin can store `javascript:alert(document.cookie)` → click on "Open website" becomes self-XSS. `rel="noopener noreferrer"` doesn't block `javascript:`.
- **Fix:** Add `safeHref(u)` helper:
  ```ts
  function safeHref(u: string) {
    try { const x = new URL(u); return ["http:","https:","mailto:","tel:"].includes(x.protocol) ? u : "#"; }
    catch { return "#"; }
  }
  ```
  Use in all dynamic-href positions.
- Refs: OWASP XSS Prevention.

### [FE-008] `window.open(url, "_blank", ...)` with admin-supplied `preview_url`
- Location: `frontend/src/components/dashboard/PreviewPublishBar.tsx:130-142`
- `status.preview_url` from backend (admin-configured) passed to `window.open` unchecked. Same `javascript:` concern as FE-007. Modern browsers refuse `javascript:` in `window.open` but older mobile webviews don't.
- **Fix:** Validate with `new URL()` and require `http:`/`https:` before `window.open`.
- Refs: MDN Window.open; OWASP XSS prevention.

### [FE-011] File upload UI has no client-side type/size validation
- Location: `frontend/src/components/dashboard/editors/{ImageEditor,GalleryEditor,VideoEditor,FileDownloadEditor}.tsx`, plus the upstream call in `[serviceKey]/page.tsx:56-70`
- `accept="image/*"` set on three of four uploaders (trivially bypassable). `FileDownloadEditor` accepts any MIME. None check `file.size` / magic bytes / max upload size before POSTing multipart. `file.name` stored verbatim, used as download label (JSX-escaped on display, fine to render — but stored unsanitised).
- **Fix:** Before `onUpload(file)`: enforce `MAX_BYTES`, `file.type` matches explicit allow-list (`image/png|jpeg|webp|gif`), strip non-printable / control chars from filename, reject `..` / `/`. Backend must replicate.
- Refs: OWASP Unrestricted File Upload; CWE-434.

### [INFRA-005] Migrations not idempotent — missing `IF NOT EXISTS`/`IF EXISTS`
- Location: `backend/migrations/2026_04_16_draft_publish_split.sql:4-13`, `backend/migrations/2026_04_22_sessions_rename.sql:6, 11-13`
- `ALTER TABLE … RENAME COLUMN`, `ADD COLUMN`, `RENAME TO` lack guards. Re-running fails. Only `2026_05_06_admin_api_keys.sql` uses `IF NOT EXISTS`. No migrations-table tracking.
- **Fix:** Wrap each migration in a transaction. Add `IF EXISTS`/`IF NOT EXISTS` guards. Adopt Supabase CLI / Alembic, or document append-only manual application.
- Refs: Postgres ALTER TABLE; 12-factor §V.

### [INFRA-007] `SUPABASE_SERVICE_ROLE_KEY` not enforced at startup — silent fallback to anon
- Location: `backend/auth_service/core/config.py:20`, `backend/auth_service/services/supabase_client.py:14, 24`
- `SUPABASE_SERVICE_ROLE_KEY: str = ""`. Misconfigured in Vercel prod = silent fall to anon key. RLS denies anon → app silently empty. No model_validator enforcing this in production (mirror the `FRONTEND_ORIGINS` validator at line 38-46).
- **Fix:** Add `model_validator` requiring service-role key when `ENVIRONMENT in ("preview", "production")`.
- Refs: 12-factor §III.

### [INFRA-008] Forms sub-app `allow_origins=["*"]` — relies on per-row origin check that allows all if empty
- Location: `backend/auth_service/main.py:131-138`, `backend/auth_service/routers/forms.py:100-108`
- `/forms/*` mount accepts cross-origin from anywhere. App-layer check `if allowed_origins and origin not in allowed_origins`: a project with empty `allowed_origins` accepts submissions from anywhere.
- **Fix:** Make `allowed_origins` required at project creation, OR change to `if origin not in (allowed_origins or [])` to deny by default.
- Refs: OWASP CSRF; CWE-352.

### [INFRA-009] `disable_vercel_auth.py` fail-open default for projects with no `link`
- Location: `scripts/disable_vercel_auth.py:67-75`
- Per design, projects with no `link` → "treated as non-infra unless name matches denylist" → default action is to PATCH them public. New infra projects added without updating `INFRA_NAMES` will be silently exposed.
- **Fix:** Invert default: skip projects without `link.repo == INFRA_REPO`. Require `--allow-unlinked` opt-in to PATCH.
- Refs: Defense-in-depth; fail-closed principle.

### [INFRA-012] `ENVIRONMENTS.md` config drift vs backend `Settings`
- Location: `docs/ENVIRONMENTS.md:18-31`, `backend/auth_service/core/config.py:15-32`
- `Settings` reads `SUPABASE_DB_URL` (`config.py:22`) — `ENVIRONMENTS.md:26` calls it "optional". `routers/publish.py:119` reads `VERCEL_TOKEN` — NOT documented in `ENVIRONMENTS.md` at all.
- **Fix:** Add `VERCEL_TOKEN` to `docs/ENVIRONMENTS.md` Backend env table with a note that it's required for the rotate-preview-token admin endpoint.
- Refs: 12-factor; "fail-loud" principle.

### [INFRA-015] `CMS_PREVIEW_TOKEN` rotation silently no-ops when `VERCEL_TOKEN` missing
- Location: `backend/auth_service/routers/publish.py:112-130, 162-174`
- `_update_vercel_preview_env_var` returns early on missing `VERCEL_TOKEN` and on any HTTPError, with no logging. DB token rotates but Vercel env doesn't follow. Endpoint returns 200 with the new token regardless.
- **Fix:** Return structured response distinguishing `db_rotated` from `vercel_synced`, OR fail loud when `VERCEL_TOKEN` is unset. At minimum, log at WARN in both early-return branches.
- Refs: "Fail loud"; OWASP A09:2021.

### [CI-001] `workflow_dispatch` unrestricted on all three workflows
- Location: `.github/workflows/{ci,e2e,scheduled-merge}.yml`
- Anyone with write access can hand-trigger any workflow. For `scheduled-merge.yml` that means triggering `dev → master` fast-forward at any time, bypassing the Friday cadence.
- **Fix:** For `scheduled-merge.yml`, drop `workflow_dispatch` or restrict via an environment with required reviewers (`environment: production-merge`).
- Refs: GitHub deployment-environment docs.

### [CI-005] `npm ci` runs without `--ignore-scripts`
- Location: `.github/workflows/ci.yml:79`, `.github/workflows/e2e.yml:63`
- `npm ci` verifies lockfile integrity (good) but postinstall scripts run with full env access. Compromised transitive dep reads `process.env.E2E_*`.
- **Fix:** Add `--ignore-scripts` to `npm ci`. Selectively allow scripts via `package.json` `scripts.preinstall` if needed.
- Refs: npm ci docs; postinstall-script supply-chain history.

### [CI-006] Playwright browser binary install — informational only
- Location: `.github/workflows/e2e.yml:64`
- `npx playwright install --with-deps chromium` — Playwright validates a per-version SHA on the download. Pinned via `@playwright/test 1.59.1` in lockfile. No action.
- **Fix:** None required. Optional: cache `~/.cache/ms-playwright` keyed by Playwright version.
- Refs: Playwright Browsers docs.

### [CI-007] `scheduled-merge.yml` shell interpolation safety
- Location: `.github/workflows/scheduled-merge.yml:60-70`
- `for WORKFLOW in "CI" "E2E"; ... gh api "...select(.name == \"$WORKFLOW\")...`. `$WORKFLOW` is loop literal. `${{ github.repository }}` repo-owned. `$DEV_SHA` is a 40-char hex. No injection vector.
- **Fix:** None required. Quote `"${DEV_SHA}"` for hygiene.
- Refs: GitHub SecurityLab — untrusted-input.

### [CI-012] Pre-commit hooks pinned by tag, not SHA
- Location: `.pre-commit-config.yaml:7,14,19`
- `rev: v0.7.4`, `24.10.0`, `v5.0.0`. Tags can be force-pushed.
- **Fix:** `pre-commit autoupdate --freeze` rewrites `rev:` to a 40-char SHA.
- Refs: pre-commit docs.

### [CI-014] E2E secrets at job-level env (broad scope)
- Location: `.github/workflows/e2e.yml:23-28, 49-55`
- `E2E_*` secrets exposed at job level — every step (including `npm ci`, `pip install`) runs with these in `process.env`. Compromised dep with postinstall reads them.
- **Fix:** Move `env:` blocks down from job-level to step-level on test invocations. Or set `npm_config_ignore_scripts=true` job-wide.
- Refs: GitHub Actions security hardening.

### [CI-015] `seed_e2e.py` builds SQL via f-string interpolation
- Location: `scripts/seed_e2e.py:132-138, 144-157, 202-225`
- Builds SQL via f-string against Supabase Management `/database/query` (no bound parameters). Currently safe — interpolated values are UUIDs / module constants / escaped JSON. Risk on future modification.
- **Fix:** Add a CI lint rule flagging new f-string SQL in `scripts/`. Consider switching to psycopg.
- Refs: OWASP A03:2021.

### [CI-017] `smoke_admin_*.py` reads `CMS_ADMIN_API_KEY` from a file path, not env
- Location: `scripts/smoke_admin_endpoints.py:19, 24-32`; `scripts/smoke_admin_writes.py:30, 36-43`
- Reads from `agents/CMS Connector - Website/.env` rather than env vars. Filesystem-bound secrets risk accidental commit.
- **Fix:** Refactor to `os.environ.get("CMS_ADMIN_API_KEY")` and let operator source `.env`.
- Refs: CICD-SEC-6.

### [CI-018] No CodeQL / SAST workflow
- Location: `repo-config`
- No `.github/workflows/codeql.yml`. Free for public repos.
- **Fix:** Add CodeQL workflow with `python` and `javascript` languages, on `push` + `schedule`.
- Refs: GitHub Code scanning.

### [DEP-008] pytest 8.3.3 — predictable `/tmp/pytest-of-{user}` (Linux)
- Location: `backend/requirements-dev.txt:7`, `agents/CMS Connector - Website/requirements-dev.txt:3`
- CVE-2025-71176; fixed 9.0.3. Local privesc/DoS via predictable temp dir on UNIX. Negligible risk on GitHub Actions runners.
- **Fix:** `pytest==9.0.3`, `pytest-asyncio==1.3.0`. Re-run suite for minor API removals.
- Refs: GHSA-6w46-j5rx-g56g.

### [DEP-010] Pre-commit hooks tag-pinned, not SHA-pinned (related to CI-012)
- Location: `.pre-commit-config.yaml:7,14,19`
- Same as CI-012. Listed here for dependency-domain visibility.
- **Fix:** See CI-012.

### [PROC-008] `agents/CMS Connector - Website/.env.example` lacks revocation/rotation guidance for `CMS_ADMIN_API_KEY`
- Location: `agents/CMS Connector - Website/.env.example:19-20`
- "Lost = mint a new one" but no revocation, expected lifetime, blast radius, or compromise procedure documented. Other vars (GITHUB/VERCEL/ANTHROPIC) link to issuer revocation pages.
- **Fix:** Extend each `.env.example` line with required scopes, expected lifetime, "If compromised: …" line pointing at `docs/SECURITY.md`, explicit revocation URL/procedure for `CMS_ADMIN_API_KEY`.
- Refs: OWASP ASVS V2.10.

### [PROC-009] `README.md` security section is two lines and missing operational pointers
- Location: `README.md:93-96`
- Two lines: rotation log link + reporting email. Doesn't link `docs/ENVIRONMENTS.md`, doesn't repeat "no public issue" rule, no PGP key, no SLA.
- **Fix:** Expand to ~10 lines: link `docs/ENVIRONMENTS.md`, restate disclosure rule, add Reporting subheader with response SLA, link branch-protection docs.
- Refs: OpenSSF Scorecard (Security-Policy check).

### [PROC-010] `docs/SECURITY.md` "Standing rules" implicitly accepts historical leaks
- Location: `docs/SECURITY.md:28-29`
- "Past commits cannot be sanitized without rewriting git history." Doesn't enumerate WHICH commits / WHICH secrets remain. Future incident responder must re-derive.
- **Fix:** Either accept residual risk explicitly with a list of "known-leaked commits" (sha + secret kind + rotation date), OR perform a one-time `git-filter-repo` cleanup with coordinated reclone.
- Refs: GitHub docs — Removing sensitive data.

### [PROC-013] Plan doc reproduces verbatim leaked secret values (duplicate of SEC-005)
- Location: `docs/superpowers/plans/2026-04-30-env-config-hygiene.md:20, 134, 182`
- Same as SEC-005. Listed here for process-doc visibility.
- **Fix:** See SEC-005.

### [TEST-007] `mock_supabase` fixture silently skips missing patch targets
- Location: `backend/auth_service/tests/conftest.py:54-60`
- Each `patch(target).start()` wrapped in `try/except (ModuleNotFoundError, AttributeError): continue`. Future router renaming `get_supabase` silently no-ops the patch; with CI env vars present, real DB writes happen.
- **Fix:** After the loop, assert at least one patch applied per known router module: `assert any("workspace" in t for t in started_targets)`. Refactor to explicit allow-list.
- Refs: unittest.mock docs.

### [TEST-008] `auth_as` fixture monkeypatch silently swallows AttributeError
- Location: `backend/auth_service/tests/conftest.py:104-127`
- `monkeypatch.setattr("auth_service.routers.publish.require_user", fake)` and `routers.projects.require_user` wrapped in `try/except (AttributeError, ImportError)`. Future refactor that renames the function leaves real auth dep in place — test continues passing with mocked-out dep semantics flipped.
- **Fix:** Replace silent except with explicit list of required patch targets that must succeed. `monkeypatch.setattr(..., raising=False)` only on truly-optional ones.
- Refs: pytest monkeypatch docs.

### [TEST-009] `e2e/helpers/cleanup.ts` doesn't run cleanup for 01/03/04/07 specs
- Location: `e2e/tests/05-cms-edit.spec.ts:6-12`, `06-publish.spec.ts:6-12`, `e2e/helpers/cleanup.ts:24-44`
- `resetSeedState` runs in `afterEach` for 05 + 06. If `getSidCookie` itself fails, `afterEach` throws; next spec runs against unreset project. Tests 01/03/04/07 have no `afterEach` — if any future writes are added there, no cleanup.
- **Fix:** Wrap `resetSeedState` in try/finally with telemetry. Add Playwright `globalTeardown` that always runs reset.
- Refs: Playwright globalTeardown.

### [TEST-010] Playwright traces / screenshots / videos retained on failure capture sid + form passwords
- Location: `e2e/playwright.config.ts:19-22`, `e2e.yml:67-72`
- `trace: "retain-on-failure"`, `video: "retain-on-failure"`, artifact uploaded with 7-day retention. Playwright traces include cookies (`sid` HttpOnly cookie captured). If a test fails *during* login, the trace contains the live `E2E_USER_PASSWORD` keystroke-by-keystroke.
- **Fix:** Use Playwright's `mask` option for sensitive fields. Reduce trace level to `on-first-retry` only. Restrict artifact uploads to private repos with strict role-based access. Rotate `E2E_USER_PASSWORD` after every leaked-artifact incident.
- Refs: Playwright tracing — sensitive-data masking.

---

## Info-severity findings (27)

### [SEC-006] Internal admin-API-key sentinel in test fixtures (intentional)
- `cmsk_dev_aaaaaaaaaaaaaaaa_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz` etc. — deliberately invalid. Note in `docs/SECURITY.md` that `aaaa…`/`zzzz…` are sentinel values so future secret scanners can be tuned to ignore them.

### [BE-013] `/content` endpoints set wildcard `Access-Control-Allow-Origin: *`
- `routers/content.py:103-122,184-190,230-232` — handler-level `*` injection plus middleware. Wildcard + credentials would be browser-rejected, so harmless. Header duplication only.
- **Fix:** Remove manual `*` from content.py, rely on CORSMiddleware regex (already covers `*.vercel.app`).

### [BE-014] `admin_get_project` returns long-lived `preview_token`
- `routers/workspace.py:397-412`, `models/schemas.py:250-258`. `AdminProjectDetailOut` exposes `preview_token`. Admins need it but it leaks into error reports / proxy logs. Rotate endpoint already returns it once correctly.
- **Fix:** Drop `preview_token` from `AdminProjectDetailOut`. Force admins to rotate to see it.

### [BE-015] No CSRF token on cookie-authenticated mutations
- All cookie-auth POST/PATCH/DELETE routes. Production protection rests entirely on `SameSite=Strict`. Dev/preview uses `Lax` and is bypassable via top-level form POSTs.
- **Fix:** Add an `Origin` allowlist check in `require_user` (compare against CORS regex). Or implement double-submit CSRF token, especially given BE-008.

### [FE-006] Login page has no client-side rate-limit / back-off
- `frontend/src/app/log-in/page.tsx:34-56`. Backend brute-force protection is the right place; UX-level back-off would also help.
- **Fix:** Optional: disable submit for N seconds after 3 failures. Confirm backend lockout (BE-002).

### [FE-009] Auth uses HttpOnly cookies — no localStorage/sessionStorage tokens (positive)
- `frontend/src/lib/auth.ts:13-59`. `localStorage` only stores `dashboard-theme`. `document.cookie` never written from client. `credentials: "include"` for all `/api/*` calls (same-origin via proxy). CSRF mitigation via SameSite=Lax.
- **Action:** Maintain pattern. Optional: add CSRF double-submit token on mutating `/api/*` for older iOS browsers.

### [FE-010] No `dangerouslySetInnerHTML`/markdown sinks (positive)
- `TextBlockEditor`, `RepeaterEditor`. Markdown stored as plain text, rendered with JSX text interpolation only (escaped). Zero `dangerouslySetInnerHTML`, `innerHTML=`, `eval`, `Function`, `setTimeout(string,…)`.
- **Action:** Maintain a project rule (lint or PR review) banning `dangerouslySetInnerHTML` in `frontend/src/`.

### [INFRA-010] Database password rotation recent (2026-04-30, within 90-day threshold)
- `docs/SECURITY.md:11`. No finding.
- **Action:** Continue logging rotations. Reminder for 2026-07-30.

### [INFRA-011] Backups / PITR config not visible in repo
- Out-of-repo Supabase setting.
- **Fix:** Document plan tier + PITR retention in `docs/SECURITY.md` or new `docs/OPS.md`.

### [INFRA-013] Session token hashing uses unsalted SHA-256 — acceptable
- `backend/auth_service/core/security.py:10-14`. 256-bit random token; precomputed table infeasible. Stored value is hash, never raw.
- **Action:** None.

### [CI-008] `scheduled-merge.yml` fast-forward path under `enforce_admins=true`
- Working as designed: pre-flight check on `head_sha` ensures status checks went green on that exact SHA before fast-forward push. Branch protection then validates the same checks on the same SHA when push lands. No bypass.
- **Action:** Document in `docs/ci.md` so future contributors don't think the workflow bypasses protection.

### [CI-016] `mint_admin_api_key.py` prints plaintext key once (intended)
- No log-pipe protection. Operator running under `script(1)` / piping through `tee` lands key on disk.
- **Fix:** Document in script header: don't run in CI, don't pipe stdout. Optionally write to TTY directly via `/dev/tty`.

### [DEP-011] Frontend deps use caret/tilde ranges
- `frontend/package.json:25-52`. Lockfile mitigates for `npm ci`. Fresh `npm install` would resolve newer versions.
- **Fix:** Either keep + ensure `npm ci` only in CI/Vercel, or tighten to exact pins (e2e is a good model).

### [DEP-012] `@types/node` major lag (frontend v20, e2e v22; latest 25)
- Type-only, not a vulnerability.
- **Fix:** Bump frontend to `"@types/node": "^22"` to match runtime. Optional.

### [DEP-013] Outdated but non-vulnerable backend pins
- FastAPI 0.115.6 → 0.136.1, uvicorn 0.32.1 → 0.46.0, pydantic 2.11.7 → 2.13.4, etc. None have published advisories at pinned versions (other than DEP-001…008). Lag is large enough that an unpatched CVE forces a multi-version jump.
- **Fix:** Quarterly bump pass; align FastAPI bump with starlette/python-multipart (DEP-002/003).

### [DEP-014] No typosquats / off-registry packages detected
- Verified: no `--index-url` / `--extra-index-url`; no `git+`/`github:`/`file:` specifiers; all `"resolved"` URLs in lockfiles point at `registry.npmjs.org`. All package names canonical.
- **Action:** None.

### [DEP-015] Lockfiles committed and consistent
- `frontend/package-lock.json` + `e2e/package-lock.json` tracked. `npm ci --dry-run` is up to date. No Python lockfile (see DEP-009).

### [DEP-016] `cms-client-template` has no `package.json`
- Template config only. Nothing to scan.
- **Action:** Confirm `scripts/sync-cms-types.mjs` runs against consuming client's package, not against an unpinned global.

### [PROC-011] No `.devcontainer/` — no current risk
- Codespaces not used.
- **Action:** If added later, document "no `ENV SECRET=…` in `Dockerfile`" rule.

### [PROC-012] `.gitattributes` and `.editorconfig` — no security issues
- `.gitattributes` well-formed. No `.editorconfig` (low priority).
- **Action:** Optional: add `.editorconfig`.

### [TEST-003] No rate-limit tests in integration suite
- No test exercises `/auth/login` lockout, `/forms` spam, `/admin/clients/{email}/welcome` Resend abuse, `/admin/projects/{slug}/transfer` loop. Regressions land silently.
- **Fix:** Add integration test firing N+1 requests to `/auth/login` with bad password and asserting 429. Same shape for forms.

### [TEST-004] CORS preflight test only covers two origins
- `backend/auth_service/tests_integration/test_cors.py:1-29`. No coverage for PATCH/DELETE methods, `Authorization` header in `Access-Control-Request-Headers`, `Access-Control-Allow-Credentials: true`. Regression dropping `Authorization` from allowed headers would silently break agent's Bearer flow.
- **Fix:** Parametrize preflight test over (method, request-header, expected-allow-headers, expected-allow-credentials).

### [TEST-006] `/admin/projects/{slug}/transfer` integration test only happy-path
- `backend/auth_service/tests_integration/test_admin_delegation.py:46-60`. Only 200 on happy path. Missing: non-admin → 403; non-existent email → 404 in integration layer.
- **Fix:** Append `("POST", "/admin/projects/e2e-test-project/transfer")` to `test_admin_gating.py:5-18` parametrize list.

### [TEST-011] `pytest.ini` allows arbitrary plugin auto-discovery
- `backend/auth_service/pytest.ini`, `agents/CMS Connector - Website/pytest.ini`. No `addopts = -p no:cacheprovider` or similar. Future poisoned dev dep with pytest plugin entry-point auto-loads.
- **Fix:** `addopts = -p no:autoload` OR `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` in CI workflows.

### [TEST-012] Coverage gaps in security-critical paths
- No test for revoking admin API key, no CORS test for agent's Bearer Authorization preflight, no test that `/auth/me` does NOT return `password_hash`, no test that `/content/{slug}` does NOT leak `preview_token`, no test for `Secure` cookie flag in production env (only `HttpOnly` is checked).
- **Fix:** File one ticket per gap. Minimum: Secure cookie + password_hash redaction tests (5-line additions).

### [TEST-013] Test conftest reads env at module level — brittle
- `backend/auth_service/tests_integration/conftest.py:15-18`. `os.environ["E2E_USER_PASSWORD"]` crashes import if env var missing. `pytest --collect-only` requires the secret.
- **Fix:** `os.environ.get(...)` + session-scoped `pytest_configure` that calls `pytest.skip` cleanly when E2E_* env vars are absent.

### [TEST-014] Hardcoded fake admin token format in tests (informational)
- `cmsk_dev_aaaaaaaaaaaaaaaa_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz` documents exact admin-key format publicly. Not a leak, but if repo goes private later, replacing with `cmsk_<test>_*` placeholders avoids documenting brute-force planning data.
- **Fix:** Acceptable as-is for current visibility model.

### [TEST-015] No snapshot test files
- No `__snapshots__/` directories. Vitest snapshots not used. No risk of secrets in snapshots.

---

## Cross-domain duplicates

A handful of findings appear under multiple domains because they cross domain boundaries. The implementation plan should treat each pair as ONE work item:

| Finding A | Finding B | Implementation = single task |
|---|---|---|
| BE-009 | INFRA-003 | Privilege boundary fix in `services/supabase_client.py` |
| BE-010 | (n/a) | RLS policies on `users`, `sessions`, `projects`, `content_entries` |
| FE-001 | INFRA-002 | Security headers in `next.config.ts` |
| PROC-003 | SEC-004 | gitleaks pre-commit hook + `.gitleaks.toml` |
| PROC-003 | CI-011 | Same hook |
| CI-009 | PROC-004 | Branch protection on `dev` |
| SEC-005 | PROC-013 | Redact secrets in plan doc |
| CI-012 | DEP-010 | SHA-pin pre-commit hooks |

---

## Phasing for the implementation plan

The audit produced 109 findings; bundling them into 5 phases with explicit dependencies keeps the future plan executable in a sensible order.

### Phase S1 — Stop the bleeding (must finish in 2–3 days)

| Task | Findings |
|---|---|
| Flip repo private OR enable secret scanning + push protection + Dependabot + automated security fixes | PROC-001 |
| Rotate Supabase PAT in `.mcp.json`; document rotation cadence | PROC-002 |
| Add gitleaks + bandit + eslint-plugin-security to pre-commit and CI | PROC-003 / SEC-004 / CI-011 |
| Bump Next.js 16.1.6 → 16.2.5 | DEP-001 |
| Bump FastAPI 0.115.6 → 0.118.0 (carries starlette + python-multipart fix) | DEP-002 / DEP-003 |
| Branch protection on `dev` | CI-009 / PROC-004 |
| Rate-limit `/auth/login` | BE-002 |

### Phase S2 — Browser hardening (3–4 days)

| Task | Findings |
|---|---|
| `next.config.ts` headers (HSTS, CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy) | FE-001 / INFRA-002 |
| Backend `vercel.json` + `SecurityHeadersMiddleware` extension | INFRA-001 |
| Fix `secure` cookie attribute in preview environment | BE-008 |
| Path-traversal guard in proxy | FE-003 |
| `safeHref()` helper everywhere a dynamic href / `window.open` accepts admin input | FE-007 / FE-008 |
| `FASTAPI_URL` strict-mode startup guard | FE-004 |
| Method allow-list in proxy | FE-002 |

### Phase S3 — Privilege boundary repair (5–7 days)

| Task | Findings |
|---|---|
| Split `get_supabase()` (anon) vs `get_supabase_admin()` (service-role) | BE-009 / INFRA-003 |
| Audit ~60 call sites for least-privilege use | BE-009 |
| Add RLS policies on `users`, `sessions`, `projects`, `content_entries`, `project_issues`, `project_requests` | BE-010 / INFRA-006 |
| `model_validator` requiring `SUPABASE_SERVICE_ROLE_KEY` in preview/production | INFRA-007 |
| Drop `preview_token` from `AdminProjectDetailOut` and `AdminProjectPatchIn` | BE-004 / BE-014 |
| `Origin` header allowlist (or CSRF token) on cookie-auth mutations | BE-015 |
| Vercel deployment-protection check for infra projects in `disable_vercel_auth.py` | INFRA-009 / INFRA-014 |

### Phase S4 — Supply-chain + CI hardening (3–5 days)

| Task | Findings |
|---|---|
| `pip-compile --generate-hashes` for backend + agent | DEP-009 / CI-004 |
| `npm audit fix` (frontend) | DEP-005 / DEP-006 |
| Bump python-dotenv 1.2.2, black 26.3.1, pytest 9.0.3, lint-staged 15.5.2 | DEP-004 / DEP-007 / DEP-008 |
| SHA-pin first-party Actions + pre-commit hooks | CI-002 / CI-012 / DEP-010 |
| `.github/dependabot.yml` (5 ecosystems) | CI-010 |
| `permissions: contents: read` top-level on ci.yml + e2e.yml | CI-003 |
| `--ignore-scripts` on `npm ci` | CI-005 |
| Restrict `E2E_*` secrets to step-level env | CI-014 |
| Plumb `E2E_ADMIN_API_KEY` through `e2e.yml` (or revoke if dead) | CI-013 / TEST-005 |
| CodeQL workflow | CI-018 |
| `workflow_dispatch` environment gate on scheduled-merge | CI-001 |

### Phase S5 — Process, tests, residual hardening (3–4 days)

| Task | Findings |
|---|---|
| Symlink `docs/SECURITY.md` → root, expand with disclosure policy + threat model + IR runbook | PROC-005 / PROC-009 |
| Redact rotated literal secrets in plan doc | SEC-005 / PROC-013 / SEC-002 / SEC-003 |
| Add `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` | PROC-006 |
| Phase 6 agent doc: drop inline secret prompts, secure-temp-file pattern | PROC-007 |
| `.env.example` revocation/rotation per-secret guidance | PROC-008 |
| Document VERCEL_TOKEN in `ENVIRONMENTS.md` | INFRA-012 |
| Migrations idempotent + transaction-wrapped | INFRA-005 |
| Storage bucket-level limits in Supabase | INFRA-004 |
| `cms-files` bucket: drop SVG or attach `Content-Disposition: attachment` | INFRA-004 |
| Backend rate limits on writes (change-password, /admin/* writes, /project-requests) | BE-003 |
| Pydantic validation: `max_length` + `pattern` everywhere user-controlled | BE-005 |
| Welcome email HTML escape | BE-006 |
| Generic 500 error messages (drop `str(exc)`) | BE-007 |
| LAN range removal from dev CORS regex | BE-012 |
| `_resolve_client` / Phase 6 short-circuit Resend in `ENVIRONMENT=preview` | TEST-002 |
| `globalTeardown` for Playwright resetSeedState | TEST-009 |
| Mask password field in Playwright traces; restrict artifact retention | TEST-010 |
| Integration tests for rate limit + transfer 403 + Secure-cookie flag | TEST-003 / TEST-006 / TEST-012 |
| Fix `mock_supabase` and `auth_as` silent except patterns | TEST-007 / TEST-008 |
| `forms.py` rate-limiter keyed by `(slug, form_key, real-ip)` | BE-001 |
| Bearer-path rate limit + dummy argon2 verify on parse-fail | BE-011 |
| `INFRA-008`: require non-empty `allowed_origins` at project creation | INFRA-008 |
| Fail-loud on `VERCEL_TOKEN` missing during preview-token rotation | INFRA-015 |
| `addopts = -p no:autoload` to pytest.ini | TEST-011 |

---

## Notes for implementers

1. **PROC-001 first.** The repo is public with all scanning disabled. Until that is fixed, every other remediation is racing against an unknown number of hostile readers.

2. **Phase S1 + S2 ship together.** The browser-side hardening (S2) only matters once the public exposure is contained (S1).

3. **Phase S3 is the riskiest.** Splitting service-role / anon usage across ~60 call sites changes runtime behaviour. Land it behind a feature flag (`SETTINGS.SUPABASE_USE_RLS_GATE = bool`), audit each call site one-by-one, and run the full E2E suite before flipping the flag in production.

4. **The "rotated leaks in history" reality.** History rewrite is documented as out of scope. Combined with PROC-001 (private repo flip), the residual exposure is contained but the historical literals stay forever. Future contributors must internalise the redaction discipline (PROC-010) so this doesn't happen again.

5. **Auditor sentinel values** (`cmsk_dev_aaaa…`, `zzzz…`, `cms-test.dev` test domain): keep them; document them in `docs/SECURITY.md` so future scanner rules can allow-list them explicitly.

---

## Appendix — scan provenance

- 7 scans dispatched in parallel via subagents. Each got a narrow scope, a domain-specific checklist, and a strict output format. The merge in this document preserves the original IDs (`SEC-*`, `BE-*`, `FE-*`, `CI-*`, `INFRA-*`, `DEP-*`, `PROC-*`, `TEST-*`) so any future re-scan can map findings 1:1.
- Audit date: 2026-05-07.
- Repo HEAD at audit time: dev = `59aa958` (also master after scheduled-merge).
- Tools used: ripgrep (read-only file search), `gh api` (repo + branch protection state, secrets list), `pip-audit` (CVE check, installed in `backend/venv`), `npm audit` / `npm outdated` (frontend + e2e), `git log -p --pickaxe-regex` (history scan).
- No source files were modified during the audit. No `git commit` was made by the audit. The scanners installed `pip-audit` into `backend/venv` only.
- This document is the single source of truth for the remediation plan. Update it in place if a finding is fixed, and reference its ID from the implementation commit message (e.g. `fix(security): BE-002 rate-limit /auth/login`).
