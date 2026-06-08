# Phase 5 — Testing

**Orchestration:** per the skill's *Orchestration policy (ultracode)*, fan out root-cause analysis via the Workflow tool across failing test dimensions when multiple tests red or a failure is multi-layered; be exhaustive.

**Goal:** Prove the integration end-to-end before claiming success.

**Inputs:** outputs of Phase 4.

Run **all** tests below. Never claim Phase 6 success while any 5a–5h test is red.

## 5a — CMS read path

1. `GET /content/<slug>` (production endpoint, public). Expect 200 + JSON manifest. Assert back-compat for single-locale and multilingual sites alike.
2. `GET /content/<slug>/draft` with header `X-CMS-Preview-Token: <preview_token>`. Expect 200 + JSON manifest.
3. Without `X-CMS-Preview-Token` header: expect 401/403.
4. Compare service keys in the response against approved manifest. Any missing → fail.

**Per-locale loop (multilingual sites only):** for each locale in `manifest.locales`:
- `GET /content/<slug>/<locale>` → expect 200; assert the response contains locale-specific content for that locale.
- `GET /content/<slug>/<locale>/draft` with header `X-CMS-Preview-Token: <preview_token>` → expect 200.

**Negative locale test:** `GET /content/<slug>/<unconfigured-locale>` (e.g. `/content/<slug>/xx`) → expect 404.

**Legacy back-compat:** `GET /content/<slug>` (no locale path segment) → 200, returns default-locale content.

## 5b — CMS write path (admin)

1. PUT a known test value to one service via the CMS admin API. Expect 200.
2. GET production and draft endpoints — verify the test value appears immediately on `/draft`, on `/content/<slug>` only after publish.
3. Revert the test value.

## 5c — Vercel preview deploy

1. Fetch `preview_url` from the CMS project row.
2. HTTP GET the preview URL. Expect 200.
3. Verify the rendered page contains a known string sourced from the CMS draft (use a known seeded `initial_content` string, or the test value from 5b before revert).
4. **Multilingual sites** (manifest has `locales` with >1 entry): for each locale, fetch `<preview_url>/<locale>` (e.g. `/en`, `/nl` per `localePrefix:"always"`) and assert the response contains the locale-specific content string. Skip this step for single-locale sites — just use the bare `preview_url`.

## 5d — Production deploy

1. Same as 5c but against `production_url`. The production deploy should reflect *published* content only.
2. **Multilingual sites:** fetch each locale's deployed route (`<production_url>/<locale>`) and assert each renders its own locale's content. Single-locale sites: check the bare `production_url` only.

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

## 5h — Booking smoke matrix (only if booking was provisioned in Phase 4)

All requests below target the provisioned `{slug}`. The e2e email short-circuit must be active so no real mail is delivered during this suite.

**Run these steps in order:**

1. **Services list**
   `GET /booking/{slug}/services` → expect 200 + non-empty array. Capture `service_id` from the first result.

2. **Availability**
   `GET /booking/{slug}/availability?service_id={service_id}&from={today_utc}&to={7_days_utc}` → expect 200 + at least one available slot. Capture a `start_utc` value.

3. **Booking submission — three cases**

   a. **Valid booking:** `POST /booking/{slug}` with `service_id`, `start_utc`, name, email. Expect 200 + `booking_id` + `manage_url`.

   b. **Honeypot rejection:** same POST with `website` field non-empty. Expect a fake-success 200 response but **no row created** in the database. (No real booking stored.)

   c. **Double-book:** `POST /booking/{slug}` again with the same `start_utc` captured in step 2. Expect **409 Conflict**.

4. **Manage page**
   `GET /booking/manage/{token}` (token from `manage_url` in step 3a) → expect 200.

5. **Reschedule**
   `POST /booking/manage/{token}/reschedule` with body `{slot_start: <new_start_utc>}` → expect 200. Note: the token rotates on success; capture the new token from the response for step 6.

6. **Cancel**
   `POST /booking/manage/{new_token}/cancel` → expect 200.

7. **Email preview — assert no "Stefan" leaks**
   `POST /projects/{slug}/bookings/email-preview` for each template: `confirmation`, `reschedule`, `cancellation`, `reminder`. Send a `draft` body populated from the provisioned settings, e.g.:
   ```json
   {
     "case": "confirmation",
     "draft": {
       "business_name": "<provisioned business_name>",
       "accent_color": "<provisioned accent_color>",
       "destination_email": "<provisioned destination_email>"
     }
   }
   ```
   (An empty or omitted `draft` falls back to `"Your business"` / `#18181b`, which will fail the business-name assertion.) For each:
   - Expect 200 + HTML body.
   - Assert the rendered output contains the `business_name` from the `draft`.
   - Assert the rendered output contains the `accent_color` from the `draft`.
   - Assert the rendered output does **not** contain the string `"Stefan"` in any visible text. Fail loudly if it does — this would mean the default fallback email leaked into a client's template.

8. **Reminder cron**
   `POST /booking/cron/reminders` with header `X-Cron-Secret: {cron_secret}` → expect 200.

9. **Client build / render**
   Run the client repo's build command. Expect 0 errors. Confirm the booking UI component that was wired to `lib/booking.ts` compiles without type errors and renders without console errors.

> Any red result in 5h blocks Phase 6 "done". Print one PASS/FAIL line per step; on failure include the curl command for manual reproduction.

## Failure handling

For each failed test:
- Print test name + expected vs actual + remediation hint.
- Attempt fix.
- Re-run only the failed test (not the entire matrix).
- After fix succeeds, append to `LEARNINGS.md` under `## Phase 5 — Testing rules`. Example:
  - `- 2026-06-10: Smoke test must hit projectSlug-specific path, not bare host. Triggered by: smoke test green against root domain even though /<slug> 404'd.`

## Token tactics

- Run all 5a–5h tests; print one PASS/FAIL line per test.
- On failure: dump expected/actual + curl command for the user to reproduce. Don't dump entire HTTP body unless < 1KB.
- Don't re-fetch the manifest between tests if cached in process memory.

## Model policy

Test-failure root-cause analysis is the highest-stakes reasoning task in the
pipeline — a misdiagnosis here ships a broken integration. Use
**`claude-opus-4-8`** with effort `xhigh` for any LLM-assisted failure analysis (e.g. interpreting
a 5xx response body, correlating a console error with a CMS service mis-wire).
Never downgrade to a smaller model in this phase.
