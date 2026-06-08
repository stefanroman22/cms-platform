# Medium findings

_Schedule soon. Reflected XSS, CSRF, info disclosure, weak rate limiting, or authZ gaps on writes._

**10** finding(s). See [`../FINDINGS.md`](../FINDINGS.md) for live status. Reviewed 2026-06-07.

---

<a id="sec-005"></a>

## SEC-005 — Admin issue-status update endpoint lets the Solver mark ANY issue done cross-project, decoupled from whether the agent actually fixed it

| | |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Category** | Token scope / authorization |
| **Dimension** | agents |
| **Location** | `backend/auth_service/routers/issues.py:276-344; agents/Solver - Issues/backend_api.py:23-37` |
| **Reviewer confidence** | medium |
| **Verifier verdict** | partially_confirmed (adjusted: medium) |
| **First seen** | 2026-06-07 |

**Description**

finalize.py PATCHes /admin/issues/{id}/status with status=done using CMS_API_TOKEN. The admin route `admin_update_issue_status` explicitly 'Skips the project-access ownership check — the solver acts cross-project.' Combined with the Supabase advisor note that the security-definer RPCs claim_next_solver_issue / claim_specific_solver_issue are EXECUTE-able by anon/authenticated via PostgREST, the solver pipeline's privileged surface (claim any issue, mark any issue done cross-project) is broad. The CMS_API_TOKEN is a single admin bearer with no per-issue scoping; anyone who obtains it (see the token-exfil finding) can mark arbitrary issues resolved across all tenants and fire the S1.5 promotion Slack flow.

**Attack scenario**

If CMS_API_TOKEN leaks (e.g. via the agent prompt-injection exfil vector) an attacker can PATCH any tenant's issue to done and trigger the resolved-issue Slack message that primes Stefan to ✅-promote whatever is on that repo's cms-preview.

**Evidence**

```text
async def admin_update_issue_status(
    issue_id: str,
    body: IssueStatusRequest,
    request: Request,
):
    """Admin/agent path ... Skips the project-access ownership check — the solver acts cross-project."""
    user = await admin_user_via_bearer_or_sid(request)
```

**Adversarial verification**

The finding bundles two claims; I verified each independently.

PRIMARY CLAIM (the title — admin status endpoint is a privileged cross-project surface): FALSE POSITIVE as an independent vulnerability. `admin_update_issue_status` (backend/auth_service/routers/issues.py:280-344) is gated by `admin_user_via_bearer_or_sid` (deps.py:42-75), which on the bearer path calls `verify_admin_api_key` (admin_keys.py:85+) — an argon2-hashed, revocable, expiry-checked key that must map to an `is_admin`+`is_active` user, and is rate-limited (10/min/IP, BE-011) and timing-equalised. The "skips the project-access ownership check" comment is accurate but inconsequential: `require_project_access` (deps.py:21-39, line 37) already grants admins access to ALL projects, and the user-facing status route (issues.py:219-273) itself requires `user.is_admin` (line 228-232). So "cross-project mark-done" is intended admin/automation behavior, not an escalation. The entire attack scenario is explicitly conditional on CMS_API_TOKEN leaking ("see the token-exfil finding") — i.e. it has no exploitability of its own. "Decoupled from whether the agent fixed it" is a defense-in-depth nit, not an exploitable flaw.

SECONDARY CLAIM (the claim_* RPCs are EXECUTE-able by anon/authenticated): CONFIRMED LIVE. The migration backend/migrations/2026_05_16_solver_agent_columns.sql:79-80 intends REVOKE ALL FROM PUBLIC + GRANT to service_role only, but that REVOKE was never applied to the second function and was lost on a later CREATE OR REPLACE. I queried live ACLs on project xeluydwpgiddbamysgyu: both `claim_next_solver_issue` AND `claim_specific_solver_issue` have EXECUTE granted to `anon` and `authenticated` (and claim_specific also has the PUBLIC default `-` grantee). Supabase security advisors independently flag lints 0028 (anon) and 0029 (authenticated) "Public Can Execute SECURITY DEFINER Function ... via /rest/v1/rpc/...", plus 0011 mutable search_path on both. The legitimate solver uses SUPABASE_SERVICE_ROLE_KEY (agents/Solver - Issues/db.py:24), so revoking anon/authenticated EXECUTE breaks nothing. The scope-checklist (security/scope-checklist.md:44) lists this grant as an unverified TODO, not a cleared item.

Net: the headline mechanism is a false positive, but the RPC-grant fact the finding relies on is real and independently exploitable without any token leak, so partially_confirmed.

**Exploitability:** Admin-endpoint path (titled finding): NOT independently exploitable — requires a valid, non-revoked admin API key, which is exactly the credential being protected; no escalation beyond normal admin authority. Only realized if CMS_API_TOKEN is already compromised (a separate finding).

RPC-grant path (the real, live-confirmed part): exploitable by ANY unauthenticated internet caller. Supabase project anon keys are public (PostgREST accepts them at https://xeluydwpgiddbamysgyu.supabase.co/rest/v1/rpc/claim_specific_solver_issue with apikey: <anon>). Both SECURITY DEFINER functions run as the definer and are granted to anon, so an attacker who knows/guesses an issue UUID (or just calls claim_next_solver_issue with no args) can: (1) read back any tenant's issue title/description/priority/status/revision_feedback (cross-tenant info disclosure, RLS bypassed because SECURITY DEFINER), and (2) flip agent_status='claimed'/agent_claimed_at=now() on arbitrary issues, stalling the Solver pipeline for up to the 15-min stale window and griefing auto-fix across all tenants. No admin token required. This is why I raised severity to medium: it is an unauthenticated cross-tenant read + pipeline-DoS, independent of the token-leak premise the titled finding depends on. Fix: REVOKE EXECUTE ... FROM anon, authenticated, PUBLIC on both claim_* functions (service_role already covers the real caller) and pin search_path.

**Recommendation**

Scope the solver's automation credential to only the status transition it needs, and require that admin_update_issue_status verify the issue was actually claimed/committed by the solver (e.g. agent_commit_sha present and recent) before allowing done. Tighten the anon/authenticated EXECUTE grants on the claim_* RPCs (revoke from anon/authenticated; backend uses service role).

---

<a id="sec-006"></a>

## SEC-006 — Solver Agent auto-commits and force-pushes attacker-influenced file changes to cms-preview, which a single Slack ✅ promotes to client production

| | |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Category** | Untrusted-input → privileged action |
| **Dimension** | agents |
| **Location** | `agents/Solver - Issues/finalize.py:42-49; agents/Solver - Issues/repo.py:85-101; backend/auth_service/services/github_merge.py:25-46` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: medium) |
| **First seen** | 2026-06-07 |

**Description**

