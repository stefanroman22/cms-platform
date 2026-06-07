# CMS Connector × Booking Auto-Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the CMS Connector agent to detect a client site's booking/scheduling experience, provision the headless booking backend for that project (branded, with the right destination email), wire the client's own bespoke booking UI to the booking API, smoke-test it, and learn from feedback — plus two shared booking-module fixes so per-client colors and company name genuinely hold.

**Architecture:** Booking is a headless backend (tenant = project, addressed by `public_slug`). The connector provisions via the admin API (`enable` → settings/services/resources/hours), generates a typed client `lib/booking.ts` in the client repo, and wires the design's booking UI to it. Two shared fixes land first: de-hardcode "Stefan" in emails/calendar titles, and make the booking widget consume the per-tenant accent color. Spec: [docs/superpowers/specs/2026-06-06-connector-booking-integration-design.md](../specs/2026-06-06-connector-booking-integration-design.md).

**Tech Stack:** Python 3.13 · FastAPI · supabase-py · Resend · Next.js 16 / React / Tailwind v4 · pytest (backend `auth_service/tests/`, connector `agents/CMS Connector - Website/tests/`) · vitest (frontend).

---

## Conventions

- All work is in the MAIN working tree on `feat/lead-scraper-system`. Per Stefan's standing rule, **commits go in one batch by Stefan** — the `git commit` steps below stage only this task's files (leaving the rest of the working tree alone); run them only on Stefan's go (the booking module + multilang work are already uncommitted there).
- Test commands:
  - Backend: `cd backend && venv/Scripts/python -m pytest auth_service/tests/<file> -q`
  - Connector: `cd "agents/CMS Connector - Website" && ../../backend/venv/Scripts/python -m pytest tests/ -q`
  - Frontend: `cd frontend && npm test -- <pattern>`
- TDD: failing test → see it fail → minimal implementation → see it pass.

## File structure

**Part A — shared booking-module fixes:**
- Modify `backend/auth_service/services/booking_i18n.py` (neutral, host-name-free strings)
- Modify `backend/auth_service/services/booking_email.py`, `booking_manage_email.py`, `booking_reminder_email.py` (calendar titles + reminder text)
- Modify `frontend/src/components/booking/BookingCalendar.tsx` (consume per-tenant accent via `--color-accent`)
- Test `frontend/src/components/booking/__tests__/BookingCalendar.test.tsx` (new)

**Part B — connector extension (`agents/CMS Connector - Website/`):**
- Modify `prompts.py` (detection + `booking` manifest block + wiring guidance)
- Modify `scan.py` (booking provisioning + `lib/booking.ts` generation + env)
- Modify `output_writer.py` (booking config in `cms.config.json`)
- Modify `phases/2-scan.md`, `phases/4-integration.md`, `phases/5-testing.md`
- Modify `AGENTS.md`, `LEARNINGS.md`, `SKILL.md`
- Tests under `agents/CMS Connector - Website/tests/`

---

# PART A — Booking module fixes (land first)

## Task A1: De-hardcode "Stefan" in booking emails

**Files:**
- Modify: `backend/auth_service/services/booking_i18n.py`
- Modify: `backend/auth_service/services/booking_email.py` (calendar title ~line 110)
- Modify: `backend/auth_service/services/booking_manage_email.py` (calendar title ~line 87)
- Modify: `backend/auth_service/services/booking_reminder_email.py` (render_text ~line 70)
- Test: `backend/auth_service/tests/test_booking_email.py` (extend) and `test_booking_manage_email.py` / `test_booking_reminder_email.py` if present

- [ ] **Step 1: Write/extend the failing test**

Add to `backend/auth_service/tests/test_booking_email.py` (read the file first to match its fixtures/imports for `render_visitor_html` / the email render functions and the `Brand`/`TenantConfig` they take):

