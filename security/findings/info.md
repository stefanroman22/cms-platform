# Informational findings

_Best-practice notes and accepted-by-design observations._

**10** finding(s). See [`../FINDINGS.md`](../FINDINGS.md) for live status. Reviewed 2026-06-07.

---

<a id="sec-046"></a>

## SEC-046 — Bearer auth path returns a plain dict while the rest of the codebase assumes a UserOut object, creating an authZ-shape fragility

| | |
|---|---|
| **Severity** | info |
| **Status** | open |
| **Category** | Type-confusion / defensive coding |
| **Dimension** | admin-priv |
| **Location** | `backend/auth_service/routers/deps.py:60-75,86-91; backend/auth_service/services/admin_keys.py:135-140` |
| **Reviewer confidence** | medium |
| **Verifier verdict** | confirmed (adjusted: info) |
| **First seen** | 2026-06-07 |

**Description**

admin_user_via_bearer_or_sid returns the raw dict from verify_admin_api_key on the Bearer path but a UserOut pydantic object on the session path. user_via_bearer_or_session then hands either shape to require_project_access, which reads user.id / user.is_admin as attributes (project["user_id"] != user.id and not user.is_admin). A dict has no .id/.is_admin attributes, so a Bearer admin key calling any owner-or-admin route that funnels through require_project_access (e.g. booking_admin _tenant -> user_via_bearer_or_session -> require_project_access) would raise AttributeError rather than authorize. This is not an authZ bypass (it fails closed with a 500), but the inconsistent principal shape is a latent fragility: the admin dep itself only survives because it reads is_admin via getattr-then-dict-fallback at lines 67-69, a pattern not replicated in require_project_access. Confirm via tests whether Bearer admin keys actually exercise the booking-admin/require_project_access path; if they do, it 500s today.

**Attack scenario**

No direct attacker exploit. The risk is that a future refactor relies on the dict-vs-object duality and silently weakens a check, or that the current AttributeError masks a route that admins believe works. Documented here as a correctness/defense-in-depth nit within the admin-gating dimension.

**Evidence**

```text
user = verify_admin_api_key(plain)
        if user:
            return user   # <-- plain dict
    ...
    if project["user_id"] != user.id and not user.is_admin:   # require_project_access expects attributes
```

**Adversarial verification**

The type-shape inconsistency is real and I confirmed it end-to-end. verify_admin_api_key returns a plain dict (admin_keys.py:135-140), while the session path returns a UserOut pydantic object (deps.py require_user -> validate_session). admin_user_via_bearer_or_sid returns the dict verbatim on the Bearer path (deps.py:59-61) and only has the getattr-then-dict-fallback for is_admin on the COOKIE path (deps.py:67-69) — the bearer dict is never normalized. require_project_access then does `project["user_id"] != user.id and not user.is_admin` (deps.py:37), reading .id/.is_admin as attributes. A plain dict has no such attributes; I reproduced `AttributeError: 'dict' object has no attribute 'id'`. UserOut is a plain BaseModel (schemas.py:62-66) with no dict-style access, so the two shapes are genuinely incompatible.

The reachability the finding asked to confirm is real and broader than stated. Multiple LIVE routes pass the bearer dict into require_project_access (or read user.is_admin) on the bearer path: workspace.py:220-225 save_service (also `if seed and not user.is_admin` at :221 fails first), workspace.py:407-408 add_service, workspace.py:490-491 remove_service, booking_admin.py:117-118 _tenant, booking_admin.py:134-135 enable (also `admin.email` at :135). The connector agent authenticates with real Bearer admin keys against these endpoints, so on the bearer path these would raise AttributeError -> HTTP 500 in production.

Why this isn't caught: every bearer-path test patches user_via_bearer_or_session / admin_user_via_bearer_or_sid to return a UserOut object (test_workspace_save.py:438 with _ADMIN_USER=UserOut(...), test_booking_admin_router.py:192 with ADMIN=UserOut(...)). The real verify_admin_api_key dict is never exercised through require_project_access, so the suite is green while the integrated path is broken.

This is a correctness/robustness defect, not an authZ bypass. It fails CLOSED (500/denied), never granting access. Keeping severity at info as reported — it is a latent fragility / functional-breakage nit within the admin-gating dimension, not an exploitable security vulnerability.

**Exploitability:** No attacker exploit and no privilege gain. The only principal that can reach the dict path is a holder of a valid, active, non-revoked admin API key (the trusted Connector automation) — i.e., an already-authorized admin, not an outside attacker. The outcome is a fail-closed HTTP 500 (AttributeError on dict.id/dict.is_admin), which DENIES the operation rather than authorizing it; there is no path where the wrong shape silently grants access. Real-world impact is functional/self-DoS: bearer-authenticated connector calls to save_service/add_service/remove_service/booking enable+_tenant would error out, an availability/correctness problem masked by tests that mock the auth dep. Security risk is limited to defense-in-depth: a future refactor could lean on the dict-vs-object duality and weaken a check. Recommendation stands — normalize verify_admin_api_key (or admin_user_via_bearer_or_sid) to always return a UserOut so every downstream check sees one principal type.

**Recommendation**

Normalize verify_admin_api_key to return a UserOut (or have admin_user_via_bearer_or_sid wrap the dict in UserOut) so every downstream authZ check sees a single, consistent principal type with .id/.is_admin attributes.

