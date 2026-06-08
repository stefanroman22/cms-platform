# Dashboard Overhaul — Design Spec

**Date:** 2026-06-08
**Branch:** `feat/lead-scraper-system`
**Status:** Approved (design); pending spec review → plan

## Summary

A coordinated overhaul of the CMS dashboard spanning the **Leads** and **Booking**
modules plus a shared visual layer. Eight workstreams sit on top of one shared
foundation (gold theme tokens + shared label maps). Each workstream has a single
clear purpose, a well-defined interface, and is independently testable. The
booking-decoupling workstream is the architecturally heaviest and is described in
the most detail.

### Decisions locked during brainstorming

1. **Product column reuses `lead_type`.** The three product categories
   (Website / AI Workflow / Website + AI Workflow) map exactly onto the existing
   `lead_type` enum (`website` / `automation` / `both`). We relabel in the UI
   rather than add a redundant `product` column or migration.
2. **Booking decoupling = Shared Booking Client SDK.** Framework-agnostic JS
   adapter + hardened backend contract + connector field-mapping enforcement.
3. **Overview layout prefs in `localStorage`,** abstracted behind a store
   interface so it can move to the backend later without UI changes.
4. **Staff rename = UI relabel, keep types.** `booking_resources` table and the
   room/equipment/generic types stay; the UI leads with "Staff" (people).
5. **Per-staff Overview.** When multiple staff exist, the user can scope the
   entire Overview (calendar + every stat/chart) to a single staff member; the
   selected scope persists in `localStorage` alongside the layout.

---

## 0. Shared foundation

Built first; every visual workstream depends on it.

### 0.1 Gold theme tokens for the dashboard

- **Current:** dashboard is plain Tailwind zinc; the landing page owns
  `--color-accent: #c9a961` (antique brass), `--color-accent-muted: #8b7a47`,
  `--color-accent-glow: #c9a96133` inside a `@theme` block in
  `frontend/src/app/globals.css`. The dashboard does not reference these.
- **Change:** make the brass accent tokens available within the dashboard scope
  and add a small set of reusable accent primitives (shared class constants or
  utilities): active-tab underline, focus ring, primary-CTA, KPI highlight,
  calendar "today" marker.
- **Constraint — minimalistic.** Accent is applied to active states, key CTAs,
  the calendar "today" marker, and at most one or two KPI highlights. The gray
  zinc base stays dominant. No gold floods, no gradients on broad surfaces. This
  mirrors the landing page's high-impact / low-quantity gold language.
- **Interface:** a documented set of token names + class constants other
  workstreams consume. Changing the accent value in one place re-themes the
  dashboard.

### 0.2 Shared label maps

- One source of truth for **Product labels** (derived from `lead_type`):
  `website → "Website"`, `automation → "AI Workflow"`,
  `both → "Website + AI Workflow"`, with a per-value badge class.
- One source of truth for **Staff terminology** so leads + booking stay
  consistent.

---

## 1. Leads — Product column (replaces Presence)

- **Current:** `LeadsTable.tsx` renders a **Presence** column from `web_presence`
  (`none` / `social_only` / `has_website` / `unknown`) via `WEB_PRESENCE_LABEL` /
  `WEB_PRESENCE_BADGE_CN` in `frontend/src/lib/leadEnums.ts`.
- **Change:** replace that column with a **Product** column driven by `lead_type`,
  relabeled via the shared label map (§0.2): Website / AI Workflow /
  Website + AI Workflow, each with a distinct badge. Applies to both the desktop
  table and the mobile card list.
- **`web_presence` is untouched** in the DB and the detail drawer — it is still
  scraped and still editable in the drawer; it simply no longer occupies the
  table column.
- **Default:** scraper and the manual-add form default `lead_type` to `website`
  ("just put category website for now").
- **Interface:** the column reads `lead.lead_type` and the shared label map.
  No backend change required for the column itself.

## 2. Leads — Manual "Add Lead" form

- **Current gap:** there is **no** `POST /admin/leads` endpoint — leads are 100%
  scraper-sourced. `admin_leads.py` exposes only GET (list/one), PATCH, DELETE.
- **Backend:** add `POST /admin/leads` guarded by the same admin auth as the rest
  of `admin_leads.py`, accepting a new `LeadCreate` schema covering all writable
  lead fields **including reviews** (the JSONB `reviews` array) and ratings,
  hours, contact/links, location, presence, product (`lead_type`), notes.
  Inserts with `primary_source = 'manual'`; sets `external_id` to a generated
  manual key so it does not collide with scraper dedup. Returns the created
  `LeadOut`.
