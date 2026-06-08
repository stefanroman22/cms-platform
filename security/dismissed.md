# Dismissed findings (false positives / non-issues)

These 14 candidate findings were raised by a finder agent but **adversarially verified as false positives or non-issues**. Kept here so future reviews don't re-raise them. Reviewed 2026-06-07.

---

## D-01 — Rate-limit key fully trusts client-supplied X-Forwarded-For, spoofable outside the Vercel edge

- **Claimed severity:** low · **Dimension:** authn-session · **Verdict:** false_positive
- **Location:** `backend/auth_service/core/limiter.py:14-18, backend/auth_service/core/bearer_limiter.py:59-61`

**Why dismissed:** The finding's core premise — that the leftmost X-Forwarded-For entry is attacker-controlled in production — is contradicted by THIS codebase's own documented edge behavior. `client_ip()` (limiter.py:14-18) does take XFF[0], and both the Bearer brute-force limiter (bearer_limiter.py:59-61 via deps.py:52-53) and the login limiter (auth.py:62 `@limiter.limit("30/minute")` against `Limiter(key_func=client_ip)`) key on it — all as described. BUT the repo explicitly documents that Vercel PREPENDS the real client IP to the LEFT of XFF at the edge: auth.py:58-59 ("Vercel rewrites X-Forwarded-For at the edge (prepends the real client IP)") and, decisively, test_rate_limits.py:18-23 which states the attacker/test-supplied fresh XFF lands at "position [-1], not [0]. The backend's client_ip() resolver picks the leftmost entry — i.e. the [edge-prepended] outbound IP." So a spoofed `X-Forwarded-For: 1.2.3.4` is pushed rightward and position [0] is the trusted edge IP — spoofing the leftmost value does NOT rotate the bucket key on the deployed path. The finding's attack scenario ("hit cms-backend-roman.vercel.app directly, bypassing the frontend proxy") also fails: that origin is itself a Vercel deployment, so requests still traverse the Vercel edge and still get the real IP prepended at [0]; there is no non-edge ingress. Additionally the frontend proxy (route.ts:23-27, FE-005) forwards only cookie + content-type, stripping any client-supplied XFF, so client XFF never reaches the backend via the normal path. Finally, even if the limiter were defeated, it is defense-in-depth, not the sole barrier: the admin secret is 128-bit (admin_keys.py:27/66, secrets.token_hex(16)) and login uses argon2 — the BE-011 spec itself calls brute-force "infeasible regardless." The residual "what if redeployed off-Vercel" is speculative and not a vulnerability in the system as architected/deployed.

---

## D-02 — logout delete_cookie omits Secure/SameSite/HttpOnly attributes used to set the cookie

- **Claimed severity:** info · **Dimension:** authn-session · **Verdict:** false_positive
- **Location:** `backend/auth_service/routers/auth.py:43-44`

**Why dismissed:** Read backend/auth_service/routers/auth.py:43-44 — _clear_session_cookie calls response.delete_cookie(SESSION_COOKIE, path="/"). Compared against _set_session_cookie (auth.py:30-40) which sets httponly=True, secure=IS_PROD, samesite="strict"/"lax", path="/". Confirmed Starlette 0.41.3 delete_cookie defaults (secure=False, httponly=False, samesite="lax"), so the clearing Set-Cookie does drop Secure/HttpOnly and downgrades SameSite — the factual asymmetry the finding describes is real. However the SECURITY premise is wrong: per RFC 6265/6265bis the browser cookie storage model keys cookie identity on (name, domain, path) ONLY; Secure/HttpOnly/SameSite do not participate in the replacement/deletion match. A Max-Age=0 Set-Cookie with matching name+path+domain reliably clears the original in all mainstream browsers, so there is no actual deletion failure — the "some edge cases" is hand-waved with no concrete browser. Even granting a hypothetically-persisted cookie, the session is independently killed server-side: logout calls revoke_session(sid) which sets revoked=True (services/sessions.py:115), and validate_session filters .eq("revoked", False) (sessions.py:73), returning None for revoked rows on every later request. The token is dead in the DB. The finding itself labels the impact "cosmetic", "negligible", a "hardening nit". There is no authn/authz bypass, no token leakage, no session fixation, no CIA impact — this is code pedantry, not a security vulnerability, so it is a false positive as a security finding.