```python
from auth_service.services import booking_i18n


def test_no_hardcoded_host_name_in_strings():
    blob = "\n".join(booking_i18n.STRINGS["en"].values())
    assert "Stefan" not in blob


def test_visitor_confirmation_uses_company_not_person(monkeypatch):
    # render the visitor confirmation HTML for a generic tenant and assert it
    # carries the business name and no hardcoded person name.
    from auth_service.services import booking_email
    from auth_service.services.email_layout import Brand

    brand = Brand(business_name="Acme Salon", logo_url="", accent="#aa0000",
                  canonical_url="https://acme.example")
    html = booking_email.render_visitor_html(
        brand=brand, locale="en", copy={},
        name="Jane", when_label="Mon 10:00", note="", manage_url="", meeting_url="",
        google_calendar_url="",
    )
    assert "Acme Salon" in html
    assert "Stefan" not in html
```
(Adapt the `render_visitor_html(...)` call to the function's REAL signature — read `booking_email.py` first; the assertions, not the arg list, are the contract.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_booking_email.py -q`
Expected: FAIL — `"Stefan"` present in STRINGS / rendered HTML.

- [ ] **Step 3: Rewrite the strings in `booking_i18n.py`**

Replace the host-name-bearing / call-specific values in `STRINGS["en"]` with host-name-neutral, booking-generic copy (keep keys + `{placeholders}` identical so callers are unchanged):

```python
        "confirm_subject": "Your booking is confirmed",
        "reminder_subject": "Reminder: your upcoming appointment",
        "cancel_subject": "Your booking has been cancelled",
        "reschedule_subject": "Your booking has been rescheduled",
        ...
        "confirmed_subtext": "Your booking is confirmed.",
        "reminder_heading": "Your appointment is in about an hour, {name}.",
        "cancel_client_heading": "Your booking has been cancelled, {name}.",
        "reschedule_client_heading": "Your booking has been moved, {name}.",
        "host_new_heading": "New booking",
        "join_cta": "Join the meeting",
        "email_you_link": "We'll email you the meeting link before your appointment.",
```
(Leave `host_new_subject`, `host_cancel_subject`, `host_reschedule_subject` — they use `{name}`, no "Stefan". Leave `manage_cta`, `add_cal_cta`, `manage_prompt`, headers as-is. The point is: zero "Stefan", generic "booking/appointment" wording. The company name comes from the email header/footer Brand, and the connector may further set per-tenant `email_copy`.)

- [ ] **Step 4: Fix the calendar-event titles + reminder text**

In `booking_email.py` (~line 110) and `booking_manage_email.py` (~line 87), replace:
```python
title=f"Call with Stefan @ {_brand.business_name}"
```
with (read the surrounding function first — if a `service_name` is in scope, prefer it; otherwise use the generic form):
```python
title=f"Booking @ {_brand.business_name}"   # or f"{service_name} @ {_brand.business_name}" if service_name is in scope
```
In `booking_reminder_email.py` (~line 70) replace `"Reminder — your call with Stefan is in about an hour.\n..."` with `"Reminder — your appointment is in about an hour.\n..."` (keep the rest of the f-string identical).

- [ ] **Step 5: Run the booking email tests**

Run: `cd backend && venv/Scripts/python -m pytest auth_service/tests/test_booking_email.py auth_service/tests/test_booking_manage_email.py auth_service/tests/test_booking_reminder_email.py -q`
Expected: PASS. (Update any pre-existing assertion that pinned the OLD "...with Stefan..." subject text to the new neutral text — those are the only expected breakages; the live tenants are functionally unaffected.)

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/services/booking_i18n.py backend/auth_service/services/booking_email.py backend/auth_service/services/booking_manage_email.py backend/auth_service/services/booking_reminder_email.py backend/auth_service/tests/test_booking_email.py
git commit -m "fix(booking): de-hardcode host name in emails + calendar titles"
```

---

## Task A2: Booking widget consumes per-tenant accent color

**Files:**
- Modify: `frontend/src/components/booking/BookingCalendar.tsx` (the wrapper `style` object, ~lines 276-279)
- Test: `frontend/src/components/booking/__tests__/BookingCalendar.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/booking/__tests__/BookingCalendar.test.tsx` (mirror the dashboard vitest pattern: `vi.fn()` on `global.fetch`, `waitFor`):

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { BookingCalendar } from "../BookingCalendar";

beforeEach(() => {
  global.fetch = vi.fn((url: string | URL | Request) => {
    const u = typeof url === "string" ? url : url.toString();
    if (u.includes("/config")) {
      return Promise.resolve({ ok: true, json: async () => ({
        public_slug: "acme", business_name: "Acme", logo_url: null,
        primary_color: "#123456", accent_color: "#abcdef", locale: "en" }) });
    }
    if (u.includes("/services")) {
      return Promise.resolve({ ok: true, json: async () => ({ services: [] }) });
    }
    return Promise.resolve({ ok: true, json: async () => ({ days: [] }) });
  }) as unknown as typeof fetch;
});
afterEach(() => vi.restoreAllMocks());

describe("BookingCalendar theming", () => {
  it("applies the tenant accent color to the widget's --color-accent", async () => {
    const { container } = render(<BookingCalendar slug="acme" />);
    await waitFor(() => {
      const root = container.querySelector("[data-booking-root]") as HTMLElement;
      expect(root).toBeTruthy();
      // tenant accent must drive the accent utilities, i.e. override --color-accent
      expect(root.style.getPropertyValue("--color-accent")).toBe("#abcdef");
    });
  });
});
```
(If the widget root has no stable selector, add `data-booking-root` to the wrapping element in Step 3.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm test -- BookingCalendar`
Expected: FAIL — `--color-accent` not set (today the widget only sets the unused `--booking-accent`).

- [ ] **Step 3: Make the widget consume the tenant accent**

Read `BookingCalendar.tsx` around lines 270-280. The widget already computes `accentColor`/`primaryColor` from config and sets the (unused) `--booking-primary`/`--booking-accent` CSS vars on the wrapper style. The widget's actual accent utilities (`text-accent`, `border-accent`, etc.) resolve to the global Tailwind token `--color-accent`. So additionally override `--color-accent` (and a primary token if one exists) ON THE WIDGET ROOT, scoped, with a fallback to the global when unset. Update the style object:

```tsx
  const wrapperStyle: React.CSSProperties = {
    ...(primaryColor ? { "--booking-primary": primaryColor } : {}),
    ...(accentColor ? { "--booking-accent": accentColor } : {}),
    // Drive the widget's accent utilities (text-accent/border-accent/...) from the
    // tenant color; falls back to the app-global --color-accent when unset.
    ...(accentColor ? { "--color-accent": accentColor } : {}),
  } as React.CSSProperties;
```
Ensure the wrapper element uses `style={wrapperStyle}` and add `data-booking-root` to it (for the test + future styling). Do NOT change the utility class names — overriding the CSS var they consume is the whole fix. (Roman's own usage passes no accent_color override → `--color-accent` not set → unchanged.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npm test -- BookingCalendar`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/booking/BookingCalendar.tsx frontend/src/components/booking/__tests__/BookingCalendar.test.tsx
git commit -m "fix(booking): widget consumes per-tenant accent color (--color-accent)"
```

---

# PART B — Connector extension

## Task B1: Booking detection + manifest block (prompts.py)

**Files:**
- Modify: `agents/CMS Connector - Website/prompts.py`
- Test: `agents/CMS Connector - Website/tests/test_prompts_booking.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# agents/CMS Connector - Website/tests/test_prompts_booking.py
# Import/build the SYSTEM_PROMPT the same way the existing prompts test does
# (read tests/test_prompts*.py first — the prompt may be a constant or built by a
# function that reads LEARNINGS).
from prompts import SYSTEM_PROMPT  # adjust to the real import used by existing tests


def test_prompt_instructs_booking_detection():
    p = SYSTEM_PROMPT.lower()
    assert "booking" in p
    assert "scheduling" in p or "appointment" in p


def test_prompt_documents_booking_manifest_block():
    assert '"booking"' in SYSTEM_PROMPT
    for field in ["public_slug", "services", "resources", "hours", "destination_email"]:
        assert field in SYSTEM_PROMPT
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd "agents/CMS Connector - Website" && ../../backend/venv/Scripts/python -m pytest tests/test_prompts_booking.py -q`
Expected: FAIL — booking guidance absent.

- [ ] **Step 3: Add booking guidance to the SYSTEM_PROMPT**

Read `prompts.py`. Add a new rule block (and extend the manifest schema example) that instructs the model to:
1. **Detect a booking service** when the design/source shows SCHEDULING intent: a calendar/date-time slot selector, an "appointment / book a call / book a table / reserve / schedule" flow, or a services-with-durations + staff + opening-hours pattern, or an existing booking widget. A plain contact form (no scheduling) stays the `email_config` path — booking is only for scheduling.
2. **Extract** booking config from the design/source (demo values acceptable): business_name, brand colors (accent + primary), logo, services (name + duration_min), resources/staff (names), opening hours (weekday 0=Sun..6=Sat + local start/end), locale, timezone.
3. **Emit a top-level `booking` block** in the manifest when detected:
```json
"booking": {
  "detected": true,
  "public_slug": "<project-slug>",
  "business_name": "...",
  "accent_color": "#...", "primary_color": "#...", "logo_url": "...",
  "locale": "en", "timezone": "Europe/Berlin",
  "destination_email": "",
  "calendar_provider": "none",
  "reminders": { "enabled": true, "offsets_min": [1440, 120] },
  "services":  [{ "name": "Consultation", "duration_min": 30 }],
  "resources": [{ "name": "Staff", "type": "staff" }],
  "hours":     [{ "weekday": 1, "start_time": "09:00", "end_time": "17:00" }],
  "ui_wiring": { "components": ["<paths of the client's booking UI to wire>"], "fallback_embed": false }
}
```
Leave `destination_email` empty in the manifest (Stefan fills the client email in the report, or it defaults to his email at provision time). Note: the client's booking UI is wired to the booking API at integration time (headless) — `ui_wiring.components` lists the source files to connect; `fallback_embed:true` only when the site shows booking intent but has NO usable UI.

- [ ] **Step 4: Run to verify it passes**

Run: `cd "agents/CMS Connector - Website" && ../../backend/venv/Scripts/python -m pytest tests/test_prompts_booking.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "agents/CMS Connector - Website/prompts.py" "agents/CMS Connector - Website/tests/test_prompts_booking.py"
git commit -m "feat(connector): booking detection + manifest block in scan prompt"
```

---

## Task B2: Booking provisioning + client `lib/booking.ts` (scan.py)

**Files:**
- Modify: `agents/CMS Connector - Website/scan.py`
- Test: `agents/CMS Connector - Website/tests/test_scan_booking.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# agents/CMS Connector - Website/tests/test_scan_booking.py
# Read tests/test_scan*.py first for the HTTP-mock style (urllib/_http call log).
from unittest.mock import patch
import scan  # adjust import to match existing scan tests


def _manifest():
    return {
        "project_slug": "acme",
        "framework": "next",
        "services": [],
        "booking": {
            "detected": True, "public_slug": "acme", "business_name": "Acme",
            "accent_color": "#abcdef", "primary_color": "#123456", "logo_url": "",
            "locale": "en", "timezone": "Europe/Berlin", "destination_email": "client@acme.com",
            "calendar_provider": "none", "reminders": {"enabled": True, "offsets_min": [1440, 120]},
            "services": [{"name": "Cut", "duration_min": 45}],
            "resources": [{"name": "Sam", "type": "staff"}],
            "hours": [{"weekday": 1, "start_time": "09:00", "end_time": "17:00"}],
            "ui_wiring": {"components": ["src/components/Booking.tsx"], "fallback_embed": False},
        },
    }


def test_booking_provision_order_and_destination_email(...):
    # Mock the admin API; assert the call ORDER:
    #  POST /projects/acme/bookings/enable  → before any settings/services PATCH
    #  PATCH /projects/acme/bookings/settings includes owner_notification_email == "client@acme.com"
    #  services/resources/hours replace happen after enable
    ...


def test_booking_destination_defaults_to_stefan_when_empty(...):
    # destination_email == "" → settings PATCH owner_notification_email == "stefanromanpers@gmail.com"
    ...


def test_generates_lib_booking_ts(...):
    # the generated client file lib/booking.ts is written with the slug + getServices/getAvailability/createBooking
    ...
```
(Fill in the mock + assertions to match the existing scan test harness — the contract is: enable-first ordering, destination-email logic, `lib/booking.ts` emitted.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd "agents/CMS Connector - Website" && ../../backend/venv/Scripts/python -m pytest tests/test_scan_booking.py -q`
Expected: FAIL — no booking provisioning path.

- [ ] **Step 3: Implement the booking provisioning path in `scan.py`**

Read `scan.py` (`_provision`, `_http`, `_vercel_setup`, the manifest handling). Add a `_provision_booking(manifest, project_slug)` invoked from `_provision` when `manifest.get("booking", {}).get("detected")`:
1. `POST /projects/{slug}/bookings/enable` (admin) — idempotent.
2. `PATCH /projects/{slug}/bookings/settings` with: `public_slug` (= booking.public_slug or project slug), `business_name`, `timezone`, `locale`, `email_from_name` (= business_name), `accent_color`, `primary_color`, `calendar_provider:"none"`, `reminders_enabled` (= reminders.enabled), `reminder_offsets_min` (= reminders.offsets_min), and `owner_notification_email = booking["destination_email"] or "stefanromanpers@gmail.com"`.
3. Replace services: delete the seeded default `Consultation`, then `POST .../bookings/services` for each manifest service (`name`, `duration_min`); replace resources similarly (`name`, `type`). Ensure each service is linked to ≥1 resource (the create API links; verify the link is requested).
4. `PUT .../bookings/hours` with the manifest hours.
5. If `booking.logo_url`/a logo asset exists, `POST .../bookings/logo`.
6. Generate the client file (Step 4) and set the env var (Step 5).

- [ ] **Step 4: Generate `lib/booking.ts` in the client repo**

In `_provision_booking` (or `output_writer`), write `lib/booking.ts` into the client repo with this content (the booking analog of the content client), substituting the slug + env-var name by framework:

```ts
// Auto-generated by the CMS Connector. Headless booking client for "{SLUG}".
const BASE = process.env.{ENVPREFIX}BOOKING_API_BASE!;     // e.g. https://cms-backend-roman.vercel.app
const SLUG = "{SLUG}";

export type Service = { id: string; name: string; duration_min: number };
export type Slot = { start_utc: string };

export async function getServices(): Promise<Service[]> {
  const r = await fetch(`${BASE}/booking/${SLUG}/services`);
  if (!r.ok) throw new Error("booking: services failed");
  return (await r.json()).services as Service[];
}
export async function getAvailability(serviceId: string, from: string, to: string) {
  const r = await fetch(`${BASE}/booking/${SLUG}/availability?service_id=${serviceId}&from=${from}&to=${to}`);
  if (!r.ok) throw new Error("booking: availability failed");
  return (await r.json()).days as { date: string; slots: Slot[] }[];
}
export async function createBooking(input: {
  service_id: string; start_utc: string;
  customer: { name: string; email: string; phone?: string; tz?: string };
  note?: string;
}) {
  const r = await fetch(`${BASE}/booking/${SLUG}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...input, website: "" }),  // website = honeypot, always empty
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "booking: create failed");
  return r.json() as Promise<{ success: boolean; booking_id: string; manage_url: string; start: string; end: string }>;
}
export async function getManage(token: string) {
  return (await fetch(`${BASE}/booking/manage/${token}`)).json();
}
export async function reschedule(token: string, slot_start: string) {
  return (await fetch(`${BASE}/booking/manage/${token}/reschedule`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ slot_start }),
  })).json();
}
export async function cancel(token: string) {
  return (await fetch(`${BASE}/booking/manage/${token}/cancel`, { method: "POST" })).json();
}
```
`{ENVPREFIX}` = `NEXT_PUBLIC_` (next) / `VITE_` (vite-react) / `PUBLIC_` (astro) / `NEXT_PUBLIC_` (default). The actual UI wiring (connecting the design's service picker/date-time/form to these functions) is performed by the Phase-4 integration reasoning over the specific client components — this task only guarantees the lib + provisioning exist.

- [ ] **Step 5: Set the booking env var**

In `_vercel_setup` (or alongside the CMS endpoint wiring), set `{ENVPREFIX}BOOKING_API_BASE` to the backend base (`https://cms-backend-roman.vercel.app`) on prod + preview, using the same framework-prefix logic added for the multilang `NEXT_PUBLIC_CMS_ENDPOINT`.