- **Frontend:** an **"Add lead"** button on `LeadsDashboard` opens a drawer/modal
  form, grouped into sections:
  - Identity (business_name, category, description/about)
  - Location (country, region, city, address, postal_code)
  - Contact & links (phone, email, website_url, facebook_url, instagram_url)
  - Presence & Product (web_presence, lead_type)
  - Ratings & Reviews (rating, review_count, + repeatable reviews sub-form:
    author, rating, text, date)
  - Opening hours (reuse the existing hours editor pattern if available)
  - Notes
  - Required minimum: business_name. Everything else optional.
- On submit the lead inserts and appears in the table immediately (optimistic or
  refetch — match existing dashboard data-flow conventions).
- **Interface:** form state → `LeadCreate` payload → `POST /admin/leads` → table
  refresh.

## 3. Booking — Settings cleanup

### 3.1 Remove widget styling from the dashboard

- **Current:** `BookingSettingsForm.tsx` has a **"Widget accent color"** field
  (`widget_color`); `SettingsPatch` accepts `widget_color`; the public
  `/booking/{slug}/config` returns it; the widget applies it as `--color-accent`.
- **Change:** remove the field from the Settings UI and drop `widget_color` from
  the `SettingsPatch` schema so the **dashboard can no longer edit it**. **The
  booking widget's color now belongs to the client site** — the connector detects
  the client's accent (or the widget inherits the host page's `--color-accent` CSS
  var). The dashboard owns **no** widget/form styling.
- **Email branding stays.** Email accent color + logo remain editable in the
  Email Template editor — emails are rendered/sent by the backend, so their
  branding is legitimately a backend/dashboard concern.
- **Non-destructive (no breakage for live sites):** the
  `booking_settings.widget_color` DB column is **retained** (no drop migration)
  and the public `/booking/{slug}/config` endpoint **still returns the stored
  value**, so already-provisioned widgets are unaffected. Only the dashboard's
  ability to *edit* it is removed; going forward, widget styling is owned by the
  client/connector.

### 3.2 Rename "Resources" → "Staff"

- **Current:** a "Resources" tab + `ResourcesManager` / `ResourceFormDrawer`;
  `booking_resources` has `type` (`staff` | `room` | `equipment` | `generic`) and
  `capacity` (how many can perform a service in parallel).
- **Change:** relabel the tab, headings, and copy to **"Staff"** and lead with
  people. The `type` selector stays (room/equipment/generic available but
  de-emphasized, defaulting to staff). The backend table name and schema are
  unchanged — UI-only relabel.

### 3.3 Service ↔ Staff restriction

- **Already enforced:** `booking_service_resources` (service↔resource linker) plus
  `_free_resource_for` ensure only linked staff can be auto-assigned to a service.
  `ServiceFormDrawer` already exposes resource-assignment checkboxes.