After the model edits files driven by the client-controlled issue text, finalize.py unconditionally commits and force-with-lease pushes whatever is in the working tree to the client's `cms-preview` branch (`repo.commit_and_push`). The commit message is `fix: {issue_title}` — also client-controlled. The only gate before this reaches live production is a human Slack ✅, which calls github_merge.fast_forward to promote cms-preview → production (triggering a Vercel prod deploy). The agent's instruction-level prohibitions ('git operations FORBIDDEN', 'minimum change') are prompt text, not enforced controls; a successful prompt injection that steers the model to write extra files (e.g. a malicious serverless route, an exfiltrating build step, an injected <script>) results in those changes being pushed to cms-preview automatically. Production promotion then depends entirely on Stefan eyeballing the diff in the Slack flow.

**Attack scenario**

Client files an issue 'Footer copyright year is wrong' but embeds injection steering the agent to also add an innocuous-looking change plus a hidden third-party <script src> or an analytics endpoint pointing at attacker infrastructure. The diff is small and plausible; Stefan ✅ the resolved message; fast_forward promotes it to production; the malicious script now executes in every visitor's browser on the client's live site.

**Evidence**

```text
sha = repo.commit_and_push(
    path=REPO_DIR,
    issue_id=issue["id"],
    issue_title=issue["title"],
)
...
_run(["git", "-C", path, "add", "-A"])
_run(["git", "-C", path, "commit", "-m", message])
_run(["git", "-C", path, "push", "--force-with-lease", "origin", "HEAD"])
```

**Adversarial verification**

The mechanism is real and the cited code supports it. Issue title/description are client-controlled text: create_issue (backend/auth_service/routers/issues.py:73-93) stores body.title/body.description verbatim, and claim_issue.py:145,148 injects them directly into the agent prompt's <issue> block. The headless agent runs with --allowed-tools "Read,Edit,Write,Glob,Grep,..." (.github/workflows/solver-agent.yml:98) — Write/Edit have NO path restriction, so a prompt-injected model can create/modify arbitrary files (new serverless route, build step, injected <script>) anywhere in ./client-repo/. --disallowed-tools (line 99) only blocks git push/commit/rm/WebFetch/WebSearch — not a content/scope gate. finalize.py:42-49 then unconditionally calls repo.commit_and_push (repo.py:85-101 = git add -A; commit -m "fix: <client title>"; push --force-with-lease) with zero diff inspection. Approval (slack_handler.py:21-85) fires github_merge.fast_forward (services/github_merge.py:25-46) promoting the pinned agent_commit_sha to production_branch → Vercel prod deploy. The "git FORBIDDEN / minimum change / don't touch CI" lines (claim_issue.py:132,222-224) are prompt text aimed at the model, not enforced controls — exactly as the finding states. The approval gate is in fact WEAKER than the finding claims: _build_resolved_blocks (slack_notify.py:119-165) surfaces only Title + Resolver + Preview link in the Slack approval message — NO diff is shown, so the default ✅ path is blind. Two corrections lowering severity from high to medium: (1) require_project_access (deps.py:37) restricts issue creation to the project's own owner (user_id == user.id) or an admin — this is NOT an anonymous/cross-tenant attacker; the threat actor is an authenticated/compromised client account acting on its own project. (2) The injection must additionally survive the multi-step self-review protocol AND a human out-of-band approval that CAN catch it if Stefan inspects the preview. So it is a genuine design weakness (untrusted input → privileged force-push + one-click prod promotion with no machine-checked diff gate and a diff-less approval UI), but not a trivially-remote, unauthenticated exploit.

**Exploitability:** Trigger requires an authenticated user who is the owner of the target project (deps.py:37 require_project_access). That client files an issue whose title/description embeds prompt-injection steering the model to make its small "fix" plus an innocuous-looking malicious addition (e.g. a third-party <script src> or an analytics/exfil endpoint, or a serverless route). solver_dispatch fires the workflow within ~30s; the model edits files (Write/Edit unrestricted), finalize.py force-pushes the whole working tree to that project's cms-preview, and the commit SHA is pinned. The only thing between that and the client's LIVE production site is Stefan's single ✅ reaction — and the Slack approval message shows only the issue title + a preview link, no diff (slack_notify.py:141-143), so the realistic default is a blind approve. On approval, fast_forward promotes the pinned commit to the production branch and Vercel deploys it; the injected script then runs in every visitor's browser on the client's live domain, attributed to Roman Technologies' automation. What the attacker gets: attacker-controlled JS/serverless code shipped to the production site of a project they control (self-XSS/supply-chain against their own visitors, brand abuse, or a staging ground if the client account is compromised/phished). Mitigating factors: needs a valid project-owner session AND a human ✅ that could catch the change if the diff were actually inspected. Recommended hardening matches the finding: a machine-checked diff-policy gate before push/promote (reject new <script>, new network endpoints/deps, CI/env/workflow changes, or files outside a per-issue allowlist), surface the full diff + file count/paths in the Slack approval, and run a second review model that only sees the diff vs the original issue to flag scope creep.

**Recommendation**

Add an automated diff-policy gate before push and before promotion: reject diffs that add <script> tags, new network endpoints, new dependencies, CI/workflow/env changes, or touch files outside a per-issue allowlist. Surface the full machine-checked diff (not just the title) in the Slack approval message and require the approver to confirm file count/paths. Consider running the agent's output through a second review model that only sees the diff and the original issue, flagging scope creep.

---

<a id="sec-007"></a>

## SEC-007 — Dependabot auto-merge self-approves and merges minor/major-range bumps without independent review; a compromised dependency can reach master/prod

| | |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Category** | Supply chain / auto-merge gating |
| **Dimension** | ci-workflows |
| **Location** | `.github/workflows/dependabot-auto-merge.yml:36-50` |
| **Reviewer confidence** | medium |
| **Verifier verdict** | partially_confirmed (adjusted: medium) |
| **First seen** | 2026-06-07 |

**Description**

