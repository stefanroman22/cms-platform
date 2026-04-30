# Phase 5 — Testing

**Goal:** Prove the integration end-to-end before claiming success.

**Inputs:** outputs of Phase 4.

Run **all** tests below. Never claim Phase 6 success while any 5a–5g test is red.

## 5a — CMS read path

1. `GET /content/<slug>` (production endpoint, public). Expect 200 + JSON manifest.
2. `GET /content/<slug>/draft` with `Authorization: Bearer <preview_token>`. Expect 200 + JSON manifest.
3. Without `preview_token`: expect 401/403.
4. Compare service keys in the response against approved manifest. Any missing → fail.

## 5b — CMS write path (admin)

1. PUT a known test value to one service via the CMS admin API. Expect 200.
2. GET production and draft endpoints — verify the test value appears immediately on `/draft`, on `/content/<slug>` only after publish.
3. Revert the test value.

## 5c — Vercel preview deploy

1. Fetch `preview_url` from the CMS project row.
2. HTTP GET the preview URL. Expect 200.
3. Verify the rendered page contains a known string sourced from the CMS draft (use a known seeded `initial_content` string, or the test value from 5b before revert).

## 5d — Production deploy

1. Same as 5c but against `production_url`. The production deploy should reflect *published* content only.

## 5e — Contact form (only if `email_config` exists)

1. POST a test submission with `subject: "[CMS-CONNECTOR-TEST]"`.
2. Confirm a 200 response.
3. Manually verify the destination inbox (or Resend dashboard event log) received the email.
4. Confirm the email arrived from the configured `RESEND_FROM_EMAIL`.

## 5f — Auth & cookie behavior

1. Login flow returns the `sid` cookie with `HttpOnly`, `Secure`, `SameSite=Strict`.
2. Logout invalidates the session.

## 5g — Smoke checklist (printed for user sign-off)

- [ ] Preview URL renders the expected layout
- [ ] All sections from the report are editable from the CMS dashboard
- [ ] Form submission test email received
- [ ] Production URL is live and serves published content
- [ ] No console errors in browser dev tools on either deploy

## Failure handling

For each failed test:
- Print test name + expected vs actual + remediation hint.
- Attempt fix.
- Re-run only the failed test (not the entire matrix).
- After fix succeeds, append to `LEARNINGS.md` under `## Phase 5 — Testing rules`. Example:
  - `- 2026-06-10: Smoke test must hit projectSlug-specific path, not bare host. Triggered by: smoke test green against root domain even though /<slug> 404'd.`

## Token tactics

- Run all 5a–5f tests; print one PASS/FAIL line per test.
- On failure: dump expected/actual + curl command for the user to reproduce. Don't dump entire HTTP body unless < 1KB.
- Don't re-fetch the manifest between tests if cached in process memory.

## Model policy

Test-failure root-cause analysis is the highest-stakes reasoning task in the
pipeline — a misdiagnosis here ships a broken integration. Use
**`claude-opus-4-7`** for any LLM-assisted failure analysis (e.g. interpreting
a 5xx response body, correlating a console error with a CMS service mis-wire).
Never downgrade to a smaller model in this phase.