---

## D-03 — Admin Bearer brute-force rate limiter keyed on spoofable X-Forwarded-For, defeating its own BE-011 mitigation

- **Claimed severity:** medium · **Dimension:** admin-priv · **Verdict:** false_positive
- **Location:** `backend/auth_service/core/limiter.py:14-18; backend/auth_service/routers/deps.py:52-59`

**Why dismissed:** I read all cited code plus the deployment context. The finding's literal code observation is accurate: client_ip() at backend/auth_service/core/limiter.py:14-17 returns request.headers["x-forwarded-for"].split(",")[0] (leftmost value) with no trusted-hop counting, and deps.py:52-53 keys the Bearer brute-force limiter (check_bearer_attempt) on that value before verify_admin_api_key. In a generic untrusted-network deployment, trusting the leftmost XFF is a real anti-pattern.

But the claimed exploit ("rotate X-Forwarded-For per request -> fresh bucket every time -> 10/min cap bypassed") does NOT hold in THIS system, and the codebase itself documents why. The backend runs behind the Vercel edge (MEMORY: cms-backend-roman.vercel.app, @vercel/python). Two independent in-repo sources state the edge behavior: backend/auth_service/routers/auth.py:58-61 and backend/auth_service/tests_integration/test_rate_limits.py:18-23 both say "Vercel rewrites X-Forwarded-For at the edge (prepends the real client IP), so the per-test fresh XFF header is at position [-1], not [0]. The backend's client_ip() resolver picks the leftmost entry — i.e. the [real outbound] IP." Because Vercel PREPENDS the true peer IP, split(",")[0] yields the real client IP, not the attacker-injected value. This is empirically confirmed: the maintainers had to mark test_rate_limits.py with pytest.mark.skip (lines 28-35) precisely because spoofing XFF could NOT isolate buckets against the live backend — every spoofed request collapsed onto the runner's real outbound IP. That is direct evidence the spoof fails in production; the finding's central premise is contradicted by the platform's documented prepend behavior.