---

<a id="sec-047"></a>

## SEC-047 — Session cookie not rotated to a stronger lifetime on remember-me users after password change

| | |
|---|---|
| **Severity** | info |
| **Status** | open |
| **Category** | session-management |
| **Dimension** | authn-session |
| **Location** | `backend/auth_service/routers/auth.py:117-125` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: info) |
| **First seen** | 2026-06-07 |

**Description**

On password change all sessions are correctly revoked and a fresh one minted (good — prevents session-fixation/privilege-retention). However the new session is always created with remember_me=False, so a user who originally logged in with remember-me silently drops from a 60-day to a 30-day session after changing their password. This is a UX/consistency nit, not a security weakness — if anything a shorter lifetime is safer. No action required beyond awareness.

**Attack scenario**

Not exploitable. Noted for completeness because it is the privilege/session-rotation path under review.

**Evidence**

```text
raw_sid, _ = await create_session(fresh_user, remember_me=False, user_agent=user_agent, ip=ip)
    _set_session_cookie(response, raw_sid, remember_me=False)
```

**Adversarial verification**

I read the cited code and it matches the evidence exactly. In backend/auth_service/routers/auth.py, change_password (lines 97-125) validates the session (101-103), enforces the new-password length (105-109), verifies the current password via change_user_password (111-115), then revokes ALL sessions for the user (line 118 revoke_all_for_user) and mints a fresh one (line 124 create_session(..., remember_me=False)) with the cookie set at line 125 (_set_session_cookie(..., remember_me=False)). The remember_me flag controls only session lifetime: _set_session_cookie (lines 30-38) and sessions.create_session (services/sessions.py:25, with REMEMBER_ME_DAYS=60 vs DEFAULT_DAYS=30, confirmed by tests test_sessions.py:164-173 and test_auth_router.py:79-95). So the claim is factually correct: a remember-me user is silently downgraded from a 60-day to a 30-day session after a password change. Critically, this moves in the SAFER direction (shorter session lifetime), grants no attacker any capability, exposes no data, and the security-relevant rotation (revoke-all + re-mint on the same response) is fully intact. The reviewer already self-classified this as info / not exploitable / no action required. My independent read agrees: it is a real behavioral/UX consistency observation, not a security vulnerability.

**Exploitability:** Not exploitable. There is no attacker and no privilege/data gain. The only effect is that a user who chose remember-me and then changes their own password gets a 30-day instead of a 60-day session cookie — a shorter, strictly-safer lifetime. Triggering it requires the legitimate authenticated user to call POST /auth/change-password with their correct current password (line 111 verification). No third party can induce any security-relevant state from this behavior.

**Recommendation**

Optional: preserve the user's original remember_me preference when re-minting the post-password-change session. No security change.

---

<a id="sec-048"></a>

## SEC-048 — Public booking slug allows tenant existence enumeration via config endpoint

| | |
|---|---|
| **Severity** | info |
| **Status** | open |
| **Category** | Information disclosure / enumeration |
| **Dimension** | public-tokens |
| **Location** | `backend/auth_service/routers/booking.py:305-320` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: info) |
| **First seen** | 2026-06-07 |

**Description**

GET /booking/{slug}/config returns 404 for an unknown slug and 200 with business_name, colors, logo_url and locale for a known one. By design these booking pages are public (the widget addresses tenants by public_slug), so this is expected behaviour, but it does let an attacker enumerate which projects have a booking page and read their public branding by guessing/sweeping slugs. No private data (no tenant_id, customer data, or tokens) is exposed.

**Attack scenario**

An attacker sweeps candidate slugs against /booking/{slug}/config; 200 vs 404 reveals which tenants have booking enabled, and the body discloses business name/logo for reconnaissance. No sensitive data leaks.

**Evidence**

```text
@router.get("/{slug}/config")
def public_config(slug: str) -> JSONResponse:
    cfg = booking_tenant.load_tenant_by_slug(slug)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Unknown booking page")
    return JSONResponse(content={... "business_name": cfg.business_name, ...})
```

**Adversarial verification**

The cited code matches the evidence exactly. `GET /booking/{slug}/config` (booking.py:305-320) calls `booking_tenant.load_tenant_by_slug(slug)`, raises 404 when it returns None, and otherwise returns a JSON body. I confirmed via booking_tenant.py:73-74 and _load_where (lines 63-70) that load_tenant_by_slug returns None both for a non-existent slug AND for an inactive tenant (`is_active` false), so the 404-vs-200 split discloses exactly 'has an active booking page'. I also confirmed the response body is strictly branding-only: public_slug, business_name, primary_color, accent_color, widget_color, logo_url, locale. The richer TenantConfig fields that ARE loaded (tenant_id, owner_notification_email, meeting_url, calendar_provider, reminder config, email_copy) are deliberately NOT included in the response — so no tenant_id, no PII, no tokens, no internal addressing leak. The route has no auth dependency and no rate limit (confirmed by grep: only `_require_tenant` helper appears on sibling routes, which is just a 404-or-load wrapper, not authZ). This is the intended public booking surface — the embeddable widget addresses tenants by public_slug, which is itself public knowledge to anyone holding a booking link. The finding is factually accurate and its self-classification as info / expected-behavior is correct. No data-exposure change is warranted; the only residual is generic enumeration, mitigated by non-guessable slugs + optional per-IP rate limiting.