- [ ] **Step 6: Run to verify it passes**

Run: `cd "agents/CMS Connector - Website" && ../../backend/venv/Scripts/python -m pytest tests/test_scan_booking.py tests/ -q`
Expected: PASS (new booking tests + the existing suite unaffected — booking path only runs when `manifest.booking.detected`).

- [ ] **Step 7: Commit**

```bash
git add "agents/CMS Connector - Website/scan.py" "agents/CMS Connector - Website/tests/test_scan_booking.py"
git commit -m "feat(connector): provision booking backend + generate lib/booking.ts"
```

---

## Task B3: Booking config in `cms.config.json` (output_writer.py)

**Files:**
- Modify: `agents/CMS Connector - Website/output_writer.py`
- Test: `agents/CMS Connector - Website/tests/test_output_writer_booking.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# agents/CMS Connector - Website/tests/test_output_writer_booking.py
import json, output_writer  # adjust to existing output_writer test import


def test_cms_config_includes_booking(tmp_path):
    manifest = {"project_slug": "acme", "endpoint": "https://x/content",
                "services": [], "booking": {"detected": True, "public_slug": "acme"}}
    # call the same writer the existing test uses; read the produced cms.config.json
    # assert it has a "booking": {"slug": "acme"} (or similar) block.
    ...


def test_cms_config_no_booking_when_absent(tmp_path):
    manifest = {"project_slug": "acme", "endpoint": "https://x/content", "services": []}
    # assert no "booking" key when manifest has none (back-compat)
    ...
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd "agents/CMS Connector - Website" && ../../backend/venv/Scripts/python -m pytest tests/test_output_writer_booking.py -q`
Expected: FAIL.

