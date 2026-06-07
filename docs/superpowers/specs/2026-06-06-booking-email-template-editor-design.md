# Booking Email Template Editor — Design Spec

**Date:** 2026-06-06
**Author:** Stefan Roman (via Claude)
**Status:** Approved (design)

**Builds on:** the multi-tenant booking module (P1–P4) — emails render server-side
via `email_layout.Brand` + `booking_i18n` strings; the dashboard "Bookings"
section already edits brand fields in `BookingSettingsForm`.

## Goal

Let a project owner customize their booking emails from the dashboard — upload a
logo, pick a brand color, and edit the wording of every field — with a **live,
accurate preview** for each client-facing email (confirmation, reschedule,
cancellation, reminder). Editing is per-tenant; defaults remain the fallback.

## Locked decisions (brainstorming)

1. **Styling scope:** logo + a single brand/accent color (applied to the email
   header bar **and** primary buttons) + editable copy text. **No** custom fonts,
   per-field sizes, or rich text (email-client-unsafe).
2. **Emails covered:** the 4 client-facing ones — confirmation, reschedule,
   cancellation, reminder. Host/owner emails keep defaults (shared brand still
   applies to them).
3. **Copy storage:** per-tenant overrides in a new `booking_settings.email_copy`
   JSONB column; missing keys fall back to `booking_i18n` defaults.
4. **Preview:** server-rendered (the real renderers) via an endpoint, shown in an
   iframe, debounced ≈300ms — byte-identical to the sent email.
5. **Save model:** explicit Save; the preview reflects the unsaved draft.

## Scope

**In:** the `email_copy` column (additive migration), override-aware rendering,
accent-color-on-buttons, three new owner endpoints (`email-template` schema,
`email-preview`, `logo` upload), and the "Emails" editor tab with live preview.