**Exploitability:** Any unauthenticated internet client can sweep candidate slugs against /booking/{slug}/config. A 200 reveals that a project has an active booking page; a 404 means absent or inactive. The 200 body discloses only public branding (business name, brand/widget colors, logo URL, locale) — the same data the public booking widget already renders to every visitor. No tenant_id, no owner email, no customer/booking data, no tokens are returned. So the practical gain is reconnaissance only: an attacker can fingerprint which tenants have booking enabled and scrape their public branding. Real-world risk depends on slug guessability; with slugs derived from public business names this enumeration is trivial but yields nothing beyond what visiting the public booking page already shows.

**Recommendation**

Accept as inherent to a public booking surface. If enumeration is a concern, use non-guessable slugs and add a per-IP rate limit to bound sweeping. No data-exposure change needed.

---

<a id="sec-049"></a>

## SEC-049 — Short-link expansion follows redirects without re-validating the resolved host (limited SSRF surface)

| | |
|---|---|
| **Severity** | info |
| **Status** | open |
| **Category** | SSRF / URL handling (operator-gated) |
| **Dimension** | scraper |
| **Location** | `scraper/src/scraper/urls.py:84-95 (expand_if_short)` |
| **Reviewer confidence** | medium |
| **Verifier verdict** | confirmed (adjusted: info) |
| **First seen** | 2026-06-07 |

**Description**

expand_if_short issues a GET to a goo.gl / maps.app.goo.gl short link and reads response.geturl(); the final URL is validated only by checking it contains '/place/' or '!1s', NOT by re-applying the Google host allowlist. urllib follows redirects automatically. The input is gated by is_google_maps_url (host must be a Google shortener), and short-link redirect targets are Google-controlled, so this is not a practical attacker-driven SSRF. It is also reached only from the operator/admin scrape-url single-URL path (direct_url), not an unauthenticated surface. Noted as info because the resolved host is trusted without re-checking the allowlist and no SSRF protections (no internal-IP blocking) exist on the urllib calls used across geo.py / urls.py / build_regions.py.

**Attack scenario**

Not realistically exploitable today: the entry host must be a Google shortener and only Google controls where those resolve. If the host allowlist were ever loosened, or a Google open-redirect were chained, the follow-redirect + weak final-URL check could be steered. Operator-only entry point further reduces risk.

**Evidence**

```text
with urllib.request.urlopen(req, timeout=_EXPAND_TIMEOUT_S) as resp:
    final: str = resp.geturl()
if "/place/" not in final and "!1s" not in final:
    raise InvalidMapsURLError(...)
return final   # host of `final` is never re-checked against the allowlist
```

**Adversarial verification**

The code claim is accurate. In scraper/src/scraper/urls.py, expand_if_short() only issues a network GET when the input host is in _SHORT_HOSTS = {maps.app.goo.gl, goo.gl} (urls.py:21,76). urllib.request.urlopen (urls.py:89) follows redirects automatically, and the resolved URL from resp.geturl() (urls.py:90) is validated ONLY by a content/path check — `if "/place/" not in final and "!1s" not in final` (urls.py:93) — never re-checking the resolved host against _MAPS_HOST_SUFFIXES (urls.py:13-20). So the evidence in the finding is faithful to the source. The input is host-gated upstream by is_google_maps_url (urls.py:46, called at urls.py:65 and in cli.py:164), so the entry host must be a Google shortener; redirect targets of those shorteners are Google-controlled. I also confirmed the absence of any internal-IP/SSRF blocking on the urllib calls across urls.py, geo.py (geo.py:99), and tools/build_regions.py (build_regions.py:31). On reachability: the ONLY caller of expand_if_short is google_maps.py:803 inside run_pipeline's direct_url branch, and direct_url is set exclusively by the `scrape-url` Typer CLI command (cli.py:149-184). I grepped the entire backend and repo — no FastAPI router, HTTP endpoint, or subprocess wrapper invokes the scraper; all references are confined to the scraper package and its tests. This is a local operator/CLI tool, not a web-reachable surface. The finding self-rates info and explicitly states it is not a practical attacker-driven SSRF; that assessment matches the code.

**Exploitability:** Not exploitable by any remote or unauthenticated actor. There is no HTTP entry point — the only way to reach expand_if_short is to run `python -m scraper.cli scrape-url <url>` from a shell on the operator's machine/CI, which already requires the input host to be a Google shortener (is_google_maps_url gate). The follow-redirect destination is therefore controlled by Google's goo.gl / maps.app.goo.gl service, not the caller. To turn this into real SSRF an attacker would need (a) shell access to run the CLI AND (b) either a loosened host allowlist or a Google open-redirect to chain through the shortener, plus the weak final-URL check happening to pass (`/place/` or `!1s` present in the resolved URL). With shell access an operator could already make arbitrary network calls directly, so no privilege is gained. Concrete worst case today: none — the trust boundary is not crossed. The value of the recommendation (re-validate resolved host against _MAPS_HOST_SUFFIXES, optionally resolve one hop at a time) is purely defense-in-depth to keep the surface safe if the allowlist is ever broadened. Severity info is correct.

**Recommendation**