- **Change:** surface this clearly under the Staff/Services relabel ("Which staff
  can perform this service"), and **verify** availability + assignment are
  computed only against eligible staff. Ship tests proving an unlinked staff
  member is never offered or assigned for a service.

## 4. Booking — Customizable Overview

### 4.1 Widget-registry architecture

- Each overview widget is a self-describing registry entry:
  `{ id, title, defaultSize, defaultEnabled, render(scope) }`.
- A **layout config** = an ordered list of `{ id, size, enabled }`, read from a
  `localStorage`-backed store behind an interface (`OverviewPrefsStore`) so it can
  later move to the backend without touching widgets.
- A **"Customize" panel** lets the user toggle widgets on/off and reorder them.
- **Extensible:** a new widget = append one registry entry; no changes to the
  page shell or the prefs store.

### 4.2 Widgets

Existing (ported into the registry): KPI group, bookings-over-time area chart,
by-service bar, by-status donut, peak-times heatmap.

New:
- **Calendar widget (default-on):** Google-Calendar-style month / week / day view
  of bookings, built custom (reusing patterns from the public-widget
  `MonthGrid.tsx`) — lightweight, dependency-free, gold-themeable. Events colored
  by service; "today" marked in brass; click an event → appointment drawer.
- **By-staff widgets:** appointments-per-staff and staff-utilization stats/charts,
  powered by `/stats` + appointments data (extended if needed).

Defaults shown on first load: **Calendar + general KPI overview**.

### 4.3 Per-staff scope

- A **staff-scope selector** ("All staff" | a specific staff member). When a staff
  member is selected, the calendar and **every** stat/chart widget filter to that
  person's appointments and metrics.
- The selected scope persists in `localStorage` alongside the layout config, so
  returning to Overview restores the user's own calendar without re-selecting.
- **Interface:** scope value flows into each widget's `render(scope)`; widgets
  that don't support scoping ignore it. Staff attribution of a booking is its
  assigned `bookings.resource_id` (the staff resource); the scope selector lists
  active staff-type resources.

## 5. Booking — Email preview mobile UX

- **Current:** on mobile, "Show preview" reveals the iframe **below** the editor
  (`hidden lg:block` → `block`), forcing the user to scroll.
- **Change:** on mobile, tapping "Show preview" opens a **full-screen Motion
  sheet** (`motion/react`) that slides up over the editor — preview immediately in
  view, no scrolling — with a cross-fade between editor and preview and a clear
  "Done/close" affordance. Respects `prefers-reduced-motion`.
- **Desktop split-view is unchanged.**
- **Interface:** a `showPreview` toggle drives an `AnimatePresence` sheet on
  mobile; the same `EmailPreviewFrame` renders inside it.

## 6. Booking — Hide mobile tab scrollbar

- **Current:** the booking tab strip in `BookingsSection.tsx` uses
  `overflow-x-auto` **without** `no-scrollbar`, so the scrollbar shows on mobile.
- **Change:** add the existing `.no-scrollbar` utility (already used by
  `SectionRail` / `PageTabs`) to that strip. Keeps full scrollability; hides the
  bar. One-line change.

## 7. Booking decoupling — Shared Booking Client SDK

**Goal:** a client website's booking form may have any styling, colors, or
question order, yet must always send a **correct, complete** payload to the
**correct** backend target. We never dictate the client's UI. Three coordinated
pieces:

### 7.1 Backend contract hardening

- Version the public create-booking contract.
- Return **precise field-level validation errors** (which field, why) instead of a
  generic 422, so miswired forms produce actionable diagnostics.
- Expose a **machine-readable contract**: `GET /booking/{slug}/contract` returning
  required fields, types, and the contract version. This is the single source of
  truth the SDK + connector validate against.
- Existing `CreateIn` (`service_id`, `start_utc`, `customer{name,email,phone,tz}`,
  `note`, `website` honeypot) is the baseline; hardening makes the requirements
  explicit and machine-checkable. Behavior-preserving for already-valid payloads.

### 7.2 `@roman/booking-client` SDK

- A tiny **framework-agnostic** JS adapter the client form calls:
  `createBooking(payload)` (plus helpers for config/services/availability as
  needed).
- Responsibilities:
  - **Validate + normalize** the payload against the versioned contract *before*
    sending (field presence, types, email shape, ISO datetime).
  - **Route** to the correct slug/endpoint (the target), so the client form cannot
    accidentally post to the wrong tenant.
  - Surface clear errors the client UI can render however it likes.
- The client owns 100% of the UI; the SDK owns correctness + targeting. No styling
  in the SDK.

### 7.3 Connector enforcement

- During import, the CMS connector **maps the client form's fields to the SDK
  contract** and records the binding.
- The connector **test matrix fails** if any required contract field cannot be
  mapped — a miswired form is caught at provisioning, not in production.
- Connector output (`cms.config.json`) carries the slug + apiBase + contract
  version so the SDK is correctly targeted.

## 8. Testing

Every workstream ships with tests; final verification runs all suites green.

- **Backend (pytest):** `LeadCreate` insert path; hardened booking contract +
  `/contract` endpoint + field-level errors; staff-eligibility (unlinked staff
  never assigned); `widget_color` removal from `SettingsPatch`.
- **Frontend:** component/build tests for the Product column, Add-Lead form,
  Overview widget registry + per-staff scope + localStorage persistence, email
  preview sheet, settings without widget color.
- **SDK:** unit tests for validate/normalize/route, including rejection of
  incomplete/mistyped payloads.
- **Connector:** field-mapping enforcement (test matrix fails on unmappable
  required field).
- **Playwright user-stories:** add-lead flow, overview customization +
  per-staff scope persistence, email-preview sheet on mobile.

---

## Execution

1. **Shared foundation first:** theme tokens + label maps land before anything
   consumes them.
2. **Fan out** the eight workstreams across parallel agents (mostly independent
   after the foundation), with codependent pairs sequenced so they don't collide:
   - settings-cleanup (§3.1) ↔ decoupling (§7) — both touch the contract/connector.
   - staff-rename (§3.2/3.3) ↔ overview-by-staff (§4.2/4.3) — both touch staff.
3. **Adversarial verification** on each piece; full test suites green before any
   completion claim.
4. **No auto-commit** — per project preference, commit only on explicit request.

## Out of scope

- Backend persistence of overview layout prefs (localStorage only for now; the
  store interface leaves the door open).
- Dropping the `widget_color` DB column or the room/equipment/generic resource
  types (retained, just de-emphasized / no longer dashboard-editable).
- Any change to the client website's visual design — explicitly forbidden by the
  decoupling goal.
- Customer-facing staff picker in the public widget (this spec covers the
  dashboard + contract, not new public-widget UI).