The workflow auto-approves (`gh pr review --approve` using the workflow's own GITHUB_TOKEN) and enables auto-merge for ANY semver-patch OR semver-minor Dependabot PR across all 5 ecosystems (pip backend, pip agent, npm frontend, npm e2e, github-actions). The bot self-approval can satisfy a 'require 1 approval' branch-protection rule with no human ever looking at the diff, and `gh pr merge --auto` lands it as soon as CI is green. CI (ci.yml) installs npm deps with `--ignore-scripts` and pip with `--require-hashes`, which blocks install-time postinstall hooks and tampered artifacts — but it does NOT stop malicious code that executes at RUNTIME (e.g. a backdoored minor release of a transitive lib that runs when imported in the FastAPI app or rendered in Next.js). Because auto-merge-dev-to-master fast-forwards dev→master and Vercel deploys master, an auto-merged poisoned minor bump reaches production with zero human review. 'minor' is a wide blast radius (e.g. left-pad/event-stream-style takeovers ship as minor).

**Attack scenario**

An attacker compromises a transitive npm/pip dependency and publishes a malicious minor release. Dependabot opens a grouped minor PR; this workflow auto-approves and auto-merges it once CI passes (CI does not execute the malicious runtime path). dev fast-forwards to master, Vercel deploys, and the backdoor runs in production with the service-role key in scope.

**Evidence**

```text
- name: Approve PR (patch + minor only)
        if: |
          steps.meta.outputs.update-type == 'version-update:semver-patch' ||
          steps.meta.outputs.update-type == 'version-update:semver-minor'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: gh pr review --approve "${{ github.event.pull_request.html_url }}"
```

**Adversarial verification**

I read the cited workflow and the surrounding pipeline. The mechanical facts hold: dependabot-auto-merge.yml:36-50 auto-approves (gh pr review --approve, GITHUB_TOKEN) AND enables auto-merge (gh pr merge --auto, line 50) for BOTH version-update:semver-patch AND semver-minor, gated only on dependabot/fetch-metadata. .github/dependabot.yml confirms all 5 ecosystems (pip /backend, pip /agents, npm /frontend, npm /e2e, github-actions) and that minor+patch are GROUPED (lines 18-19, 30-31, 42-43, 54-55), so one grouped minor PR can carry many bumps. CI hardening is install-time only: ci.yml:132/163 pip --require-hashes, ci.yml:185 npm ci --ignore-scripts — these block tampered artifacts and postinstall hooks but NOT code that runs at import/render of a legitimately-published-but-backdoored minor release. The promotion chain is real: auto-merge-dev-to-master.yml fast-forwards dev→master on green CI+E2E, and DEVELOPMENT.md:159-160 confirms Vercel auto-deploys master; backend/auth_service/core/config.py:117-125 requires SUPABASE_SERVICE_ROLE_KEY in prod, so a runtime-malicious backend dep gets RLS-bypassing DB access. So the OUTCOME the finding describes (a poisoned minor bump auto-reaching prod with no human review) is supported.

However, the finding's CENTRAL MECHANISM is wrong for this repo. It claims the bot self-approval 'can satisfy a require 1 approval branch-protection rule.' Branch protection here sets required_pull_request_reviews: null (docs/superpowers/plans/2026-05-02-e2e-merge-gate.md:1789 and docs/superpowers/specs/2026-05-07-security-audit.md:241), and DEVELOPMENT.md:153 states master requires only the two status-check aggregators (CI complete (gate) + E2E complete (gate)) — there is NO approval requirement. So the gh pr review --approve step is effectively inert; merges land because CI is green, not because a bot approved. The recommendation to 'not let GITHUB_TOKEN count as the required approval / require a CODEOWNER review a bot cannot satisfy' is largely moot since no review gate exists. Net: the supply-chain/process risk is genuine and worth hardening (drop minor from auto-merge, add cooldown/allowlist), but it is a defense-in-depth gap that requires a prior upstream third-party compromise to exploit — not a directly attacker-triggerable flaw in this code — and the stated self-approval bypass is inaccurate. High overstates it for this threat model; medium fits.

**Exploitability:** Not directly triggerable by any actor against this system as-is; it requires a precondition outside the repo: an attacker must first compromise an upstream npm/pip transitive package (or a github-actions tag) and ship a malicious patch/minor release. Once that release exists, the chain is automatic with no human in the loop: Dependabot opens a grouped patch/minor PR → dependabot-auto-merge.yml auto-enables merge → green CI (which never executes the malicious runtime path) satisfies the only branch-protection gate (status checks; reviews are disabled) → dev fast-forwards to master → Vercel deploys → the backdoor runs in the FastAPI backend with the Supabase service-role key (RLS bypass) or in the Next.js frontend. The would-be 'approval bypass' is a non-issue because there is no approval requirement to bypass. Realistic impact: full read/write of all tenant data via service-role on the next weekly Dependabot run after an upstream takeover. Likelihood is gated by upstream-compromise frequency plus the weekly schedule, hence medium rather than high.

**Recommendation**

Restrict auto-merge to semver-patch only (drop minor), or further gate on a curated allowlist of trusted, widely-used packages. Do not let the workflow's own GITHUB_TOKEN count as the required human approval — configure branch protection to require a CODEOWNER review that a bot cannot satisfy, or use `dependabot` review-required rules. Add a cooldown (do not auto-merge releases < N days old) to dodge fresh-takeover windows.

---

<a id="sec-008"></a>

## SEC-008 — Scraper dependencies are not hash-pinned and have no lockfile (DEP-009 standard not applied)

| | |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Category** | supply-chain / dependency integrity |
| **Dimension** | deps-supplychain |
| **Location** | `scraper/pyproject.toml:6-16; .github/workflows/scraper-ci.yml:27-31` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: medium) |
| **First seen** | 2026-06-07 |

**Description**

Every other Python component in the repo (backend, CMS Connector agent, Solver agent) enforces the project's own DEP-009 control: a pip-compiled `requirements.lock` with `--generate-hashes` installed via `pip install --require-hashes`. The scraper does NOT. It pins exact versions in pyproject.toml but has no lockfile and is installed in CI with `pip install -e ".[dev]"` — no `--require-hashes`. Exact version pins alone do NOT protect against a poisoned/re-published PyPI artifact: pip will install whatever bytes the index serves for that version. The scraper pulls supabase==2.29.0 (which transitively drags in ~30 packages incl. pyiceberg, mmh3, zstandard, pyroaring) and playwright==1.50.0 (which downloads browser binaries at install time), so its supply-chain surface is large and entirely unverified.

**Attack scenario**

An attacker compromises a maintainer account for one of the scraper's transitive deps (e.g. a small package like loguru, rapidfuzz, or any of the supabase transitive chain) and re-publishes a malicious build at the already-pinned version, or registers a previously-yanked version. Because scraper-ci.yml installs without --require-hashes, CI (and any developer running the scraper, which holds the Supabase SERVICE_ROLE key) executes the attacker's code. The backend's hash-pinning would have blocked this exact artifact; the scraper would not.

**Evidence**

```text
- name: Install scraper + dev deps
        working-directory: scraper
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
```

**Adversarial verification**