Even setting that aside, impact is negligible: the secret is 128 bits (secrets.token_hex(16) in admin_keys.py:36/66; the finding's 128-bit figure is correct and the bearer_limiter.py "192-bit" docstring is overstated) and argon2-verified, so brute force is infeasible even unthrottled — the finding itself concedes this. The DoS-amplification angle is also weak: verify_admin_api_key runs argon2 only once per attempt (a rotating/non-matching 16-hex prefix lands on the _equalise_timing() single dummy-verify path, admin_keys.py:111-113), and that single hash per request is still gated by the working real-IP limit.

Residual caveat: the protection depends on (a) Vercel always prepending the trusted client IP and (b) the origin never being reachable directly outside the edge. No direct-origin bypass is evidenced in the repo, and all traffic is routed through Vercel, so under the actual architecture the limiter key is non-spoofable. False positive for this deployment.

---

## D-04 — scopes column is stored and selected but never enforced — all admin keys are effectively full-scope

- **Claimed severity:** low · **Dimension:** admin-priv · **Verdict:** false_positive
- **Location:** `backend/auth_service/services/admin_keys.py:104,135-140`

**Why dismissed:** The factual claims are accurate but the security premise is invalid. CONFIRMED facts: verify_admin_api_key selects `scopes` (admin_keys.py:104) yet the returned principal (admin_keys.py:135-140) omits it; a backend-wide grep shows `scopes` is never read in any authZ path — only the migration default `'["agent"]'` (2026_05_06_admin_api_keys.sql:12), the SELECT, and a test fixture (test_admin_keys.py:26) reference it. So scopes is genuinely non-enforced dead metadata.

WHY IT IS NOT A REAL VULN: The finding assumes scopes was meant to, or could, narrow a key — and that an `['agent']` key is a lesser principal that escalates to the full admin surface. The code refutes this. (1) mint_admin_api_key (admin_keys.py:53-82) takes NO scopes parameter and never writes the column; every key inherits the DB default `["agent"]`. There is no code path anywhere that mints a key with a different scope, so the claimed 'narrow agent key vs root admin key' distinction does not exist — all keys are byte-for-byte equivalent in privilege. (2) The actual gate is users.is_admin, joined from the users table and checked at admin_keys.py:124-125; verify returns None for any non-admin/inactive user (test_returns_none_for_non_admin passes). (3) The mint operator script (scripts/mint_admin_api_key.py:53-64) queries `.eq("is_admin", True)` and REFUSES to mint for non-admin users, so a key is useless unless bound to a full admin. The `["agent"]` default is a consumer label (the Connector automation), not a privilege tier. No least-privilege boundary was ever designed, wired, or shipped — scopes is vestigial column noise, not a bypassable control.

---

## D-05 — Slack url_verification challenge is reflected unauthenticated before signature check

- **Claimed severity:** info · **Dimension:** public-tokens · **Verdict:** false_positive
- **Location:** `backend/auth_service/routers/slack_events.py:29-32`

**Why dismissed:** I read backend/auth_service/routers/slack_events.py and backend/auth_service/services/slack_signature.py. The evidence is accurate: at slack_events.py:31-32 the handler returns payload.get("challenge", "") with media_type="text/plain" BEFORE the HMAC check (which runs at line 36 via slack_signature.verify). However, this is the required, documented Slack Events API URL-verification handshake (docstring lines 4-5 and 29-30 note it), which Slack mandates be answered unsigned during one-time app setup — the signing secret may not even be configured at that point. The signature service itself (slack_signature.py:17-29) is correctly implemented: HMAC-SHA-256, 5-minute replay window, and hmac.compare_digest constant-time comparison. The "signature bypass" is illusory: the url_verification branch returns immediately (line 32), reaching no dedup, no slack_handler dispatch (lines 39-57 never execute), no DB write, and persisting nothing. It is not XSS — content-type is text/plain (inert in a browser) and the route is POST-only (@router.post, line 21), so it cannot be triggered by browser navigation, and CORS would prevent a cross-origin caller from reading the response anyway. The only effect is echoing back attacker-supplied input the attacker already controls (no information disclosure). The finding's own description rates it info/negligible and recommends "acceptable as-is per Slack docs," which is correct. This is expected protocol behavior, not an exploitable vulnerability.

---

## D-06 — Git ref-name allowlist permits leading dash, enabling potential git argument injection in Solver Agent

- **Claimed severity:** low · **Dimension:** injection · **Verdict:** false_positive
- **Location:** `backend/auth_service/models/schemas.py:387-397; agents/Solver - Issues/repo.py:42-76`

**Why dismissed:** I read all cited code. The regex claim is factually accurate: schemas.py:395 uses re.fullmatch(r"[A-Za-z0-9._/-]+", v) (re is imported at line 1; the validator runs), which permits a leading dash, so production_branch="-x" / "--upload-pack=..." passes validation. The data flow is also real: projects.production_branch -> clone_repo.py:25 -> repo.clone_and_reset_to_prod(prod_branch=...) -> two subprocess.run git calls (list-arg form, no shell=True), so the reviewer correctly rules out shell injection.

However, the asserted *argument-injection* outcome does not occur at EITHER call site. (1) repo.py:44-56 is `git clone ... --branch <prod_branch> <url> <dest>` — prod_branch is the OPERAND of --branch, not a bare positional; git consumes the token after --branch as the branch name even when it starts with '-' (e.g. `--branch -x` => branch name "-x"), so it is not reinterpreted as an option. Worst case is a failed clone on an invalid ref. (2) repo.py:76 is `git checkout -B <dev_branch> origin/<prod_branch>` — prod_branch is concatenated into `origin/<prod_branch>`, producing token `origin/-x`, which does NOT begin with a dash and cannot be an option. There is no current path where the value lands as a leading-dash positional. The finding itself concedes this ("substantially limits exploitability", risk only "after future refactors").

Privilege/trust: the only writer is PATCH /admin/projects/{slug} (workspace.py:565-575), gated by admin_user_via_bearer_or_sid — admin Bearer key or admin sid only. That actor already supplies the solver's GitHub token (repo.py:42 SOLVER_GITHUB_TOKEN) and the repo_slug/branches the agent operates on, so they have strictly greater capability than this bug would grant.

Net: accurate code reading and a valid defense-in-depth nit (the allowlist is looser than its stated goal of excluding dangerous leading-dash refs), but not an exploitable vulnerability in this system. Downgrade from low to info.

---

## D-07 — Scraper worker fully trusts scrape_jobs.params (direct_url/region/bbox) deserialized from the DB; URL safety rests on a single allowlist

- **Claimed severity:** low · **Dimension:** ssrf-outbound · **Verdict:** false_positive
- **Location:** `scraper/src/scraper/cli.py:287-289, scraper/src/scraper/google_maps.py:799-803`

**Why dismissed:** I read every cited path. The finding's technical claims are accurate but, by its own repeated admission ("a web/anon caller cannot currently inject a direct_url", "Today the allowlist holds, so impact is limited to defense-in-depth"), it describes a hypothetical future regression, not a present, exploitable issue. Concretely:

1) Worker model: scraper/src/scraper/cli.py:287 does ScrapeParams.model_validate(job["params"]) using scraper/src/scraper/models.py:33-63, which DOES include direct_url (l.53), region (l.56), bbox (l.57). Confirmed.