- [ ] **Step 3: Add the booking block to `cms.config.json`**

Read `output_writer.py`. When `manifest.get("booking", {}).get("detected")`, add to the slim `cms.config.json`: `"booking": {"slug": <public_slug>, "apiBase": "<base>/booking"}`. `cms-provision.json` (full manifest dump) already carries the whole booking block — confirm. Omit the booking key entirely when not detected (back-compat).

- [ ] **Step 4: Run to verify it passes**

Run: `cd "agents/CMS Connector - Website" && ../../backend/venv/Scripts/python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "agents/CMS Connector - Website/output_writer.py" "agents/CMS Connector - Website/tests/test_output_writer_booking.py"
git commit -m "feat(connector): emit booking slug/apiBase in cms.config.json"
```

---

## Task B4: Phase docs — report section, integration steps, smoke matrix

**Files:**
- Modify: `agents/CMS Connector - Website/phases/2-scan.md`, `phases/4-integration.md`, `phases/5-testing.md`

- [ ] **Step 1: `2-scan.md` — add the "Booking Service" report section**

Document a new required `## Booking Service` section in the human-review report (rendered only when `booking.detected`): proposed `public_slug`, business name, color swatches, the **services** table, the **resources/staff** list, the weekly **hours** grid, **destination email** (note: edit to the client email, else defaults to `stefanromanpers@gmail.com`), locale/timezone, `calendar=none`, reminder offsets, the **client UI components** to be wired (or "iframe fallback"), and the public API contract the UI will use. State that Stefan edits this before Phase 4.