Every factual claim checks out against the cited code. scraper/pyproject.toml:6-16 pins exact versions (playwright==1.50.0, supabase==2.29.0, etc.) with NO --hash entries, and globbing scraper/**/requirements*.lock and scraper/**/requirements*.txt returns nothing — there is no lockfile. .github/workflows/scraper-ci.yml:27-31 installs with `pip install -e ".[dev]"` and no --require-hashes. This is a genuine deviation from an established repo standard: DEP-009 is a documented control (docs/superpowers/specs/2026-05-07-security-audit.md:527) and is actually enforced everywhere else — backend/requirements.lock (1568 lines, header shows `pip-compile --generate-hashes`), agents/CMS Connector - Website/requirements.lock, and agents/Solver - Issues/requirements.lock all exist, and ci.yml:128-132/163, e2e.yml:87-89, and solver-agent.yml:40 all run `pip install --require-hashes -r requirements.lock` with an explicit "CI-004 / DEP-009" comment. The scraper is the sole Python component that skipped the control. Blast radius is real: the scraper holds the Supabase SERVICE_ROLE key (scraper/config.py:11, cli.py:252/264, supabase_sink.py:18; README.md:30 states it "bypass[es] RLS"), and the installed .venv confirms the large unverified transitive surface the finding names (pyiceberg, mmh3, zstandard, pyroaring all physically present). I did not find any guard or alternate install path that neutralizes this — the dev README install (scraper/README.md) also uses `pip install -e ".[dev]"`. Severity stays medium, consistent with the repo's own rating of DEP-009 as Medium: the SERVICE_ROLE blast radius rules out 'low', but the trigger is a speculative upstream-supplier compromise rather than anything an external CMS user can drive, which rules out 'high'.

**Exploitability:** Not directly triggerable by any user of the CMS. The threat actor is a third-party PyPI supplier: someone who compromises a maintainer account in the scraper's dependency tree (top-level loguru/rapidfuzz/supabase, or any of the ~30 unpinned transitive deps such as pyiceberg/mmh3/zstandard/yarl) and ships malicious bytes for a version the scraper will resolve. Because there is no lockfile, transitive versions float freely, and because CI/dev install without --require-hashes, the malicious artifact is accepted silently. Whoever then runs the scraper — Scraper CI (push/PR on scraper/**) or a developer running it locally with credentials loaded — executes the attacker code in a process that carries SUPABASE_SERVICE_KEY, granting full RLS-bypassing read/write to the production Supabase database (leads, projects, content, etc.). The backend/agents would have rejected the same poisoned artifact via --require-hashes; the scraper would not. This is a latent, conditional supply-chain hardening gap (no evidence any current pinned version is malicious), not an actively exploitable hole, which is why it sits at medium rather than high.

**Recommendation**

Generate a hash-pinned lockfile for the scraper (`pip-compile --generate-hashes` against pyproject.toml deps) and change scraper-ci.yml to `pip install --require-hashes -r requirements.lock` followed by `pip install -e . --no-deps`, matching the DEP-009 pattern used for backend and the agents.

---

<a id="sec-009"></a>

## SEC-009 — Unauthenticated HTML/email injection in multi-tenant form submissions (stored XSS in owner inbox)

| | |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Category** | XSS / HTML injection |
| **Dimension** | public-tokens |
| **Location** | `backend/auth_service/routers/forms.py:23-41, 169-212` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: medium) |
| **First seen** | 2026-06-07 |

**Description**

The public, unauthenticated form endpoint /forms/{project_slug}/{form_key} builds the notification email by interpolating attacker-controlled field names AND values directly into an HTML string with NO escaping. `fields = {k: str(v) ...}` is taken verbatim from the JSON body, then `_build_email_html` does `f"...{key}...{value}..."` inside `<td>` cells. `form_key` (a path segment) is likewise injected as `<span style="font-family:monospace">{form_key}</span>`. The booking email path (services/booking_email.py:116-118) deliberately calls `html.escape(...)` on every interpolated value, so this is a clear inconsistency: forms emails are unescaped. Any `<img onerror>`, `<a>`, `<script>` (in clients that render it), tracking pixel, or spoofed content is delivered into the project owner's mailbox.

**Attack scenario**

Attacker finds an allowed origin (or the form is widely embedded) and POSTs `{"name":"<img src=x onerror=...>","email":"a@b.co","<b>Injected</b>":"<a href='https://evil'>Click</a>"}`. The owner opens the New-submission email; the injected markup renders, enabling phishing links that appear to come from the CMS, content spoofing, hidden tracking pixels, or—in HTML email clients with weaker sanitisation—script execution against the owner. Field NAMES are also injected, so the attacker controls both columns of the table.

**Evidence**

```text
rows = "".join(
        f"""
        <tr>
          <td ...>{key}</td>
          <td ...>{value}</td>
        </tr>
        """
        for key, value in fields.items()
    )
... fields = {k: str(v) for k, v in body.items() if isinstance(k, str) and not k.startswith("_") and v is not None}
```

**Adversarial verification**

Code confirms the vulnerability. In backend/auth_service/routers/forms.py, submit_form builds `fields = {k: str(v) ...}` directly from the JSON body (lines 169-173) with no escaping, then _build_email_html (lines 23-41) interpolates both `{key}` and `{value}` raw into `<td>` cells, and `{form_key}` (the attacker-controlled URL path segment) plus `{project_name}` raw into the HTML (lines 59-61). The result is sent verbatim via Resend to the owner's destination_email (lines 207-223). The cited inconsistency is real and is the project's own established baseline: booking_email.py:116-118 calls html.escape() on every value, and test_booking_email.py:24 explicitly asserts `Jane <b>Doe</b>` -> `Jane <b>Doe</b>`. No global sanitizer wraps the resend html, and there is no test covering escaping on the multi-tenant forms path. So the finding's core claim (unescaped attacker-controlled HTML reaching the owner's inbox) is accurate. I downgrade severity from high to medium for two reasons the finding glosses over: (1) Trigger is gated by the origin allow-list check (lines 119-129, fail-closed when empty) — though this is weak, since allowed_origins are public website domains and the Origin header is trivially spoofable by any non-browser client (curl), so it does not actually authenticate the caller; and (2) the worst case ('stored XSS'/script execution) depends on a weakly-sanitizing HTML email client — mainstream clients (Gmail/Outlook) strip script/onerror, so the reliable, realistic impact is HTML/content injection (phishing links, spoofed rows, tracking pixels) into a single owner mailbox rather than guaranteed code execution.

**Exploitability:** Who: any unauthenticated attacker who knows one of a project's allowed_origins (these are the public domains embedding the form, not secret) can pass the origin check by setting the Origin header via curl/script — CORS only constrains browsers, not server-to-server callers. Additionally, any ordinary visitor to a legitimately embedded form can inject via a field value from a real browser. What they get: POST /forms/{project_slug}/{form_key} with a JSON body like {"name":"<img src=x onerror=...>","email":"a@b.co","<b>Injected</b>":"<a href='https://evil'>Click</a>"} delivers attacker-controlled markup, unescaped, into the project owner's notification email. Because both the field NAME (key) and VALUE are interpolated, the attacker controls both table columns, plus form_key in the header. Concrete impact: convincing phishing links that appear to originate from the CMS, content/row spoofing, hidden tracking pixels (read receipts / IP disclosure), and — only in email clients with weak sanitization — active content. Rate limit is 5/10min per (project,form,IP), bounding volume but not the injection. Fix: html.escape() key, value, form_key, and project_name before interpolation, mirroring booking_email.py.