2) API model split: the backend job-creation path uses a DIFFERENT ScrapeParams (backend/auth_service/models/schemas.py:493-503) that has NONE of direct_url/region/bbox. admin_scrape_jobs.py:47 inserts body.params.model_dump() — so the only fields that can ever be written via the API are the safe subset. The web/admin-reachable lane physically cannot carry direct_url. Confirmed.

3) AuthZ on the write path: admin_scrape_jobs.py:42-43 gates create_job behind admin_user_via_bearer_or_sid (deps.py:42-75) — requires a valid admin API key (bearer, rate-limited) or an admin session with is_admin. No anon/web write path exists.

4) DB-level guard: backend/migrations/2026_05_17_lead_scraper.sql:141 enables RLS on scrape_jobs with NO permissive policy; the comment (l.136-138) states anon access "fails closed". Only the backend service-role key (server-side, not exposed to frontend) can write.

5) SSRF chokepoint: scraper/src/scraper/urls.py — expand_if_short() requires is_google_maps_url() (host in _MAPS_HOST_SUFFIXES: google.com/maps.google.com/maps.app.goo.gl/goo.gl only), full URLs must contain /place/ or !1s, and short links are followed via urllib only from allowlisted hosts with the resolved URL re-validated as a place page. The only caller, google_maps.py:803, runs expanded value through canonicalize_place_url which rebuilds from the feature id. The guard is intact today.

The only path that populates direct_url is the operator-run `scrape-url` CLI command (local, trusted), per the docstring at google_maps.py:790-792. The "over-permissive PostgREST/anon RPC surface" the finding leans on is a separate, unverified finding and is not evidence of exploitability here. Net: trust boundary is currently sound (model split + admin auth + RLS fail-closed + Google-only allowlist). This is valid hardening advice but not a present vulnerability; "low" overstates it.

---

## D-08 — dependabot-auto-merge.yml has no top-level concurrency guard and grants pull-requests:write for every pull_request event

- **Claimed severity:** low · **Dimension:** ci-workflows · **Verdict:** false_positive
- **Location:** `.github/workflows/dependabot-auto-merge.yml:18-27`

**Why dismissed:** Read the actual file at .github/workflows/dependabot-auto-merge.yml. The evidence matches: line 18 `on: pull_request`, lines 20-22 top-level `permissions: contents: write / pull-requests: write`, line 26 `if: github.actor == 'dependabot[bot]'`. All steps use only `secrets.GITHUB_TOKEN` (lines 33,41,49,55) — no PAT or org-wide secret. Verified no `pull_request_target` exists anywhere in the workflows dir.

The finding itself concedes "not directly exploitable," and its one concrete technical claim is wrong: the actor check on line 26 is a JOB-LEVEL `if`, which GitHub evaluates BEFORE provisioning a runner. A non-Dependabot PR therefore skips the entire job — no shell spins up, no step runs, the declared write token is never minted into any step. So the asserted "spin up the job shell before the actor check short-circuits" window does not exist.

Two factual items are true but security-neutral: (a) there is no `concurrency:` block, but `gh pr review --approve` and `gh pr merge --auto` are idempotent, so racing reruns cause at most redundant API calls, not a security impact; (b) permissions are top-level rather than job-level, which is a defense-in-depth style preference with no exploitable delta because the only job that uses the token is actor-gated to dependabot[bot].