- [ ] **Step 2: `4-integration.md` — booking provisioning + wiring steps**

Document the Phase-4 booking sub-steps matching `scan.py._provision_booking`: (a) `enable` first; (b) PATCH settings incl. destination-email logic (client-or-Stefan) + company name + colors + `calendar=none`; (c) replace services/resources/hours (every service linked to ≥1 resource); (d) generate `lib/booking.ts` + set `*BOOKING_API_BASE`; (e) wire the design's booking UI (service picker → `getServices`, date/time → `getAvailability`, form submit → `createBooking`, success → show `manage_url`); (f) confirmation emails use the centralized manage page — no client manage UI needed.

- [ ] **Step 3: `5-testing.md` — booking smoke matrix**

Add a booking smoke block (run when booking was provisioned), using the e2e email short-circuit so no real mail sends: list services → availability → create booking (+ honeypot non-empty → fake success no row; + double-book same slot → 409) → `GET /booking/manage/{token}` → reschedule → cancel → `POST /projects/{slug}/bookings/email-preview` for confirmation/reschedule/cancellation/reminder (assert company name + accent present, **no "Stefan"**) → `POST /booking/cron/reminders` with `X-Cron-Secret` → client build/render check. Fix the draft-token header note here too if present (`X-CMS-Preview-Token`, already done in the multilang pass). Any red test blocks Phase-6 "done".