**Recommendation**

Escape every interpolated value with html.escape() (escape both key and value, and form_key/project_name) before building the HTML, exactly as booking_email.py does. Better: render through a templating engine with autoescaping (Jinja2) or build the DOM with an escaping helper. Also cap field count/length to bound abuse.

---

<a id="sec-010"></a>

## SEC-010 — In-memory rate limiter resets per serverless invocation and is not shared across instances on Vercel, neutering every slowapi limit (login, forms, booking, admin bearer)

| | |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Category** | Rate limiting / DoS |
| **Dimension** | ratelimit-dos |
| **Location** | `backend/auth_service/core/limiter.py:21; backend/auth_service/core/bearer_limiter.py:1-14,56; backend/auth_service/main.py:42,157` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: medium) |
| **First seen** | 2026-06-07 |

**Description**

The whole platform relies on slowapi's default storage backend (in-process memory) — `limiter = Limiter(key_func=client_ip)` is created with no `storage_uri`, and a grep across the backend shows no Redis/Memcached/storage_uri configuration anywhere. The custom `bearer_limiter.Bucket` is likewise a module-level Python object. On Vercel @vercel/python, each cold start gets a fresh process (counters reset to zero), and concurrent requests are load-balanced across MANY simultaneous instances, each with its own independent counter. The code itself concedes this: bearer_limiter.py's docstring says 'The bucket is process-local; on Vercel each serverless instance gets its own counter', and tests_integration/test_rate_limits.py:1-10 says 'The deployed slowapi limiter resets on cold-start'. Net effect: the advertised limits (30/min login, 5/10min forms, 5/hour booking create, 10/min admin bearer) are effectively per-instance-per-cold-window, so real-world enforced throughput is far higher than the stated cap and resets continuously. The 'cuts attack throughput by ~6 orders of magnitude' claim in bearer_limiter.py holds for a single instance but not when a load balancer spreads attempts across N warm instances. This degrades every downstream rate-limit finding (login brute force, form/booking email-bomb).

**Attack scenario**

An attacker scripts password-spray against POST /auth/login. Because the limiter is per-instance and resets on cold start, sustained concurrent requests fan out across multiple Vercel instances, each allowing 30/min independently, and counters vanish whenever an instance is recycled — so the effective brute-force ceiling is many multiples of the intended 30/min/IP and self-heals constantly. The same applies to flooding POST /forms/{slug}/{key} and POST /booking/{slug} to drive Resend email volume.

**Evidence**

```text
limiter = Limiter(key_func=client_ip)
```

**Adversarial verification**

The finding is accurate as written. Verified directly: (1) limiter.py:21 instantiates `Limiter(key_func=client_ip)` with NO storage_uri, so slowapi falls back to its default in-process MemoryStorage. (2) A grep across all of backend/ for `storage_uri|redis|Redis|memcached|MovingWindow|FixedWindow` returns ZERO matches — there is no shared/persistent counter store anywhere. (3) bearer_limiter.py:23-56 defines a module-level singleton `_BEARER_BUCKET = Bucket(...)` whose state lives in process memory, and its own docstring (lines 7-10) concedes "The bucket is process-local; on Vercel each serverless instance gets its own counter." (4) vercel.json:3 confirms the `@vercel/python` serverless build model — each cold start is a fresh process (counters = 0) and concurrent load fans out across independent instances, each with its own counter. (5) The limits are genuinely wired to the claimed paths: auth.py:62 (30/min login), forms.py:91/255 (5/10min), booking.py:372/852 (5/hour), deps.py:53 -> check_bearer_attempt (10/min bearer). (6) tests_integration/test_rate_limits.py:5-6 states "The deployed slowapi limiter resets on cold-start," and lines 18-35 disclose an ADDITIONAL deployed-only defect the reviewer did not mention: Vercel rewrites X-Forwarded-For at the edge, so client_ip()'s leftmost-entry resolver lands on the wrong IP in prod — the team marked these integration tests skip/un-runnable against the live backend. So the in-memory + per-instance + cold-start reset behavior is real and acknowledged in-tree. I downgrade high->medium because the limits are NOT fully neutered: within any warm instance they still apply, a low-traffic CMS spins up a bounded (not unbounded) instance count, and the bearer path guards a 192-bit secret where even N x 10/min is cryptographically negligible — so the practical impact is bounded login brute-force amplification and forms/booking email-flood (Resend cost/abuse), an availability/abuse-cost issue rather than an authZ or data-exposure compromise.

**Exploitability:** Any unauthenticated internet attacker can exploit this. They script concurrent POSTs to /auth/login (password spray), POST /forms/{slug}/{key}, or POST /booking/{slug}. Because counters are per-process and reset on every cold start, sustained concurrent traffic load-balanced across multiple Vercel instances yields an effective ceiling of roughly N x (stated limit) where N = number of warm instances, and the floor continuously self-heals as instances recycle. Concretely: many multiples of 30/min for login brute-force, and amplified 5/10min form / 5-per-hour booking submissions that drive Resend email volume (cost + recipient spam). The deployed XFF-rewrite bug (test_rate_limits.py:18-35) compounds this on prod: the resolved client_ip can collapse to a shared upstream IP, further distorting bucketing. What the attacker gains is amplified brute-force attempts and email-bomb/cost-abuse throughput, not direct data access. The admin Bearer path is effectively unaffected in practice because it protects a 192-bit machine-issued secret that is not brute-forceable even at the amplified rate. Fix per the recommendation: back slowapi and the bearer bucket with a shared store (Upstash Redis storage_uri, or an atomic per-(key,window) Postgres upsert) and separately fix client_ip() to read the correct XFF position for the Vercel edge.

**Recommendation**

Back slowapi (and the bearer bucket) with a shared, persistent store reachable from all serverless instances — e.g. `Limiter(key_func=client_ip, storage_uri="redis://...")` (Upstash Redis works well on Vercel), or move counting into Postgres/Supabase (atomic upsert of a per-(key,window) counter). Without shared state, no in-memory limiter is meaningful in this deployment model.

---

<a id="sec-011"></a>

## SEC-011 — No per-account lockout or throttle on /auth/login (only forgeable per-IP limit)

| | |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Category** | Rate limiting / DoS |
| **Dimension** | ratelimit-dos |
| **Location** | `backend/auth_service/routers/auth.py:54-77; backend/auth_service/services/auth_service.py (no lockout logic)` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: medium) |
| **First seen** | 2026-06-07 |

**Description**

Login defends only with `@limiter.limit("30/minute")` keyed on the spoofable client_ip (see XFF and serverless findings). There is no per-account failed-attempt counter or temporary lockout: a grep for lockout/failed_attempt/account_lock in auth_service.py returns nothing. The 30/min cap was deliberately raised from 10 to tolerate typos (comment lines 55-61), further widening the brute-force window. Because the only throttle is keyed on attacker-controlled IP and is in-memory/per-instance, a targeted credential-stuffing or password-spray attack against a single high-value account (e.g. an admin) has no account-side brake at all.