Re-validate the resolved final URL's host against _MAPS_HOST_SUFFIXES before returning it, and consider disabling automatic redirect following (resolve one hop, validate host each hop). Keep this entry point operator-only.

---

<a id="sec-050"></a>

## SEC-050 — Backend application security-headers middleware omits Content-Security-Policy by design (relies on edge config)

| | |
|---|---|
| **Severity** | info |
| **Status** | open |
| **Category** | Security headers / defense-in-depth |
| **Dimension** | secrets-config |
| **Location** | `backend/auth_service/core/security_headers.py:9,13-30` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: info) |
| **First seen** | 2026-06-07 |

**Description**

SecurityHeadersMiddleware emits only X-Frame-Options: DENY and X-Content-Type-Options: nosniff, and the module docstring explicitly states 'Content-Security-Policy is intentionally out of scope for v1.' This is acceptable in practice because backend/vercel.json applies a strict `default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'` plus COOP/CORP at the Vercel edge for all backend responses. The risk is purely operational: if the app is ever served outside Vercel (local prod-like run, alternate host, or a route that bypasses the edge headers), responses would carry no CSP at all because the application layer never sets one. Noted as info/defense-in-depth, not a live vulnerability given the current Vercel deployment.

**Attack scenario**

A future deployment change that routes backend responses without the vercel.json edge headers would silently ship API responses with no CSP, since the FastAPI middleware never adds one. No exploit on the current production topology.

**Evidence**

```text
HSTS is emitted by Vercel's edge layer; not duplicated here.
Content-Security-Policy is intentionally out of scope for v1.
```

**Adversarial verification**

All factual claims verified against the cited code. security_headers.py:9 contains the verbatim docstring "Content-Security-Policy is intentionally out of scope for v1." The middleware (security_headers.py:22-27) appends ONLY x-frame-options: DENY and x-content-type-options: nosniff — no CSP. It is wired app-wide at main.py:131. backend/vercel.json's headers block applies, for source "/(.*)", a strict "Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'" plus HSTS, COOP same-origin, CORP same-site, Referrer-Policy and Permissions-Policy — exactly as the finding states. So on the current Vercel production topology every backend response DOES carry a strict CSP from the edge; the app layer simply does not duplicate it. The finding is accurate and is self-classified as info/defense-in-depth, explicitly stating it is "not a live vulnerability given the current Vercel deployment." I agree: this is a correct observation, not an exploitable flaw. Keeping severity at info. Note also that CSP on a JSON API has limited value (CSP mitigates XSS in browser-rendered HTML; the API returns JSON guarded by nosniff), and the clickjacking-relevant frame-ancestors directive is already mirrored app-side by X-Frame-Options: DENY.

**Exploitability:** No attacker can trigger this on the current system. On live production, all backend responses route through Vercel's edge (vercel.json) which injects the strict CSP, so responses are not CSP-less. The only way the gap manifests is an internal/operational change — serving the FastAPI app outside Vercel (local prod-like run, alternate host) or adding a route that bypasses edge headers — which is a future infrastructure decision, not an externally reachable condition. Even then, the practical impact is minimal: the endpoints serve JSON (already protected by X-Content-Type-Options: nosniff) and X-Frame-Options: DENY is still emitted by the app layer, covering the clickjacking case. There is no concrete exploit and no data/privilege gained. Correctly an info-level defense-in-depth note.

**Recommendation**

Optionally add a minimal `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` to SecurityHeadersMiddleware so the protection is not solely dependent on the deployment edge config (defense-in-depth). No action required while the app remains exclusively on Vercel.

---

<a id="sec-051"></a>

## SEC-051 — Historical Supabase Postgres DB password was committed in .env.example files (rotated; remains in git history)

| | |
|---|---|
| **Severity** | info |
| **Status** | open |
| **Category** | Secret hygiene (historical) |
| **Dimension** | secrets-config |
| **Location** | `docs/superpowers/plans/2026-04-30-env-config-hygiene.md:19-20,182` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: info) |
| **First seen** | 2026-06-07 |

**Description**

The env-config-hygiene plan documents that a real Supabase Postgres password (granting full DB write access via SUPABASE_DB_URL) was previously committed in backend/.env.example and backend/auth_service/.env.example. The current committed .env.example (read at backend/.env.example) is clean — it uses placeholders like REPLACE_WITH_... — and the plan's remediation log records that the password was rotated on 2026-04-30. The literal value is masked in the surviving docs and explicitly allowlisted in .gitleaks.toml so it cannot reappear. The only residual exposure is that the OLD (now-invalid) password still exists in the repository's git history; since it was rotated, this is informational rather than a live secret leak. This is noted as context for the project's overall log/secret hygiene posture (consistent with the gitignored prod-data backup that held live manage tokens).

**Attack scenario**

An attacker cloning the repo and reading old commits recovers the historical DB password — but it was rotated, so it no longer authenticates. No live impact; included so the team is aware the credential lives in history and history-scrub (or confirming rotation completeness) may be desired.

**Evidence**

```text
| `backend/.env.example:12` | `DB_PASSWORD=Stefanb***********!` | Full Postgres write access |
...
| 2026-04-30 | Supabase database password | Old password (`Stefanb***********!`) was embedded in `SUPABASE_DB_URL` in committed `.env.example` files | Stefan |
```

**Adversarial verification**