Critically, because the trigger is `pull_request` (not `pull_request_target`), GitHub forcibly downgrades `GITHUB_TOKEN` to read-only and withholds secrets for fork PRs regardless of the declared `permissions:` — so the broad grant cannot be abused by an external attacker. This nets to a hardening/least-privilege nit, not a vulnerability.

---

## D-09 — auto-merge-dev→master gate trusts workflow names and queries runs without verifying the workflow_run actor/source

- **Claimed severity:** medium · **Dimension:** ci-workflows · **Verdict:** false_positive
- **Location:** `.github/workflows/auto-merge-dev-to-master.yml:50-91,130-131`

**Why dismissed:** I read the cited workflow and the surrounding CI/E2E/branch-protection setup. The finding's factual premise is partly correct but its security conclusion (an exploitable promotion-to-prod bypass) is not supported, because the gh-api loop is a pre-flight optimization, not the enforcement boundary.

WHAT IS TRUE: In auto-merge-dev-to-master.yml:73-78 the gate query is `gh api repos/.../actions/runs?head_sha=$SHA&per_page=20 --jq "[.workflow_runs[] | select(.name==\"$WF\")][0] | .conclusion"`. It filters only on `head_sha` + display name `.name` and takes `[0]` (newest). It does NOT pin `event`, `head_branch`, or workflow file path. So a `workflow_dispatch` run named CI/E2E for that SHA could in principle satisfy this particular check. The dev->prod path is also fully automated by design (workflow header lines 1-22; no human gate beyond CI/E2E green).

WHY IT IS NOT EXPLOITABLE:
1. Branch protection — not the gh-api loop — is the real gate. docs/DEVELOPMENT.md:26 and :153/:185 document that `master` has GitHub-native required status checks `CI complete (gate)` + `E2E complete (gate)` with `enforce_admins=true`. The workflow's `git push origin master` (line 131) is independently re-validated by GitHub against the pushed SHA. If those checks are not genuinely green for that SHA, GitHub rejects the push (note the admin-bypass runbook at DEVELOPMENT.md:183-200 exists precisely because the GITHUB_TOKEN push is subject to enforce_admins). The prior security audit analyzed this exact mechanism (CI-008, line 882): "pre-flight check on head_sha ensures status checks went green on that exact SHA before fast-forward push. Branch protection then validates the same checks on the same SHA when push lands. No bypass."
2. The "manually dispatched green run defeats the test set" sub-claim is incorrect. Both ci.yml (line 19 `workflow_dispatch:`) and e2e.yml (line 10) run their full job graph on dispatch — the CI `changes` job sees an empty `before` (`ci.yml:52`) so it runs every job, and the `ci-complete`/`e2e-complete` aggregators (ci.yml:199-228, e2e.yml:210-237) still gate. You cannot obtain a green run named CI/E2E without the actual tests + aggregator passing for that SHA, and the display name is fixed by the repo's own workflow files at that ref — an attacker cannot register a different workflow under the same name without committing that file.
3. The genuine residual concern (whoever can push to dev gets continuous promotion) is a deliberate design choice and is already tracked separately as CI-009 / PROC-004 "dev branch has no branch-protection" (security-audit.md:537-543, Medium). It is not a novel vulnerability introduced by this workflow.

The recommendation to pin event/branch/path in the query is reasonable robustness hardening (it would make the pre-flight match the intent more tightly and avoid a confusing skip), but native required status checks already exist on master, so it is defense-in-depth, not closing an exploitable hole.

---

## D-10 — CLAUDE_CODE_OAUTH_TOKEN written to a credentials file via heredoc that does not JSON-escape the secret

- **Claimed severity:** info · **Dimension:** ci-workflows · **Verdict:** false_positive
- **Location:** `.github/workflows/solver-agent.yml:69-74`