**Attack scenario**

Attacker targets a known admin email and sprays common passwords, rotating X-Forwarded-For per request so the per-IP limit never fires. Since there is no per-account attempt counter, the only ceiling is raw HTTP throughput across Vercel instances. Note: Supabase advisor also reports 'Auth leaked-password protection disabled', compounding weak-password exposure.

**Evidence**

```text
@limiter.limit("30/minute")
async def login(body: LoginRequest, request: Request, response: Response):
    user = await authenticate_user(body.email, body.password)
```

**Adversarial verification**

All factual claims verified by reading the code. (1) Login is protected ONLY by `@limiter.limit("30/minute")` (backend/auth_service/routers/auth.py:62), keyed via `client_ip` which unconditionally trusts the leftmost `X-Forwarded-For` header (backend/auth_service/core/limiter.py:14-18) — fully attacker-controlled, so the per-IP cap is forgeable by rotating XFF per request. (2) No per-account lockout exists: a grep for lockout/failed_attempt/account_lock across backend/ returns zero matches; `authenticate_user` (backend/auth_service/services/auth_service.py:32-52) only runs an argon2 verify and returns None on mismatch, with no failed-attempt counter or temporary lock. (3) The cap was deliberately raised from 10 to 30/min (comment auth.py:55-61), widening the window. (4) The slowapi `Limiter(key_func=client_ip)` has NO `storage_uri` so it defaults to in-memory, and the app deploys via `@vercel/python` (backend/vercel.json:3) = serverless/multi-instance, so the bucket is ephemeral and not shared across instances — confirming the per-instance limitation. This is a genuine CWE-307 gap (Improper Restriction of Excessive Authentication Attempts). I did NOT elevate to high because of a real mitigation the finding underweights: argon2 is configured with OWASP-grade cost (time_cost=3, memory_cost=64MB, parallelism=4 — auth_service.py:6-10), making each verify ~250ms of server CPU, which is a substantial server-side brake on raw brute-force throughput even when the IP limit is bypassed. That cost slows but does not stop a slow-and-low credential-spray, and provides no account-side lockout, so the finding stands as a missing defense-in-depth control. Medium (matching the reviewer) is correct.

**Exploitability:** Pre-auth, no credentials needed. An external attacker who knows or guesses a high-value account's email (e.g. an admin) can credential-stuff/password-spray against POST /auth/login. By setting a fresh `X-Forwarded-For` value on each request, they place every attempt in a distinct rate-limit bucket, so the 30/min per-IP cap never trips. There is no per-account attempt counter or lockout, so the account itself is never frozen. The only remaining ceiling is server-side argon2 CPU cost (~250ms/verify) and Vercel HTTP throughput; on serverless this cost is distributed across instances and does not lock the account. Successful outcome = full takeover of the targeted account if any sprayed password matches (compounded by the Supabase advisor's disabled leaked-password protection). It is not an instant compromise — success depends on the victim having a weak/breached password — but the account-side brute-force brake that should make this infeasible is entirely absent.

**Recommendation**

Add a per-account (keyed on normalized email) failed-attempt counter in a shared store with exponential backoff / temporary lockout after N failures, independent of source IP. Enable Supabase leaked-password protection. Keep the IP limit as defense-in-depth but do not rely on it as the sole brute-force control.

---

<a id="sec-012"></a>

## SEC-012 — Unauthenticated booking availability endpoints have no rate limit despite expensive per-day computation and DB I/O

| | |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Category** | Rate limiting / DoS (resource exhaustion) |
| **Dimension** | ratelimit-dos |
| **Location** | `backend/auth_service/routers/booking.py:337-351 (/booking/{slug}/availability), 805-825 (/availability), 828-839 (/slots); compute path _availability_for_range:224-283 / _availability_for_day:144-175` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: medium) |
| **First seen** | 2026-06-07 |

**Description**

GET /booking/{slug}/availability, the legacy GET /availability, and GET /slots are public (no auth, no `@limiter.limit`). They take an attacker-controlled `from`/`to` date range and run availability computation. /availability and /slots-style paths loop day-by-day (`while cur <= d1`) and /availability (legacy) calls `_availability_for_day` per day, each issuing Supabase queries (load_eligible_resources, load_hours, load_exceptions, busy_guard_intervals) plus optional external calendar fetches (calendar_provider.list_busy). There is no clamp on the date range size in the slug route. An attacker can request enormous ranges (or hammer the endpoint) to amplify DB load and external calendar API calls per request — a cheap-to-send, expensive-to-serve asymmetry. The create endpoints are limited to 5/hour, but the read/compute endpoints feeding the widget are not limited at all.

**Attack scenario**

Attacker discovers a tenant public_slug (returned by the embeddable widget) and floods GET /booking/{slug}/availability?from=2000-01-01&to=2100-01-01, forcing the backend into long day-by-day loops with repeated Supabase queries and Google Calendar busy fetches per request, exhausting DB connections / function execution time and inflating Google API usage.

**Evidence**

```text
@router.get("/{slug}/availability")
def availability(
    slug: str, service_id: str, from_: str = Query(..., alias="from"), to: str = Query(...)
) -> JSONResponse:
```

**Adversarial verification**

I read the cited code and the claim holds. Three public availability/slot endpoints in backend/auth_service/routers/booking.py have NO auth and NO @limiter.limit, while the write endpoints do (create_booking line 371-372 and legacy_create line 851-852 are both @limiter.limit("5/hour")): (1) slug /{slug}/availability (337-351) -> _availability_for_range; (2) legacy GET /availability (805-825) loops `while cur <= d1` calling _availability_for_day per day; (3) GET /slots (828-839) single day. _require_tenant (61-65) only resolves the slug and raises 404 — no auth, no caching, no limit. There is NO date-range clamp: the slug route (345-350) and legacy route (814-818) only datetime.strptime the from/to and pass d0/d1 straight through; grep for any range/clamp/max_advance check found none — max_advance_days is used only inside the slot engine (available_starts at 173/277), not to reject the span. One correction to the finding's evidence: in the SLUG route, _availability_for_range (224-283) loads resources/hours/exceptions/busy and the Google list_busy ONCE for the whole range (232-254, before the loop), so its per-day loop (257-282) is pure in-memory compute — CPU-bound, not DB-amplifying. The true per-day DB+calendar amplifier is the LEGACY /availability path: _availability_for_day (144-175) re-runs load_eligible_resources, load_hours, load_exceptions, the busy-interval query, AND calendar_provider.list_busy on EVERY day of the range. google_calendar.busy_intervals (google_calendar.py:79-94) issues a freebusy/events call with maxResults 2500 and unclamped timeMin/timeMax. Also note core/limiter.py client_ip (6-18) trusts the leftmost X-Forwarded-For verbatim, so even the existing 5/hour write limits are IP-spoofable — but that is a separate weakness; here the reads have no limit at all.