Every cited claim checks out against the actual code and git history. (1) Current backend/.env.example:18 is clean — SUPABASE_DB_URL uses placeholder [REPLACE_WITH_DB_PASSWORD] and YOUR_PROJECT_REF; no live secret in the working tree (Grep for the literal password returns zero matches). (2) The plan doc docs/superpowers/plans/2026-04-30-env-config-hygiene.md:19-20,182 accurately describes a previously-committed Postgres password, masked as Stefanb***********!, with a rotation logged for 2026-04-30. (3) The secret genuinely persists in git history: commit 21e1e2e:backend/.env.example contains cleartext DB_PASSWORD=Stefanbaschet1722!, and 21e1e2e:backend/auth_service/.env.example contains the URL-embedded password plus a live-shaped SUPABASE_SERVICE_ROLE_KEY JWT and RESEND_API_KEY=re_cENrXnX5_...; commit e9dc506 sanitized the working copy but history is unchanged (the plan explicitly declines history rewrite, lines 7/25). (4) .gitleaks.toml:72 allowlists the masked literal ('Stefanb\*+!?') and .env.example paths so it can't re-trip the scanner. The finding's own thesis is that the credential was ROTATED and is therefore non-authenticating; the rotation is recorded in the SECURITY log and corroborated by project memory. So this is a real, accurate observation but not a live-exploitable secret leak — info is the correct severity. Caveat: I can only confirm the rotation from the in-repo log, not from the provider; the actual rotation was an operational step performed in the Supabase/Resend/Vercel dashboards, which the repo cannot prove.

**Exploitability:** Anyone who can clone the repo (or already has a clone) can run `git show 21e1e2e:backend/auth_service/.env.example` and recover the historical Postgres password (Stefanbaschet1722!), the service_role JWT, and the Resend key in cleartext. IF those credentials were truly rotated on 2026-04-30 as the SECURITY log records, they no longer authenticate: the DB password reset invalidates direct Postgres logins, rolling the JWT secret invalidates the old service_role token, and deleting the Resend key revokes email send. In that case there is no live impact — the worst outcome is information disclosure of dead credentials and the project ref (xeluydwpgiddbamysgyu, already semi-public). The only way this becomes exploitable is if the documented rotation was NOT actually completed at the providers (the repo cannot prove it was), in which case a history reader gets full RLS-bypassing DB write access via the service_role key — which would be critical. Recommend confirming rotation completeness out-of-band; if confirmed, rotation alone suffices and history scrub is optional/compliance-only.

**Recommendation**

Confirm the rotation is complete and that no other system still trusts the old password. If history cleanliness matters for compliance, consider a one-time history rewrite (git filter-repo / BFG); otherwise rotation alone is sufficient and no further action is needed.

---

<a id="sec-052"></a>

## SEC-052 — Short-link redirect expansion validates only a substring of the resolved URL, not its host

| | |
|---|---|
| **Severity** | info |
| **Status** | open |
| **Category** | SSRF / outbound request safety |
| **Dimension** | ssrf-outbound |
| **Location** | `scraper/src/scraper/urls.py:84-95` |
| **Reviewer confidence** | medium |
| **Verifier verdict** | partially_confirmed (adjusted: info) |
| **First seen** | 2026-06-07 |

**Description**

expand_if_short() issues a GET on a goo.gl / maps.app.goo.gl short link and lets urllib follow redirects automatically. The only post-expansion guard is a substring check that the FINAL url contains '/place/' or '!1s'. There is no re-validation that the resolved host is still Google. A URL such as http://169.254.169.254/place/x or http://internal-host/x!1s would satisfy the substring check. In practice the redirect target is chosen by Google's own URL-shortener (the input host allowlist _SHORT_HOSTS only permits goo.gl/maps.app.goo.gl, both Google-controlled), so an attacker cannot currently steer the redirect to an internal address. This is therefore a defense-in-depth gap, not an exploitable SSRF: the resolved URL is later navigated by Playwright (google_maps.py:803 -> _scrape_one_place page.goto), so if the input allowlist ever loosened or Google's shortener were abused as an open redirector, the host check would not stop a localhost/metadata navigation.

**Attack scenario**

An operator (or a future automated caller) feeds a goo.gl short link that Google's shortener happens to redirect to an arbitrary host whose path contains '/place/'. expand_if_short returns it unchanged, canonicalize_place_url passes it through, and Playwright navigates to it. Because only Google-issued short links are accepted as input today, this is not reachable by an untrusted user; it becomes exploitable only if the host allowlist is widened or the shortener is used as an open redirect.

**Evidence**

```text
with urllib.request.urlopen(req, timeout=_EXPAND_TIMEOUT_S) as resp:
        final: str = resp.geturl()

    # After expansion, confirm we landed on a place page.
    if "/place/" not in final and "!1s" not in final:
        raise InvalidMapsURLError(f"short URL is not a place page (resolved to): {final!r}")
    return final
```

**Adversarial verification**