**Why dismissed:** Verified .github/workflows/solver-agent.yml:69-74. The code is exactly as cited: `cat > "$HOME/.claude/.credentials.json" <<'EOF'` followed by a JSON line embedding `${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}` raw, then `chmod 600`. The finding's technical facts are all correct: (1) GitHub Actions interpolates `${{ secrets.* }}` into the run-script text BEFORE bash executes, so the quoted heredoc only blocks shell `$`-expansion and does nothing to JSON-escape the inlined secret; (2) a token containing `"`, `\`, or newline would malform/restructure the JSON. However, this is NOT an exploitable security issue. The only value involved is `CLAUDE_CODE_OAUTH_TOKEN`, a trusted repo secret set by the repo owner — there is no attacker-controlled input reaching this substitution. The finding itself states "Not externally exploitable (value is a trusted secret)" and self-classifies as info / "Robustness / hardening". The worst realistic outcome is a malformed credentials file causing a self-inflicted auth/availability failure, not any breach of a security boundary (no disclosure, injection, escalation, or cross-trust-boundary impact). Claude OAuth tokens are base64url-style (alphanumeric/-/_) and don't contain JSON-special chars, so even the robustness risk is largely theoretical. The reviewer's adjacent mention of "token-on-disk during the untrusted-prompt step" (env var at line 92 + persistent .credentials.json while the client-issue-driven Claude step at lines 76-100 runs) is a genuinely more serious concern, but it is explicitly out of scope for THIS finding, which is strictly about JSON-escaping. As a security vulnerability, this is a false positive; the underlying observation and the jq-based recommendation are valid hardening but carry no exploitable impact.

---

## D-11 — Externally-sourced lead URLs (website/facebook/instagram/source) rendered as anchor href without scheme allowlist

- **Claimed severity:** low · **Dimension:** scraper · **Verdict:** false_positive
- **Location:** `frontend/src/components/admin/leads/sections/ContactSection.tsx:216-217, frontend/src/components/admin/leads/LeadDetailDrawer.tsx:214-215; values originate from scraper google_maps.py:597 (_safe_attr PLACE_WEBSITE_BUTTON 'href') and dedup.classify_web_presence`