**Exploitability:** Any unauthenticated remote attacker who knows a public_slug (trivially obtained — the embeddable widget calls /booking/{slug}/config and these endpoints) can trigger it. GET /booking/{slug}/availability?service_id=...&from=2000-01-01&to=2100-01-01 forces ~36,500 in-memory day computations per request (CPU/wall-time on the serverless function — slow responses, function-timeout/concurrency exhaustion). The legacy GET /availability?from=2000-01-01&to=2100-01-01 (hardcoded to slug roman-technologies-website, so single-tenant blast radius) is worse: each of ~36,500 days issues 4+ Supabase queries plus a Google freebusy call, exhausting DB connections and inflating Google Calendar API quota/cost. No body, no auth, no limit needed to send — cheap-to-send / expensive-to-serve asymmetry. Result is denial of service and third-party API cost inflation, not data exposure or authz bypass. Fix: hard-cap the queried span (reject > service.max_advance_days) and add a per-IP limit (acknowledging X-Forwarded-For is client-controlled, so the limit key should use a trusted proxy hop, not the leftmost value).

**Recommendation**

Apply a per-IP (un-spoofable) rate limit to the availability/slots endpoints and hard-cap the queried date span (reject ranges wider than e.g. service.max_advance_days). Consider short-TTL caching of availability per (tenant, service, day).

---

<a id="sec-013"></a>

## SEC-013 — slack_processed_events has RLS disabled and full anon DML grants — idempotency table is readable, writable and truncatable via PostgREST

| | |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Category** | Missing RLS / Broken Access Control |
| **Dimension** | supabase-db |
| **Location** | `backend/migrations/2026_05_15_slack_inbound_s1_5.sql:33-39; live pg_class.relrowsecurity=false + role_table_grants(anon/authenticated)=SELECT/INSERT/UPDATE/DELETE/TRUNCATE` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: medium) |
| **First seen** | 2026-06-07 |

**Description**

slack_processed_events is created with NO `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` (the migration comment says 'RLS stays off ... restrict via no public grants', but Supabase's default `GRANT ... ON ALL TABLES IN SCHEMA public TO anon, authenticated` applies, so the table inherits full anon DML). Confirmed on the live DB: as the anon role I SELECTed 98 rows, and anon/authenticated hold INSERT/UPDATE/DELETE/TRUNCATE. This table is the dedup ledger for the Slack events webhook: routers/slack_events.py returns 200 and drops any event whose event_id is `already_processed`. An attacker with the anon key can (a) read all historical Slack event_ids (internal-workflow disclosure), (b) DELETE/TRUNCATE the table to wipe replay-protection, or (c) pre-INSERT an event_id to make the webhook silently swallow that specific legitimate Slack approval/revision event. The signature check on the webhook protects inbound authenticity but does nothing to protect this side-channel table.

**Attack scenario**

Attacker with the anon key calls DELETE https://<ref>.supabase.co/rest/v1/slack_processed_events?event_id=neq.x (or TRUNCATE-equivalent bulk delete) to clear the dedup ledger, enabling replay of previously-captured signed Slack callbacks; or POSTs a row {event_id: <observed/guessed Ev id>} so the next genuine Slack callback with that id is dropped at slack_events.py:40-41, suppressing an approval or revision-feedback action.

**Evidence**

```text
CREATE TABLE IF NOT EXISTS slack_processed_events (
  event_id TEXT PRIMARY KEY,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- live: rls_enabled=false; anon grants = DELETE,INSERT,REFERENCES,SELECT,TRIGGER,TRUNCATE,UPDATE; SET ROLE anon -> SELECT count(*) = 98
```

**Adversarial verification**

Verified against both code and the live production DB (project xeluydwpgiddbamysgyu / "CMS").

1) Migration: backend/migrations/2026_05_15_slack_inbound_s1_5.sql:32-39 creates slack_processed_events with NO `ENABLE ROW LEVEL SECURITY`. The inline comment (lines 4-6) claims the table is safe "via no public grants (Supabase service-role-only by default)". That assumption is FALSE and the live DB proves it.

2) Live grants (information_schema.role_table_grants): anon AND authenticated each hold SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER on public.slack_processed_events. The Supabase default `GRANT ... TO anon, authenticated` did apply — refuting the migration's stated assumption.

3) RLS off + PostgREST-exposed: Supabase security advisor returns an ERROR-level lint `rls_disabled_in_public` for exactly this table ("Table public.slack_processed_events is public, but RLS has not been enabled"). It is the ONLY table with this ERROR; peer server-internal tables (admin_api_keys, leads, email_configs, project_services, scrape_jobs, all booking_*) have RLS ENABLED (default-deny). So this table is a genuine outlier, not the intended pattern.

4) Direct exploit proof: `SET ROLE anon; SELECT count(*) FROM public.slack_processed_events` returned 98 rows, and as anon I read live event_id values (e.g. Ev0B8SR1SCPN, received 2026-06-05). The anon role passes the RLS layer, so PostgREST WILL serve these to any anon-key holder.

5) Function impact (slack_events.py:39-43 + slack_events_dedup.py:20-43): the table is the Slack webhook replay-dedup ledger. already_processed() returns True for any present event_id, causing slack_events.py:40-41 to return 200 and silently drop the event. Therefore anon DELETE/TRUNCATE erases replay protection (enabling replay of captured signed callbacks), and anon INSERT of an observed/guessed Slack event_id pre-poisons the ledger so the next genuine signed callback for that id is swallowed — suppressing an approval (slack_handler.handle_reaction_added) or revision-feedback (handle_message) action. The HMAC signature check at slack_events.py:36 guards inbound authenticity but not this side-channel table.

Every claim in the finding (RLS=false, full anon DML grants, 98 rows, side-channel suppression/replay) is confirmed on the live system. Real and exploitable; the only mitigating nuance is the access vector (see exploitability), which keeps it at medium rather than high.

**Exploitability:** Trigger: anyone in possession of the project's Supabase anon/publishable key plus the project ref (https://xeluydwpgiddbamysgyu.supabase.co), hitting /rest/v1/slack_processed_events. The anon key is a non-secret publishable credential by Supabase design — the whole security model assumes RLS guards public-schema tables. Note (slightly narrowing real-world reach): this frontend ships NO Supabase client (confirmed: grep for NEXT_PUBLIC_SUPABASE/anon key in frontend = no matches), so the anon key is not handed to browsers here; an attacker must obtain it from another channel (backend env leak, CI logs, a client/connector repo, or any other place the publishable key appears). It is, however, only the anon key — not the service-role key — so no special privilege is required once held.