- [ ] **Step 4: Verify (docs)**

Re-read the three docs; confirm they describe the booking flow consistently with `scan.py`/`prompts.py` and that the smoke matrix matches the real endpoints. No automated test (docs).

- [ ] **Step 5: Commit**

```bash
git add "agents/CMS Connector - Website/phases/2-scan.md" "agents/CMS Connector - Website/phases/4-integration.md" "agents/CMS Connector - Website/phases/5-testing.md"
git commit -m "docs(connector): booking report section + integration + smoke matrix"
```

---

## Task B5: AGENTS.md glossary/contract + widened self-improvement (LEARNINGS + SKILL)

**Files:**
- Modify: `agents/CMS Connector - Website/AGENTS.md`, `LEARNINGS.md`, `SKILL.md`

- [ ] **Step 1: `AGENTS.md` — glossary + generated-client contract**

Add to the glossary: the **booking service** (headless backend, tenant=project, addressed by `public_slug`) and the manifest `booking` block. Under "Generated client website contracts," document the headless booking contract: the client UI calls `lib/booking.ts` (`getServices`/`getAvailability`/`createBooking`/manage) against `{BOOKING_API_BASE}/booking/{slug}/…`; destination email = client-or-Stefan; manage flow is centralized.

- [ ] **Step 2: `LEARNINGS.md` — Booking heading**