The code observation is accurate. In scraper/src/scraper/urls.py, expand_if_short() (lines 56-95) only follows urllib redirects for short hosts (maps.app.goo.gl, goo.gl per _SHORT_HOSTS, line 21) and the sole post-expansion guard is a substring check `if "/place/" not in final and "!1s" not in final` (lines 93-95). There is indeed NO re-validation that resp.geturl()'s host is still Google — a hypothetical resolved URL like http://169.254.169.254/place/x would pass the substring gate. The resolved URL does reach a network sink: google_maps.py:803 `canonicalize_place_url(expand_if_short(params.direct_url))` -> :827 `_scrape_one_place(..., expanded_direct_url, ...)` -> Playwright page.goto. So the data flow the finding describes is real.

However, the issue is not exploitable in this system, and the finding itself concedes this ("This is therefore a defense-in-depth gap, not an exploitable SSRF"). Two reasons: (1) Input is gated by is_google_maps_url (lines 29-53), which restricts the INPUT host to Google-controlled domains only, and only goo.gl/maps.app.goo.gl trigger the redirect path. An attacker cannot mint a goo.gl/maps.app.goo.gl short link that Google's own shortener redirects to an internal/metadata host — Google's URL shortener is not a general-purpose open redirector; it resolves only Google-created Maps links. (2) The ONLY caller is the operator-run `scrape-url` CLI command (cli.py:149-184, direct_url is set nowhere else — pipeline.py has no reference). There is no web endpoint or queue consumer feeding untrusted URLs into expand_if_short, so there is no untrusted-input trust boundary here. The exploit requires BOTH a future loosening of the allowlist AND Google's shortener behaving as an open redirect — neither holds today. Given a non-exploitable, operator-triggered, defense-in-depth gap, "low" overstates it; "info" is the honest severity. The recommendation (re-run host allowlist on the final URL, e.g. is_google_maps_url(final)) is a reasonable cheap hardening, but it is not fixing a present vulnerability.

**Exploitability:** Not exploitable as a security vulnerability in the current system. Trigger surface: the operator-only `scrape-url` CLI command (cli.py:149) is the sole producer of params.direct_url; no untrusted user, web request, or queue can reach expand_if_short. To actually navigate Playwright to an internal/metadata host, an attacker would need a goo.gl or maps.app.goo.gl short link whose redirect target is attacker-chosen AND whose path contains "/place/" or "!1s" — but Google's shortener does not let third parties create links that redirect to arbitrary non-Google hosts, so the redirect target stays Google-controlled. Worst realistic case if the only input allowlist were ever widened (or Google's shortener were abused as an open redirector), the attacker who controls the CLI argument could cause an outbound Playwright navigation to a localhost/169.254.169.254 URL ending in /place/ — i.e., SSRF from the scraper host. That precondition does not exist today, so the practical gain is zero. Value of the fix is purely future-proofing/defense-in-depth.

**Recommendation**

After resolving the short link, re-run the host allowlist on the FINAL url (reuse is_google_maps_url(final) or assert urlparse(final).hostname endswith a google.com/goo.gl suffix) before returning it, so a redirect to a non-Google host is rejected regardless of path. Optionally disable automatic redirect following and validate each hop.

---

<a id="sec-053"></a>

## SEC-053 — SECURITY DEFINER claim functions have mutable search_path (function_search_path_mutable)

| | |
|---|---|
| **Severity** | info |
| **Status** | open |
| **Category** | Function search_path / Hardening |
| **Dimension** | supabase-db |
| **Location** | `backend/migrations/2026_05_16_solver_agent_columns.sql:27-77; live pg_proc.proconfig=null for claim_next_solver_issue, claim_specific_solver_issue, leads_set_updated_at, scrape_jobs_set_updated_at` |
| **Reviewer confidence** | high |
| **Verifier verdict** | partially_confirmed (adjusted: info) |
| **First seen** | 2026-06-07 |

**Description**

Neither claim RPC sets `SET search_path = ''` / pg_catalog, confirmed by proconfig=null on the live DB. For a SECURITY DEFINER function this is a real hardening gap: it runs as postgres (a superuser-equivalent in Supabase), and an unqualified object reference resolved through a caller-influenced search_path could be hijacked if an attacker can create a same-named object in an earlier-resolving schema. In this codebase the bodies reference only the fully-trusted public.project_issues and built-ins, and a non-superuser cannot create objects in pg_catalog, so practical exploitation is constrained — hence low. The two trigger functions leads_set_updated_at / scrape_jobs_set_updated_at are NOT security-definer (they run as the invoker) and have trivial bodies, so their mutable search_path is only an advisor nit. Note the codebase already demonstrates the correct pattern in update_updated_at (proconfig = search_path="").

**Attack scenario**

If a future migration grants a lower-privileged role CREATE on a schema that precedes pg_catalog/public in the resolution order, an unqualified reference inside the definer function could resolve to an attacker-planted function/table, executing attacker code with postgres rights. Not reachable today but the missing search_path pin removes the guardrail.

**Evidence**

```text
CREATE OR REPLACE FUNCTION claim_next_solver_issue(...)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$ ... $$;   -- no SET search_path
-- live: proconfig = null (vs update_updated_at proconfig = ["search_path=\"\""])
```

**Adversarial verification**