What they get, all verified live as role anon:
- READ: SELECT returns all 98 historical Slack event_ids + timestamps (internal-workflow disclosure; reveals approval/revision cadence and Slack Ev-id format).
- WIPE: DELETE/TRUNCATE clears the dedup ledger, removing replay protection so previously-captured signed Slack callbacks can be re-delivered and re-actioned (merge/email/approval side effects, which the dedup ledger exists to prevent).
- POISON: INSERT {event_id:'<observed/guessed Ev id>'} makes the next genuine signed Slack callback with that id hit already_processed()==True and be dropped at slack_events.py:40-41 — silently suppressing a specific approval or revision-feedback event.

Fix (matches finding): ALTER TABLE public.slack_processed_events ENABLE ROW LEVEL SECURITY (no policies = default-deny for anon/authenticated, service_role bypasses RLS so the dedup service keeps working), plus belt-and-suspenders REVOKE ALL ... FROM anon, authenticated. This brings the table in line with its already-protected peers.

**Recommendation**

ALTER TABLE public.slack_processed_events ENABLE ROW LEVEL SECURITY (no policies = default-deny for anon/authenticated, matching the other server-internal tables). Belt-and-suspenders: REVOKE ALL ON public.slack_processed_events FROM anon, authenticated. The migration's stated assumption ('no public grants') is false under Supabase defaults — enabling RLS is the actual fix.

---

<a id="sec-014"></a>

## SEC-014 — HTML/email-template injection: form submission field keys AND values interpolated raw (unescaped) into the email sent to the project owner

| | |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Category** | HTML injection / email-template injection |
| **Dimension** | xss-html |
| **Location** | `backend/auth_service/routers/forms.py:30-41 (also :44-87, used by both /{project_slug}/{form_key} and /contact)` |
| **Reviewer confidence** | high |
| **Verifier verdict** | confirmed (adjusted: medium) |
| **First seen** | 2026-06-07 |

**Description**

_build_email_html() interpolates every submitted form field key and value directly into the email HTML with no escaping, unlike every other email builder in the codebase (booking_email, booking_manage_email, booking_reminder_email, issue_resolved_email, project_request_email, welcome_email all call html.escape / _escape_html on caller-controlled fields per the BE-006 convention). The /{project_slug}/{form_key} endpoint is public (forms sub-app, CORS allow_origins=['*'], allow_credentials=False, no auth) and accepts an arbitrary `body: dict`; keys and values are coerced to str and dropped straight into <td>{key}</td><td>{value}</td>. The resulting HTML email is delivered to the project's configured destination_email (the business owner). The marketing /contact path reuses the same helper, where the free-form `message` (and name) are likewise unescaped.

**Attack scenario**

An attacker submits a form on a site whose origin is in allowed_origins (or whose owner whitelisted a broad origin) with a payload like {"Message":"<a href='https://evil.example/verify'>Click to confirm your order</a><img src=x onerror=...>"} or with a crafted key containing markup. The owner receives an email where the injected anchor/markup renders as legitimate content, enabling convincing phishing/content-spoofing inside an email that appears to come from their own CMS. Style/markup injection and hidden links work in virtually all HTML mail clients; <script> is stripped by most clients but other vectors (link/image/CSS, layout spoofing) are not.

**Evidence**

```text
rows = "".join(
        f"""
        <tr>
          <td style="...">{key}</td>
          <td style="...word-break:break-word">{value}</td>
        </tr>
        """
        for key, value in fields.items()
    )
```

**Adversarial verification**

Read backend/auth_service/routers/forms.py directly. The injection is real and the comparison claim holds.

(1) forms.py:30-41 — _build_email_html() builds table rows via f-string with `{key}` (line 35) and `{value}` (line 37) interpolated with NO HTML escaping. Same file also interpolates `{project_name}` (line 59), `{form_key}` (line 61), and `{submitted_at}` (line 79) raw.

(2) The only field handling is forms.py:169-173, which coerces values to str(), drops keys starting with `_`, and drops None — it does NOT escape HTML. Confirmed no `html.escape`/`_escape_html` anywhere in forms.py (the file does not even import `html`).

(3) The BE-006 convention claim is accurate. Grep confirms every other email builder escapes caller-controlled fields: services/welcome_email.py:41-44 (html.escape, with an explicit "Closes the BE-006 angle" docstring at :21), services/issue_resolved_email.py:54-59, services/project_request_email.py:74-80 (_escape_html), services/booking_manage_email.py:65-149, services/booking_reminder_email.py:29-34. forms.py is the lone outlier. The audit doc (docs/superpowers/specs/2026-05-07-security-audit.md:360) classifies the equivalent welcome-email unescaped-HTML issue as BE-006 — i.e. the team treats this exact bug class at medium grade.

(4) Exploit path is real but the origin gate (forms.py:119-129) is a partial mitigation, not a fix. It fails closed (no allowed_origins => 403) and rejects mismatched Origin headers, so a fully cross-origin attacker cannot POST arbitrary JSON. However the injection does not depend on a foreign origin: any ordinary visitor on the client's own legitimate site (an allowed origin) controls the field values they type and can submit markup that flows unescaped into the owner's inbox. The /contact path (forms.py:254-314) validates name/email/message format but `message`/`name`/`company` remain free-form and unescaped at line 296.

(5) Severity stays medium. This is stored/transactional HTML-injection into an email delivered to the business owner — enabling link/image/CSS/layout content-spoofing and phishing inside a mail that appears to come from their own CMS. It is NOT script execution: the scenario's `<img onerror=...>` JS does not run in HTML mail clients (the finding itself concedes script is stripped). No platform-side RCE, no data exfiltration, recipient already expects attacker-influenced form content. So genuine but bounded — consistent with the codebase's own BE-006 medium rating. Fix is the one-line-per-field html.escape() the recommendation describes.

**Exploitability:** Trigger: (a) /{project_slug}/{form_key} — any visitor submitting from an origin in the project's allowed_origins (i.e. the client's own public website, the normal use case) supplies arbitrary field keys/values; the origin allow-list gates the caller's Origin header but not the typed content, so a real visitor on the legit site can inject. A fully cross-origin attacker is blocked by the fail-closed origin check unless the owner whitelisted a broad origin. (b) /contact — reached via the same-origin frontend proxy (rate-limited + honeypot), free-form `message`/`name`/`company` are unescaped. What they get: the project/business owner receives an HTML email where injected `<a>`, `<img>`, and CSS render as legitimate-looking content — convincing in-email phishing / content-spoofing branded as the owner's own CMS. No JS execution (mail clients strip script and don't fire onerror), no server compromise, no data theft from the platform.

**Recommendation**

HTML-escape both key and value before interpolation, mirroring the rest of the codebase: import html and use html.escape(key) / html.escape(value) (and html.escape(submitted_at), project_name, form_key for completeness). This is a one-line-per-field change consistent with the existing BE-006 pattern already applied in every other email builder.

---