Add a `## Booking` (or per-phase) heading with seed rules: detection (scheduling vs contact-form), provisioning order (`enable` first, every service linked to a resource, hours required), destination-email default, `calendar='none'` for clients, `email_copy` for company wording.

- [ ] **Step 3: `SKILL.md` — widen the self-improvement loop (positive + negative, cross-project)**

Read `SKILL.md`'s self-improvement section (today it records "should have caught" misses). Rewrite it so the agent records **both**: negative feedback ("don't do X / always do Y") **and** positive feedback ("Stefan praised Z — keep doing it"), each as a dated, one-line, append-only rule under the matching phase/area in `LEARNINGS.md`. State explicitly that these are global to the agent, fed into every future run, so corrections AND confirmed-good behaviors carry across all client projects (including booking).

- [ ] **Step 4: Verify (docs)**

Confirm `AGENTS.md`'s booking include/exclude + contract match `prompts.py` (the narrowed contact-form-vs-booking rule), and that the self-improvement section now explicitly covers positive feedback. No automated test.

- [ ] **Step 5: Commit**

```bash
git add "agents/CMS Connector - Website/AGENTS.md" "agents/CMS Connector - Website/LEARNINGS.md" "agents/CMS Connector - Website/SKILL.md"
git commit -m "docs(connector): booking contract + widened positive/negative self-improvement"
```

---

## Final verification

- [ ] **Step 1: Backend booking tests** — `cd backend && venv/Scripts/python -m pytest auth_service/tests/ -q` → all green (booking-email changes + the conftest null-provider fixture; no "Stefan" assertions fail).
- [ ] **Step 2: Connector suite** — `cd "agents/CMS Connector - Website" && ../../backend/venv/Scripts/python -m pytest tests/ -q` → all green (booking prompts/scan/output_writer tests + existing).
- [ ] **Step 3: Frontend** — `cd frontend && npm test -- BookingCalendar` → green; `npx tsc --noEmit` clean for changed files.
- [ ] **Step 4: Final review** — dispatch a reviewer over the whole diff for cross-cutting consistency (manifest `booking` block ↔ scan provisioning ↔ output_writer ↔ docs; destination-email logic; lib/booking.ts ↔ public API contract; no "Stefan" anywhere in default booking copy).

---

## Self-review (completed during authoring)

**Spec coverage:** ✅ detection (B1) · manifest+report section (B1, B4) · provisioning + destination email + company name + colors (B2) · `lib/booking.ts` + wiring + env (B2, B4) · centralized manage (B4) · cms.config.json (B3) · module fixes: Stefan (A1) + widget colors (A2) · smoke matrix (B4) · widened LEARNINGS positive+negative (B5). Out-of-scope items (per-tenant From address, non-English booking strings, custom manage page, capacity>1) are explicitly not tasked.

**Placeholder scan:** Code tasks (A1, A2, B2 lib/booking.ts, B3) carry complete code. The test bodies in B2/B3 and the A1 render-call deliberately defer the exact mock wiring to "match the existing test harness" (the harness style must be read first) but pin the **assertions/contract** — this is intentional grounding, not a vague requirement. Doc tasks (B4, B5) and prompt prose (B1) specify exact content to add.

**Type/name consistency:** ✅ the manifest `booking` block fields (B1) are exactly what `scan.py` consumes (B2) and `output_writer` reads (B3). `lib/booking.ts` function names (`getServices`/`getAvailability`/`createBooking`/`getManage`/`reschedule`/`cancel`) and the endpoints they call match the analyzed public API. `owner_notification_email` default `stefanromanpers@gmail.com` is consistent across B2 + B4. The widget fix overrides `--color-accent` (the token the existing utilities consume), consistent A2 test ↔ implementation.
```