The factual core of the finding is verified against the live DB (project xeluydwpgiddbamysgyu). pg_proc shows: claim_next_solver_issue (migration 2026_05_16_solver_agent_columns.sql:27-77) and claim_specific_solver_issue (live-only; NOT present in any committed migration — only claim_next exists in the file the finding cites, and the codebase RPC caller agents/Solver - Issues/db.py:39 only ever calls claim_next_solver_issue) are both prosecdef=true with proconfig=null — i.e. no SET search_path pin. By contrast update_updated_at has proconfig=["search_path=\"\""], so the correct pattern already exists in the codebase. The two trigger functions leads_set_updated_at (2026_05_17_lead_scraper.sql:122) and scrape_jobs_set_updated_at (2026_05_17_lead_scraper_fixes.sql:19) are prosecdef=FALSE (invoker rights), confirming the finding's own statement that they are only an advisor nit, not a security-definer concern.

Two corrections to the finding: (1) It claims the definer bodies "already do" fully-qualify object names as public.project_issues. They do NOT — I read both live bodies and the migration source: every reference is the unqualified `project_issues`, resolved via search_path. So the search_path dependency is slightly more real than the finding states (the recommendation to fully-qualify is the actual fix, not already-done). (2) The finding calls postgres "a superuser-equivalent." Live pg_roles shows rolsuper=false for the owner postgres — it is privileged but not a flagged superuser; the claim is overstated.

The decisive control: I checked CREATE privileges for every Supabase-exposed role on the schemas that resolve at/before public. has_schema_privilege returns CREATE=false for anon, authenticated, AND service_role on both public (owner pg_database_owner) and pg_catalog (owner supabase_admin). No tenant-facing or API role can plant a same-named object (function/table) in any schema that would shadow the unqualified project_issues reference. Therefore the hijack precondition does not exist today. Exploitation requires a hypothetical FUTURE migration to grant CREATE to a lower-privileged role — the finding itself says "Not reachable today." This is a defense-in-depth/hardening gap, not a present vulnerability.

**Exploitability:** Not exploitable by any current actor. The only DB-reaching code path is the backend service-role client calling claim_next_solver_issue via RPC (REVOKE ALL FROM PUBLIC + GRANT EXECUTE TO service_role is in place at migration line 79-80). To weaponize the missing search_path pin, an attacker would need CREATE on a schema resolving before public, then plant a shadowing object named `project_issues`. Live privilege check shows anon/authenticated/service_role all have CREATE=false on public and pg_catalog, and those schemas are owned by pg_database_owner / supabase_admin (not reachable by tenant roles). So no frontend user, no API caller, and no Supabase-exposed role can trigger the hijack. The gap only becomes live if a future migration grants a lower-priv role CREATE on a preceding schema — a self-inflicted precondition. Correct hardening: add SET search_path = '' and fully-qualify references as public.project_issues in both claim_* functions (bodies currently use the unqualified name). Severity downgraded low → info: real and worth fixing for guardrail consistency with update_updated_at, but zero present exploitability.

**Recommendation**

Add `SET search_path = ''` (and fully-qualify object names as public.project_issues, which the bodies already do) to both claim_* functions; optionally pin the two trigger functions too for consistency. Re-apply alongside the REVOKE fix from finding 1.

---

<a id="sec-054"></a>

## SEC-054 — Tenant-table RLS owner policies are inert because the app does not use Supabase Auth JWTs (auth.uid() always NULL)

| | |
|---|---|
| **Severity** | info |
| **Status** | open |
| **Category** | Defense-in-depth / RLS efficacy |
| **Dimension** | supabase-db |
| **Location** | `backend/migrations/2026_05_09_tenant_tables_rls.sql:35-159 (and 2026_05_07_project_requests_rls.sql)` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: info) |
| **First seen** | 2026-06-07 |

**Description**

The owner policies on users/sessions/projects/content_entries/project_issues/project_requests all gate on `id/user_id = auth.uid()` scoped to the authenticated role. The migration's own header documents that the app authenticates via a hand-rolled `sid` session cookie (services/sessions.py), NOT Supabase Auth JWTs, so auth.uid() is NULL for every PostgREST request and these policies reduce to deny-all for anon/authenticated. This is intentional and fail-closed (the correct posture given the backend uses the service-role key which bypasses RLS entirely), so there is no vulnerability today. Recorded as info because it means RLS provides ZERO live owner-enforcement — it is purely a tripwire for a future refactor. The real cross-tenant/IDOR authorization lives in FastAPI router/deps code (out of this dimension's scope) and is the only thing actually enforcing object-level authZ. The booking_*, leads and scrape_jobs tables are RLS-enabled with zero policies (verified live), which is correctly deny-all.

**Attack scenario**

No direct attack. The note matters if the team later assumes 'RLS protects us' — it does not protect any live request path, since service-role bypasses it and cookie-auth never populates auth.uid(). Any authZ regression must be caught in application code/tests, not relied upon at the DB layer.

**Evidence**

```text
CREATE POLICY "projects_owner_select" ON projects FOR SELECT TO authenticated USING (user_id = auth.uid());
-- migration header: 'auth.uid() is NULL for every request that reaches PostgREST today ... reduce to "deny all"'
```

**Adversarial verification**