**Why dismissed:** The render sink is correctly described: ContactSection.tsx:216-217 and LeadDetailDrawer.tsx:214-215 (plus the drawer's local Row at 481-485) all emit `<a href={value} target="_blank">` with no client-side scheme allowlist. However, every realistic data-ingress path into those fields is already gated, which the finding underweights. (1) Manual admin edits flow through `LeadUpdate` (schemas.py:554-581), where website_url/facebook_url/instagram_url/menu_url are typed `_LeadUrl` = AfterValidator(_http_url_validator). That validator (schemas.py:17-27) strips and raises ValueError("URL must start with http:// or https://") for anything not beginning with `http://`/`https://`, so `javascript:`/`data:`/`file:` schemes are rejected with a 422 at PATCH /admin/leads/{id} (admin_leads.py:85-87). The finding concedes "the backend _LeadUrl validator is the only gate" — but that gate IS an effective scheme allowlist, so the manual-edit vector it worries about is closed. (2) `source_url`, rendered at LeadDetailDrawer.tsx:214, is not present in LeadUpdate at all — it is not admin-editable and is only ever a scraper-produced Google Maps place URL. (3) The scraper path (google_maps.py:597 `_safe_attr(..., 'href')`; dedup.classify_web_presence at dedup.py:87-104 only host-classifies, never injects a scheme) yields a browser-resolved http(s) href from Google's normalized outbound website button — the finding itself rates this "low / theoretical." So no realistic path delivers a non-http scheme to the render. This is a valid defense-in-depth note (a redundant render-time scheme check would be belt-and-suspenders), not an exploitable bug in this system.

---

## D-12 — Grid fan-out guard can be fully disabled (max_cells=0) enabling unbounded scrape work

- **Claimed severity:** low · **Dimension:** scraper · **Verdict:** false_positive
- **Location:** `scraper/src/scraper/models.py:61 and scraper/src/scraper/google_maps.py:762-767 (_build_grid_queries)`

**Why dismissed:** The cited code is accurate but the security claim is not. models.py:61 does declare `max_cells: int = 300  # 0 = unlimited`, and google_maps.py:762-767 does skip the GridTooLargeError guard when `max_cells == 0` (`if params.max_cells and len(grid) > params.max_cells:`). The grid is fully materialized via `list(grid_centers(*bbox, ...))` before the guard, so a huge bbox with max_cells=0 builds an unbounded cell list. Cell-split fan-out (google_maps.py:893-907) is itself bounded (4 sub-cells, max_split_depth=2). So the "0 = unlimited footgun" exists. However, the finding mis-states reachability. The grid/region/bbox/max_cells fields exist ONLY in the scraper package's ScrapeParams (scraper/src/scraper/models.py). The BACKEND's ScrapeParams (backend/auth_service/models/schemas.py:493-503), which is what the admin endpoint actually binds via ScrapeJobCreate.params (schemas.py:634-635), defines ONLY legacy text-search fields — no max_cells, region, bbox, categories, grid_cell_km, split_on_saturation, or max_split_depth — and has NO model_config, so Pydantic's default extra=\"ignore\" silently drops any of those fields. The admin POST /admin/scrape-jobs handler (admin_scrape_jobs.py:42-52) stores body.params.model_dump() into scrape_jobs.params, meaning any max_cells=0 / region / bbox an admin sends over HTTP is discarded and never reaches the worker. Grid mode is therefore reachable ONLY through the local Typer CLI (cli.py:88-127 `scrape`, 187-243 `scrape-country`), which runs on the operator's own machine/worker. In `scrape-country` the per-municipality max_cells is auto-scaled to the exact planned cell count (cli.py:226) so the engine guard never trips by design, and --max-cells-cap (cli.py:195) gives an extra skip knob. No authentication or authorization boundary is crossed; this is a local-CLI operator control, not an app-surface security issue. The reviewer's stated attack path (admin-gated POST /admin/scrape-jobs) does not actually accept these parameters in this codebase.

---

## D-13 — Frontend ships two copies of the same animation library (framer-motion + motion)

- **Claimed severity:** info · **Dimension:** deps-supplychain · **Verdict:** false_positive
- **Location:** `frontend/package.json:35,38`

**Why dismissed:** false

---

## D-14 — client_ip() trusts the leftmost (client-supplied) X-Forwarded-For value, letting an attacker rotate IPs to bypass all per-IP rate limits

- **Claimed severity:** high · **Dimension:** ratelimit-dos · **Verdict:** false_positive
- **Location:** `backend/auth_service/core/limiter.py:14-18; used by routers/auth.py:62, routers/forms.py:20,91,255, routers/booking.py:372,575,637,852, routers/deps.py:52-53`

**Why dismissed:** The finding's load-bearing premise is factually inverted for this deployment. It asserts "edge proxies APPEND the real client IP to the right rather than overwriting the left," so split(",")[0] returns attacker-controlled data. That is the generic nginx model, not Vercel's behavior — and this app runs behind Vercel.

What the code actually does (backend/auth_service/core/limiter.py:14-18): client_ip() reads x-forwarded-for and returns split(",")[0], the leftmost entry, falling back to get_remote_address. The choice of [0] is deliberate and documented against Vercel's specific edge behavior:
- backend/auth_service/routers/auth.py:58-59 comment: "Vercel rewrites X-Forwarded-For at the edge (prepends the real client IP)."
- backend/auth_service/tests_integration/test_rate_limits.py:18-27 documents the same thing in detail: on the deployed backend, a client-supplied fresh XFF lands at position [-1] (rightmost), and client_ip()'s leftmost pick resolves to the real connecting IP that Vercel prepended. The integration tests that rely on spoofing XFF for bucket isolation are explicitly SKIPPED for the deployed backend precisely because Vercel prepends the true client IP to the left, defeating client-side XFF control.

So on Vercel, the leftmost XFF token is written by the trusted edge (the trust boundary), not by the client. An external attacker reaching *.vercel.app always transits that edge, which prepends its observed client IP; the client cannot insert a value to the left of Vercel's. Therefore rotating X-Forwarded-For per request does NOT produce a fresh bucket — every request from one source IP still hashes to that source's Vercel-prepended IP. The described bypass of /auth/login (auth.py:62), /forms/* (forms.py:20 via _form_bucket), /booking/* (booking.py:372,575,637,852), and the admin bearer guard (deps.py:52-53) does not work.

The finding's own recommendation ("take the RIGHTMOST entry") would be actively harmful here: on Vercel the rightmost entry IS the attacker-spoofed value, so adopting it would CREATE the vulnerability the finding claims to fix.

Caveat (separate, pre-existing, not this finding): both limiters are in-memory/per-process — slowapi default storage and bearer_limiter.py's documented process-local Bucket — so on serverless the counters fragment per warm instance. That weakens absolute throttle ceilings but is acknowledged in bearer_limiter.py's docstring and is unrelated to the XFF-spoofing claim under review.

---