**Out:** custom fonts / rich text; host/owner-email editing; brand
auto-extraction; multi-language copy (the mechanism is per-key strings; a second
locale is a later concern — editor edits the tenant's single locale).

## Data model

`booking_settings.email_copy jsonb not null default '{}'` — a flat
`{string_key: custom_text}` map (only overridden keys). Additive migration
`backend/migrations/2026_06_06_booking_email_copy.sql`, applied via MCP.
`TenantConfig` gains `email_copy: dict` (added to `_FIELDS` + `_to_config`,
default `{}`).

## Backend

### Override-aware rendering
Add `tt(overrides, locale, key, **fmt)` to `booking_i18n` (override → else
`t(locale, key, **fmt)`). Thread an optional `copy: dict | None = None` through
the **client-facing** render + send functions:
`booking_email.render_visitor_html` / `send_visitor_confirmation`,
`booking_manage_email.render_cancel_client` / `render_reschedule_client` /
`send_cancellation` / `send_reschedule`, `booking_reminder_email.render_html` /
`send`. Each uses `tt(copy, locale, key)` for its subjects + body strings.
Behavior is unchanged when `copy` is None/empty. The routers that send
(`booking.py` create/cancel/reschedule/reminder, `booking_admin.py` owner
cancel/reschedule) pass `copy=cfg.email_copy`.

### Accent color on buttons
`email_layout` already applies `brand.accent` to the header. Extend the primary
buttons (the "Join the call" / "Manage" CTAs in `booking_email`,
`booking_manage_email`, `booking_reminder_email`) to use `brand.accent` instead
of the hardcoded `#18181b`. Default brand accent stays `#18181b` so unbranded
output is unchanged.

### Editable field schema — `booking_i18n.EDITABLE_EMAIL_FIELDS`
A list grouping the editable keys (label + group), the single source the editor
renders from:
- **Shared:** `manage_cta`, `join_cta`, `add_cal_cta`, `manage_prompt`
- **Confirmation:** `confirm_subject`, `header_confirmed`, `confirmed_heading`, `confirmed_subtext`
- **Reschedule:** `reschedule_subject`, `header_moved`, `reschedule_client_heading`
- **Cancellation:** `cancel_subject`, `header_cancelled`, `cancel_client_heading`
- **Reminder:** `reminder_subject`, `header_reminder`, `reminder_heading`

### Endpoints (owner-scoped, `require_project_access`)
- `GET /projects/{slug}/bookings/email-template` → `{ brand: {logo_url, accent_color, business_name}, fields: [{key, label, group, default, value}] }` (value = current override or "").
- `POST /projects/{slug}/bookings/email-preview` body `{case, draft:{logo_url, accent_color, business_name, email_copy}}` → builds a `Brand` from the draft + **sample booking data** (fixed fake name/date/`when_label`) + calls the matching `render_*` fn with `copy=draft.email_copy` → `{html}`. `case ∈ {confirmation, reschedule, cancellation, reminder}`.
- `POST /projects/{slug}/bookings/logo` (multipart `file`) → mirror `workspace.py` upload: validate it's an image, size ≤ 5 MB, reject `svg/html` mimes; store in `cms-files` at `{tenant_id}/booking-logo/{uuid}.{ext}`; return `{url}`.
- `SettingsPatch` gains `email_copy: dict | None`; `update_settings` already does a generic update. (Saving the editor = PATCH settings with `email_copy` + brand fields.)

## Frontend — the "Emails" tab

A new tab in `BookingsSection` (`components/dashboard/booking/`), built per
ui-ux-pro-max (split view, progressive disclosure, one primary action, debounced
preview, reduced-motion).

- **`EmailTemplateEditor.tsx`** — loads `GET email-template`; holds a draft
  (`{logo_url, accent_color, business_name, email_copy}`). **Split layout:**
  - **Left (controls, scrollable):** a **Brand** group — logo upload (file →
    `POST logo` → thumbnail; the existing FormData upload pattern) + a color
    picker (native `<input type=color>` + hex text, bound to `accent_color`).
    Then a **segmented case selector** (Confirmation · Reschedule · Cancellation ·
    Reminder) showing that case's fields, plus a **"Shared"** group rendered once.
    Each field: label, input/textarea, **default as placeholder**, a "Reset"
    affordance (clears the override). One **Save** button (PATCH settings).
  - **Right (preview):** `EmailPreviewFrame.tsx` — an `<iframe sandbox srcDoc>`;
    on any draft change, **debounced 300ms** `POST email-preview` for the active
    case → set `srcDoc`; soft cross-fade on swap (`prefers-reduced-motion`
    respected). Desktop: sticky side-by-side. Mobile: stacked + a Preview toggle.
  - `booking/api.ts` gains `getEmailTemplate`, `previewEmail`, `uploadBookingLogo`,
    and `patchSettings` already exists (extended with `email_copy`).
- Conventions: `lib/styles.ts`, `motion/react`, cursor-pointer, dark mode,
  responsive; smooth (instant field echo + debounced preview).

## Error & edge handling

- Preview/render failure → the iframe shows a neutral "Preview unavailable" state;
  editing still works.
- Logo upload: client-side type/size check + server guards; failure → inline error.
- Empty override → treated as "use default" (don't store empty strings; deleting
  the text resets to default).
- A `{placeholder}` in copy that the user removes (e.g. `{name}`) → `tt` formats
  best-effort and never crashes (the existing `t` already guards `KeyError`).
- Preview uses sample data, clearly representative (e.g. "Alex Carter", a near-future date).

## Testing

**Backend:** `tt` override + fallback; each render fn honors `copy` (shows the
override, not the default); `email-preview` returns HTML per case reflecting the
draft brand + copy; `email-template` returns the grouped schema with defaults +
values; logo upload guards (reject svg/oversize); accent applies to a button;
default (no copy/brand) output unchanged. **Frontend:** typecheck + build; a test
for the debounced preview call and a field-edit→draft-override round-trip
(fetch mocked).

## Conventions honored

Supabase service-role + app-layer authz; `cms-files` bucket + the existing
upload guards; `booking_i18n` as the default source of truth; `email_layout`
backward-compatible (`DEFAULT_BRAND` unchanged → issue-resolved + host emails
untouched); `lib/styles.ts`; `motion/react`; no auto-commit; additive migration
applied via MCP.