All claims independently verified against the cited code. (1) The owner policies do gate on auth.uid(): 2026_05_09_tenant_tables_rls.sql lines 42/62/74/81/89/110/124/132/150/157 and 2026_05_07_project_requests_rls.sql lines 28/36 all use id/user_id = auth.uid() scoped TO authenticated. (2) The app does NOT use Supabase Auth JWTs: services/sessions.py implements a hand-rolled sid cookie — a random token hashed via hash_token() and stored in the sessions table, validated through get_supabase_admin() (service-role). routers/auth.py:77 returns a literal placeholder access_token="session" (no real JWT). Grep for sign_in/set_session/postgrest JWT injection found none; the only auth.* calls are sb_admin.auth.admin.create_user/delete_user (GoTrue admin management via service-role), which do not set a user JWT context. So auth.uid() is NULL for every PostgREST request and these policies collapse to deny-all for anon/authenticated — exactly as the migration header (lines 12-18) documents. (3) Service-role bypass is real and total: services/supabase_client.py:39-53 get_supabase_admin() uses SUPABASE_SERVICE_ROLE_KEY which bypasses RLS; get_supabase_anon() (RLS-subject) is defined but has ZERO call sites anywhere in the codebase, so no live path is subject to RLS. (4) Frontend has no direct DB client (no @supabase/createClient/supabase-js in frontend/src), so nothing could ever populate auth.uid() client-side. (5) The fail-closed posture and the CI tripwire are real: tests_integration/test_rls_policies.py asserts RLS stays ON for all six tenant tables via the tenant_rls_status view (defined at migration lines 168-185). The finding is self-consistent, accurately read, and explicitly states there is no vulnerability today; it is a defense-in-depth/info note, correctly classified. Object-level authZ is enforced in FastAPI router/deps code (out of scope here), not at the DB layer.

**Exploitability:** Not exploitable. There is no attacker and no privilege gain. Because the backend uses the service-role key (RLS bypassed) and the unused anon client is the only RLS-subject path, the dormant owner policies enforce nothing on any live request — and where they would apply, NULL auth.uid() yields deny-all (fail-closed, the safe direction). No data is exposed and no authorization is weakened by this code. The only real-world consequence is a process/assumption risk: if the team ever believes RLS provides live owner-enforcement, they would be mistaken — all cross-tenant/IDOR authorization must be (and is) enforced in FastAPI router/deps code and covered by application-layer tests. The existing CI presence test (test_rls_policies.py) appropriately guards against the RLS-disabled regression.

**Recommendation**

Keep the fail-closed RLS as defense-in-depth. Maintain the CI presence test that asserts RLS stays ON for every tenant table (the tenant_rls_status view exists for this). Do not treat these policies as live authorization; ensure cross-tenant authZ remains fully covered by application-layer tests in routers/deps.

---

<a id="sec-055"></a>

## SEC-055 — Widget posts resize messages with wildcard target origin

| | |
|---|---|
| **Severity** | info |
| **Status** | open |
| **Category** | postMessage hygiene |
| **Dimension** | xss-html |
| **Location** | `frontend/src/app/(widget)/w/[slug]/page.tsx:18-19` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: info) |
| **First seen** | 2026-06-07 |

**Description**

The widget iframe sends window.parent.postMessage({type:'booking_resize', height}, '*') with a wildcard targetOrigin. The payload is only a numeric height (no sensitive data), and the embed.js loader correctly validates event.origin, payload type, and height type before acting, so there is no exploitable issue — noted only as a hardening nit.

**Attack scenario**

No meaningful exploit: a malicious parent frame could read the resize message, but it contains only the widget's own scroll height, which is not sensitive. The inbound side (embed.js) is properly origin-checked.

**Evidence**

```text
window.parent.postMessage({ type: "booking_resize", height }, "*");
```

**Adversarial verification**

Read the cited code directly. frontend/src/app/(widget)/w/[slug]/page.tsx:18-19 posts window.parent.postMessage({ type: "booking_resize", height }, "*") where `height` = document.body.scrollHeight (a plain number). The wildcard targetOrigin is confirmed. The payload carries no credentials, tokens, or PII — only the widget's own rendered height. The inbound side, frontend/src/app/embed.js/route.ts:37-47, correctly hardens consumption: it checks event.origin !== origin (origin derived from the loader script's own src, line 38), rejects non-object data (line 40), and only acts on data.type === 'booking_resize' with typeof data.height === 'number' (line 41) before setting iframe height. So spoofed messages from a hostile parent/sibling frame cannot influence the embedder beyond the already-validated numeric height. I also checked the only other widget→parent message (BookingCalendar.tsx:244, { type: "booking_completed", booking_id }, "*") — outside the cited location but the same pattern; booking_id is an opaque server ID, and customer name/email are sent only in the POST body (lines 229-235), never broadcast via postMessage. The finding's self-assessment (info / hardening nit) is accurate. No change to severity.

**Exploitability:** No meaningful exploit. The wildcard targetOrigin means any frame that embeds the widget iframe (i.e., the site owner who intentionally dropped in the <script data-tenant> loader, or a frame that wraps that page) can read the booking_resize message. What it gains is the widget's own scroll height in pixels — non-sensitive and already visually observable. No session cookies, JWTs, customer PII, or booking details are transmitted on this channel (PII stays in the fetch POST body). The inbound consumer (embed.js) origin-checks and type-checks every message, so a malicious parent cannot inject a forged resize to cause harm. Net result: a hardening nit, not an exploitable vulnerability.

**Recommendation**

Optionally constrain the targetOrigin if the set of embedding origins is known; otherwise acceptable since no sensitive data is transmitted. The embed.js inbound origin check is correct and should be kept.

---
