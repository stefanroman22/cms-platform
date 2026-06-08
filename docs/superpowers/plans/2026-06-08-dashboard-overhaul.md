# Dashboard Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the CMS dashboard across Leads + Booking — Product column, manual lead entry, booking settings cleanup, a customizable per-staff Overview, mobile email-preview + scrollbar fixes, a gold accent theme, and a decoupled Booking Client SDK that enforces a correct payload contract.

**Architecture:** One shared foundation (gold accent tokens + label maps) underpins eight mostly-independent workstreams. Backend changes are additive and behavior-preserving (new `POST /admin/leads`, hardened booking contract + `/contract` endpoint, `/stats` staff filter, `widget_color` removed only from the editable patch). Frontend introduces a widget-registry Overview with a localStorage-backed prefs store. A framework-agnostic `booking-client` SDK validates/normalizes/routes booking payloads; the connector enforces field mapping.

**Tech Stack:** Next.js 16 / React 19 / TypeScript / Tailwind v4 / `motion` / `recharts` / `@dnd-kit/core` (frontend, tests via vitest + Testing Library); FastAPI / Pydantic / pytest (backend); Python connector agent (pytest). Spec: `docs/superpowers/specs/2026-06-08-dashboard-overhaul-design.md`.

## Conventions & commands

- **Frontend tests:** from `frontend/` → `npm run test` (vitest run). Single file: `npm run test -- src/path/file.test.ts`. Type check: `npm run typecheck`. Build: `npm run build`.
- **Backend tests:** from `backend/` activate venv (`source venv/Scripts/activate`), then `cd auth_service && python -m pytest tests -q`. Single test: `python -m pytest tests/test_x.py::test_name -v`.
- **Connector tests:** from `agents/CMS Connector - Website/` → `python -m pytest tests -q`.
- **No auto-commit:** the project rule is to commit only on explicit request. Where steps say "Commit", stage logically but **do not run `git commit` unless the user has asked**; treat commit steps as "checkpoint — changes staged, await commit approval." (This overrides the skill's frequent-commit default.)
- **Migrations:** none required. All backend changes reuse existing columns/tables.

---

## Task 0 — Shared foundation

**Files:**
- Modify: `frontend/src/lib/leadEnums.ts`
- Create: `frontend/src/lib/dashboardTheme.ts`
- Create: `frontend/src/lib/dashboardTheme.test.ts`
- Modify: `frontend/src/lib/leadEnums.test.ts` (create if absent)

### 0.1 Product (lead_type) labels + badges

- [ ] **Step 1: Write failing test** — `frontend/src/lib/leadEnums.test.ts`

```ts
import { describe, it, expect } from "vitest";
import { LEAD_TYPE_LABEL, LEAD_TYPE_BADGE_CN } from "./leadEnums";

describe("product (lead_type) labels", () => {
  it("uses the approved product wording", () => {
    expect(LEAD_TYPE_LABEL.website).toBe("Website");
    expect(LEAD_TYPE_LABEL.automation).toBe("AI Workflow");
    expect(LEAD_TYPE_LABEL.both).toBe("Website + AI Workflow");
  });
  it("has a badge class for every product value", () => {
    (Object.keys(LEAD_TYPE_LABEL) as (keyof typeof LEAD_TYPE_LABEL)[]).forEach((k) => {
      expect(LEAD_TYPE_BADGE_CN[k]).toBeTruthy();
    });
  });
});
```

- [ ] **Step 2: Run → fail** — `npm run test -- src/lib/leadEnums.test.ts` → FAIL (`LEAD_TYPE_BADGE_CN` undefined / label mismatch).

- [ ] **Step 3: Implement** — edit `frontend/src/lib/leadEnums.ts`:

```ts
export const LEAD_TYPE_LABEL = {
  website: "Website",
  automation: "AI Workflow",
  both: "Website + AI Workflow",
} as const;

// Product badge palette — gold accent reserved for the "both" (full) product.
export const LEAD_TYPE_BADGE_CN = {
  website: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  automation: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  both: "bg-accent/15 text-accent dark:bg-accent/15 dark:text-accent",
} as const;
```

- [ ] **Step 4: Run → pass** — `npm run test -- src/lib/leadEnums.test.ts` → PASS.

- [ ] **Step 5: Checkpoint** — stage `frontend/src/lib/leadEnums.ts`, `frontend/src/lib/leadEnums.test.ts`.

### 0.2 Dashboard accent theme constants

Brass tokens (`--color-accent` `#c9a961`, `--color-accent-muted`, `--color-accent-glow`) already exist globally via the `@theme` block in `globals.css`, so `text-accent` / `bg-accent` / `border-accent` utilities already resolve. This step centralizes the *sparing* usage patterns so workstreams apply gold consistently.

- [ ] **Step 1: Write failing test** — `frontend/src/lib/dashboardTheme.test.ts`

```ts
import { describe, it, expect } from "vitest";
import { dashAccent } from "./dashboardTheme";

describe("dashboard accent primitives", () => {
  it("exposes accent class constants", () => {
    expect(dashAccent.focusRing).toContain("ring-accent");
    expect(dashAccent.tabUnderline).toContain("bg-accent");
    expect(dashAccent.ctaPrimary).toContain("bg-accent");
    expect(dashAccent.kpiHighlight).toContain("text-accent");
  });
});
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — `frontend/src/lib/dashboardTheme.ts`:

```ts
// Sparing, high-impact gold accent primitives for the dashboard.
// The zinc base stays dominant; accent only on active states / key CTAs / one or two highlights.
export const dashAccent = {
  /** focus-visible ring for interactive controls */
  focusRing: "outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
  /** active tab / nav underline (use as the motion.span bg) */
  tabUnderline: "bg-accent",
  /** primary call-to-action button */
  ctaPrimary:
    "bg-accent text-bg hover:bg-accent-muted disabled:opacity-50 transition-colors",
  /** emphasise a single key metric */
  kpiHighlight: "text-accent",
  /** calendar 'today' marker ring */
  todayMarker: "ring-1 ring-accent text-accent",
} as const;
```

- [ ] **Step 4: Run → pass.**

- [ ] **Step 5: Checkpoint** — stage `dashboardTheme.ts(+test)`.

---

## Task 1 — Leads: Product column replaces Presence

**Depends on:** Task 0.1.
**Files:**
- Modify: `frontend/src/components/admin/leads/LeadsTable.tsx`
- Test: `frontend/src/components/admin/leads/LeadsTable.test.tsx` (create if absent)

- [ ] **Step 1: Write failing test** — render `LeadsTable` with a lead and assert the Product header + relabeled value appear and the Presence header is gone.

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { LeadsTable } from "./LeadsTable";
import type { Lead } from "./types";

const lead = { id: "1", business_name: "Acme", city: "Berlin", category: "cafe",
  web_presence: "none", lead_type: "both", rating: 4.5, review_count: 10,
  lead_status: "not_sent", payment_status: "not_applicable" } as unknown as Lead;

describe("LeadsTable product column", () => {
  it("shows Product header and relabeled lead_type, not Presence", () => {
    render(<LeadsTable leads={[lead]} onSelect={() => {}} />);
    expect(screen.getByText("Product")).toBeInTheDocument();
    expect(screen.queryByText("Presence")).not.toBeInTheDocument();
    expect(screen.getByText("Website + AI Workflow")).toBeInTheDocument();
  });
});
```

(Adjust props to the real `LeadsTable` signature — read the file first; it currently maps `WEB_PRESENCE_LABEL[l.web_presence]` into a "Presence" `<th>`.)

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — in `LeadsTable.tsx`:
  - Replace the `Presence` `<th>` text with `Product`.
  - Replace the desktop `<td>` `LeadBadge` using `WEB_PRESENCE_LABEL[l.web_presence]` / `WEB_PRESENCE_BADGE_CN[l.web_presence]` with `LEAD_TYPE_LABEL[l.lead_type]` / `LEAD_TYPE_BADGE_CN[l.lead_type]`.
  - Replace the mobile-card presence badge identically.
  - Update the import line to pull `LEAD_TYPE_LABEL, LEAD_TYPE_BADGE_CN` from `@/lib/leadEnums` and drop the now-unused `WEB_PRESENCE_*` imports **only if** no longer used in this file.

- [ ] **Step 4: Run → pass** + `npm run typecheck`.

- [ ] **Step 5: Checkpoint** — stage the two files.

---

## Task 2 — Leads: Manual "Add Lead"

**Files:**
- Modify: `backend/auth_service/models/schemas.py` (add `LeadCreate`)
- Modify: `backend/auth_service/routers/admin_leads.py` (add `POST /admin/leads`)
- Test: `backend/auth_service/tests/test_admin_leads_create.py`
- Create: `frontend/src/components/admin/leads/AddLeadDrawer.tsx`
- Modify: `frontend/src/components/admin/leads/LeadsDashboard.tsx` (Add-lead button + drawer wiring)
- Modify: `frontend/src/components/admin/leads/types.ts` (export a `LeadCreateInput` type if helpful)
- Test: `frontend/src/components/admin/leads/AddLeadDrawer.test.tsx`

### 2A Backend endpoint (TDD)

- [ ] **Step 1: Write failing test** — `tests/test_admin_leads_create.py`. Mirror the existing admin-leads test setup (read `tests/` for the auth/client fixtures — there is an admin bearer/session fixture used by other lead tests). Assert:
  - `POST /admin/leads` with `{ "business_name": "Manual Co", "lead_type": "website" }` → 201/200, body has `id`, `business_name == "Manual Co"`, `primary_source == "manual"`.
  - Posting `reviews` array round-trips into the response.
  - Missing `business_name` → 422.
  - Non-admin caller → 401/403.

- [ ] **Step 2: Run → fail** (`405 Method Not Allowed` — no POST route).

- [ ] **Step 3: Implement schema** — in `schemas.py`, add `LeadCreate` near `LeadUpdate`. Include every writable field with sane optionals; reviews/opening_hours as flexible JSON. Sketch:

```python
class LeadReviewIn(BaseModel):
    author: str = ""
    rating: float | None = None
    text: str = ""
    date: str = ""

class LeadCreate(BaseModel):
    business_name: str = Field(min_length=1)
    lead_type: LeadType = "website"
    web_presence: WebPresence = "unknown"
    category: str | None = None
    description: str | None = None
    about: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    address: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    email: str | None = None
    website_url: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    menu_url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    reviews: list[LeadReviewIn] = []
    opening_hours: dict | list | None = None
    languages: list[str] = []
    notes: str | None = None
```

(Confirm `LeadType` / `WebPresence` aliases exist in `schemas.py` — they were found at line ~487; reuse them.)

- [ ] **Step 4: Implement route** — in `admin_leads.py`, add a `POST ""` handler guarded by the same admin dependency the other handlers use (e.g. `admin_user_via_bearer_or_sid`). Insert via the same Supabase client/path the other lead writes use; set `primary_source="manual"` and a generated `external_id` like `f"manual:{uuid4()}"` to avoid scraper dedup collisions; serialize `reviews` to JSON. Return the inserted row mapped to `LeadOut`.

- [ ] **Step 5: Run → pass** — `python -m pytest tests/test_admin_leads_create.py -v`.

- [ ] **Step 6: Checkpoint** — stage backend files.

### 2B Frontend Add-Lead drawer (TDD)

- [ ] **Step 1: Write failing test** — `AddLeadDrawer.test.tsx`: renders when `open`, has a Business name input, an "Add review" button that appends a review row, and calls `onCreate` with a payload containing `business_name` + the reviews array on submit. Mock the create fn.

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `AddLeadDrawer.tsx`** — mirror the existing `LeadDetailDrawer.tsx` styling/animation (right-side `motion.aside`, `lead-drawer no-scrollbar` classes, `useReducedMotion`). Sections: Identity, Location, Contact & links, Presence & Product (two selects driven by `WEB_PRESENCE_LABEL` + `LEAD_TYPE_LABEL`), Ratings & Reviews (number inputs + a repeatable reviews list with add/remove), Opening hours (plain textarea or reuse `OpeningHoursSection` pattern), Notes. Use `dashAccent.ctaPrimary` for the Save button and `dashAccent.focusRing` on inputs. Submit builds the `LeadCreate` payload and calls a passed `onCreate`.

- [ ] **Step 4: Wire into `LeadsDashboard.tsx`** — add an "Add lead" button (top of the dashboard, near filters) that opens `AddLeadDrawer`; on create, call a new `createLead` helper that `POST`s to `/api/admin/leads` and then refetches/prepends to the list (match the dashboard's existing data-fetch pattern). Add the `createLead` fetch helper alongside the other admin-leads fetches (find where `PATCH /api/admin/leads/:id` is called and co-locate).

- [ ] **Step 5: Run → pass** + `npm run typecheck`.

- [ ] **Step 6: Checkpoint** — stage frontend files.

---

## Task 3 — Booking: Settings cleanup (widget color, Staff rename, service↔staff)

**Files:**
- Modify: `frontend/src/components/dashboard/booking/BookingSettingsForm.tsx` (remove widget color block)
- Modify: `frontend/src/components/dashboard/booking/api.ts` (drop `widget_color` from `SettingsPatch`; keep on `BookingSettings` read type)
- Modify: `backend/auth_service/models/booking_admin_schemas.py` (`SettingsPatch`: remove `widget_color`)
- Modify: `frontend/src/components/dashboard/booking/BookingsSection.tsx` (tab label "Resources" → "Staff")
- Modify: `frontend/src/components/dashboard/booking/ResourcesManager.tsx` + `ResourceFormDrawer.tsx` (copy: "Staff", default type staff)
- Modify: `frontend/src/components/dashboard/booking/ServiceFormDrawer.tsx` ("Assigned resources" → "Which staff can perform this service")
- Test: `backend/auth_service/tests/test_booking_settings_no_widget_color.py`
- Test: `backend/auth_service/tests/test_booking_service_staff_eligibility.py`
- Test: `frontend/src/components/dashboard/booking/BookingSettingsForm.test.tsx`

### 3A Remove widget color from the editable patch (backend TDD)

- [ ] **Step 1: Write failing test** — `test_booking_settings_no_widget_color.py`: import `SettingsPatch` from `booking_admin_schemas`; assert `"widget_color" not in SettingsPatch.model_fields`. (Mirror how other booking schema tests import.)

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — remove the `widget_color: str | None = None` line from `SettingsPatch` in `booking_admin_schemas.py`. Then in `booking_admin.py`'s `patch_settings`, ensure the field list passed to the repo no longer references `widget_color` (it iterates patch fields, so removing it from the model is sufficient — verify no hardcoded reference). **Do not** remove `widget_color` from the read/`TenantConfig`/public-config path — live widgets still read the stored value.

- [ ] **Step 4: Run → pass** — also run the full booking suite to confirm no regression: `python -m pytest tests -q -k booking`.

- [ ] **Step 5: Checkpoint.**

### 3B Remove widget color from the dashboard UI (frontend TDD)

- [ ] **Step 1: Write failing test** — `BookingSettingsForm.test.tsx`: render the form; assert no element with the label/text `Widget accent color` exists; assert the Email accent color (if rendered here) and other fields still exist. (Read the form for exact prop/draft shape to construct a minimal render.)

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** — delete the "Widget accent color" `<div>` block (the dual color picker + hex input, ~lines 161-182) from `BookingSettingsForm.tsx`, and remove `widget_color` from `SettingsPatch` in `api.ts` (keep it on the `BookingSettings` read interface so `getSettings` typing stays accurate). Remove any now-unused `widget_color` references in the form's `draft`/`set` calls.

- [ ] **Step 4: Run → pass** + `npm run typecheck`.

- [ ] **Step 5: Checkpoint.**

### 3C Rename Resources → Staff (UI relabel)

- [ ] **Step 1:** In `BookingsSection.tsx` `TABS`, change `{ key: "resources", label: "Resources" }` → `{ key: "resources", label: "Staff" }` (keep the `key` to avoid touching routing/state).
- [ ] **Step 2:** In `ResourcesManager.tsx` / `ResourceFormDrawer.tsx`, change visible headings/empty-states/buttons "Resource(s)" → "Staff"; default the `type` select to `staff`; keep room/equipment/generic as selectable options (de-emphasized, listed after staff). Capacity label → "How many can work in parallel" (optional clarity).
- [ ] **Step 3:** In `ServiceFormDrawer.tsx`, relabel "Assigned resources" → "Which staff can perform this service".
- [ ] **Step 4:** Add/extend a render test asserting the Staff tab label renders (in `BookingsSection.test.tsx` if present, else a small new test). Run frontend tests + typecheck.
- [ ] **Step 5: Checkpoint.**

### 3D Service↔staff eligibility enforcement (backend TDD — verify + lock in)

- [ ] **Step 1: Write failing/locking test** — `test_booking_service_staff_eligibility.py`: using the booking test fixtures, create a tenant with two staff resources A and B, a service linked **only** to A, then request availability / create a booking for that service and assert the assigned `resource_id` is always A and **never** B. (Read `_free_resource_for` in `booking.py` and the booking test helpers to construct the fixture; this test pins existing correct behavior so the relabel can't regress it.)

- [ ] **Step 2: Run → expected PASS** (behavior already exists). If it FAILS, fix `_free_resource_for` so it only considers linked resources.

- [ ] **Step 3: Checkpoint.**

---

## Task 4 — Booking: Customizable per-staff Overview

**Depends on:** Task 0, Task 3C (Staff terminology).
**Files:**
- Create: `frontend/src/components/dashboard/booking/overview/prefsStore.ts` (+ `.test.ts`)
- Create: `frontend/src/components/dashboard/booking/overview/widgetRegistry.tsx`
- Create: `frontend/src/components/dashboard/booking/overview/CustomizePanel.tsx`
- Create: `frontend/src/components/dashboard/booking/overview/CalendarWidget.tsx` (+ `.test.tsx`)
- Create: `frontend/src/components/dashboard/booking/overview/StaffScopeSelect.tsx`
- Create: `frontend/src/components/dashboard/booking/overview/ByStaffWidgets.tsx`
- Modify: `frontend/src/components/dashboard/booking/OverviewPanel.tsx` (consume registry + prefs + scope)
- Modify: `frontend/src/components/dashboard/booking/OverviewCharts.tsx` (export chart widgets so the registry can reuse them)
- Modify: `frontend/src/components/dashboard/booking/api.ts` (`getStats` accepts optional `resourceId`)
- Modify: `backend/auth_service/routers/booking_admin.py` (`/stats` accepts `resource_id`)
- Modify: `backend/auth_service/services/booking_repo.py` (stats query filters by resource_id; add by-staff aggregation)
- Test: `backend/auth_service/tests/test_booking_stats_by_staff.py`

### 4A Prefs store (localStorage, abstracted) — TDD

- [ ] **Step 1: Write failing test** — `prefsStore.test.ts`: a store with `getLayout()/setLayout()/getScope()/setScope()` persists to `localStorage` under a versioned key and returns defaults (Calendar + KPI enabled, scope `"all"`) when empty or corrupt.

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { createOverviewPrefs, DEFAULT_LAYOUT } from "./prefsStore";

beforeEach(() => localStorage.clear());

describe("overview prefs store", () => {
  it("returns defaults when empty", () => {
    const s = createOverviewPrefs("proj-1");
    expect(s.getLayout()).toEqual(DEFAULT_LAYOUT);
    expect(s.getScope()).toBe("all");
  });
  it("persists layout and scope", () => {
    const s = createOverviewPrefs("proj-1");
    s.setScope("staff-7");
    s.setLayout([{ id: "calendar", size: "lg", enabled: true }]);
    const s2 = createOverviewPrefs("proj-1");
    expect(s2.getScope()).toBe("staff-7");
    expect(s2.getLayout()[0].id).toBe("calendar");
  });
  it("survives corrupt storage", () => {
    localStorage.setItem("booking.overview.v1.proj-1", "not json");
    expect(createOverviewPrefs("proj-1").getLayout()).toEqual(DEFAULT_LAYOUT);
  });
});
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `prefsStore.ts`** — type `WidgetLayoutItem = { id: string; size: "sm"|"md"|"lg"; enabled: boolean }`; `DEFAULT_LAYOUT` lists all widget ids with `calendar` + `kpis` enabled by default and the rest disabled; `createOverviewPrefs(projectKey)` returns getters/setters reading/writing `booking.overview.v1.<projectKey>` with try/catch JSON. Keep it framework-free (no React) so it's unit-testable. Scope value is `"all"` or a `resource_id`.

- [ ] **Step 4: Run → pass.**
- [ ] **Step 5: Checkpoint.**

### 4B Widget registry + refactor existing charts

- [ ] **Step 1:** In `OverviewCharts.tsx`, ensure each chart (`BookingsOverTimeChart`, `ByServiceChart`, `ByStatusChart`, `PeakTimesHeatmap`) is individually exported (they likely already are). No behavior change.
- [ ] **Step 2: Implement `widgetRegistry.tsx`** — an array of entries:

```tsx
export type OverviewWidget = {
  id: string;
  title: string;
  defaultSize: "sm" | "md" | "lg";
  defaultEnabled: boolean;
  render: (ctx: OverviewWidgetCtx) => React.ReactNode;
};
export type OverviewWidgetCtx = {
  stats: BookingStats;
  appointments: BookingAppointment[]; // already scope-filtered by the panel
  services: BookingService[];
  staff: BookingResource[];
  scope: string; // "all" | resource_id
  slug: string;
  onSelectAppointment: (a: BookingAppointment) => void;
};
export const OVERVIEW_WIDGETS: OverviewWidget[] = [ /* kpis, calendar, bookingsOverTime, byService, byStatus, peakTimes, byStaff, apptCounts */ ];
```

Each entry's `render` delegates to the existing chart components / the new `CalendarWidget` / `ByStaffWidgets`. `DEFAULT_LAYOUT` in `prefsStore.ts` must be derived from / consistent with these ids (calendar + kpis enabled).

- [ ] **Step 3:** Add a registry test asserting `DEFAULT_LAYOUT` ids ⊆ `OVERVIEW_WIDGETS` ids and that `calendar` + `kpis` default-enabled.
- [ ] **Step 4: Run → pass.**
- [ ] **Step 5: Checkpoint.**

### 4C Calendar widget (TDD)

- [ ] **Step 1: Write failing test** — `CalendarWidget.test.tsx`: given two appointments on known dates within the current month, renders a month grid, shows event markers on those day cells, marks "today", and switching to "Day"/"Week" view changes the layout. Clicking an event calls `onSelectAppointment`.
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement `CalendarWidget.tsx`** — month/week/day toggle; build the month grid reusing date helpers from `@/lib/bookingDates` and patterns from `@/components/booking/MonthGrid`; place appointments into day buckets by `start_utc`; color events by `service` (use `service.color` when present); "today" cell uses `dashAccent.todayMarker`; events clickable → `onSelectAppointment`. Lightweight, no new dependency.
- [ ] **Step 4: Run → pass** + typecheck.
- [ ] **Step 5: Checkpoint.**

### 4D Per-staff scope + backend stats filter (TDD)

- [ ] **Step 1: Backend failing test** — `test_booking_stats_by_staff.py`: seed bookings across two staff; `GET /stats?resource_id=<A>` returns KPIs counting only A's bookings; response includes a `by_staff` array `[{ resource_id, resource_name, count }]` for the unfiltered call. (Read `get_stats` in `booking_admin.py` + the stats builder in `booking_repo.py`.)
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement backend** — add optional `resource_id` query param to `/stats`; thread it into the repo stats query as an extra `WHERE resource_id = ...` filter; add a `by_staff` aggregation (group bookings by `resource_id`, join `booking_resources.name`). Extend the `BookingStats` Pydantic response model with `by_staff: list[...]`.
- [ ] **Step 4: Run → pass.**
- [ ] **Step 5: Frontend** — `getStats(slug, from?, to?, resourceId?)` adds `resource_id` to the query; extend the `BookingStats` TS interface with `by_staff`. `StaffScopeSelect.tsx` renders an "All staff" + per-staff dropdown from active staff resources, value bound to the prefs store. `OverviewPanel.tsx`: on scope change, refetch stats with `resourceId` and filter `appointments` by `resource_id` before passing to widgets; persist scope via the store.
- [ ] **Step 6:** `ByStaffWidgets.tsx` — a bar chart of `by_staff` counts (recharts) + a compact per-staff KPI list; hidden/disabled when only one staff exists.
- [ ] **Step 7: Run → pass** (backend + frontend) + typecheck.
- [ ] **Step 8: Checkpoint.**

### 4E Customize panel + assemble OverviewPanel

- [ ] **Step 1:** `CustomizePanel.tsx` — a popover/sheet listing all `OVERVIEW_WIDGETS` with enable toggles and drag-to-reorder via `@dnd-kit/core`; writes through `setLayout`. Animate open/close with `motion`.
- [ ] **Step 2:** `OverviewPanel.tsx` — read layout + scope from the store; render `StaffScopeSelect` + a "Customize" button + the enabled widgets in layout order, each in a sized card; defaults (Calendar + KPI) show on first load. Keep KPI cards + existing charts working.
- [ ] **Step 3:** Add a panel test: with default prefs, Calendar + KPI render; toggling a widget off in the panel removes it and persists (re-mount shows it still off).
- [ ] **Step 4: Run → pass** + typecheck + `npm run build`.
- [ ] **Step 5: Checkpoint.**

---

## Task 5 — Booking: Email preview mobile full-screen sheet

**Files:**
- Modify: `frontend/src/components/dashboard/booking/EmailTemplateEditor.tsx`
- Test: `frontend/src/components/dashboard/booking/EmailTemplateEditor.test.tsx`

- [ ] **Step 1: Write failing test** — render the editor (mobile-ish; the toggle is `lg:hidden`); click "Show preview"; assert a dialog/sheet with `role="dialog"` containing the preview renders, and a "Done"/close control closes it. (Mock `EmailPreviewFrame`/fetch as needed.)
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** — replace the current mobile "below the editor" behavior: keep the desktop split-view (`lg:grid-cols-2`) untouched. On mobile, the "Show preview" button opens an `AnimatePresence` full-screen sheet (`motion/react`, `m.div` fixed inset-0, slide-up + cross-fade, `role="dialog"`, `aria-modal`), rendering `EmailPreviewFrame` with a header "Preview" + Done button. Respect `useReducedMotion`. The desktop preview column stays `hidden lg:block` (no longer toggled by `showPreview`); `showPreview` now drives only the mobile sheet.
- [ ] **Step 4: Run → pass** + typecheck.
- [ ] **Step 5: Checkpoint.**

---

## Task 6 — Booking: Hide mobile tab scrollbar

**Files:**
- Modify: `frontend/src/components/dashboard/booking/BookingsSection.tsx`

- [ ] **Step 1:** Change the tab `<nav>` className from `mb-6 flex gap-1 overflow-x-auto border-b ...` to `no-scrollbar mb-6 flex gap-1 overflow-x-auto overflow-y-hidden border-b ...` (matching `SectionRail`/`PageTabs`).
- [ ] **Step 2:** `npm run typecheck` + run booking frontend tests to confirm no regression.
- [ ] **Step 3: Checkpoint.**

---

## Task 7 — Booking decoupling: Shared Booking Client SDK

**Files:**
- Create: `frontend/src/lib/booking-client/index.ts` (framework-agnostic; no React)
- Create: `frontend/src/lib/booking-client/index.test.ts`
- Create: `frontend/src/lib/booking-client/contract.ts` (the versioned contract shape + validator)
- Modify: `backend/auth_service/routers/booking.py` (add `GET /{slug}/contract`; harden `CreateIn` validation → field-level errors)
- Modify: `backend/auth_service/models/booking_admin_schemas.py` or a new `booking_contract.py` (machine-readable contract constant)
- Test: `backend/auth_service/tests/test_booking_contract.py`
- Modify: `agents/CMS Connector - Website/prompts.py` (emit a `booking.field_mapping`)
- Modify: `agents/CMS Connector - Website/output_writer.py` (write contract version + field mapping into `cms.config.json`; fail if a required field is unmapped)
- Test: `agents/CMS Connector - Website/tests/test_output_writer_booking_contract.py`

### 7A Backend: machine-readable contract + field-level errors (TDD)

- [ ] **Step 1: Write failing test** — `test_booking_contract.py`:
  - `GET /booking/{slug}/contract` → 200 with `{ version, required: [...], fields: { service_id: {type}, start_utc: {type, format}, "customer.name": {...}, "customer.email": {...}, ... } }`.
  - `POST /booking/{slug}` with a missing `customer.email` → 422 whose body identifies the offending field (e.g. `detail` lists `customer.email`).
  - A valid payload still succeeds (behavior preserved).
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** — define a `BOOKING_CONTRACT` constant (version string + required field list + per-field type/format), serve it from a new `GET /{slug}/contract` route (slug validated like the other public routes). Harden `CreateIn` so validation errors name the field: keep the existing email regex + required-name + ISO-datetime checks, but raise `HTTPException(422, detail={"field": ..., "message": ...})` (or return FastAPI's field-path errors) instead of a generic message. Keep the honeypot behavior unchanged. **Bump no behavior for already-valid payloads.**
- [ ] **Step 4: Run → pass** (+ full public booking suite `-k booking`).
- [ ] **Step 5: Checkpoint.**

### 7B `booking-client` SDK (TDD)

- [ ] **Step 1: Write failing test** — `index.test.ts`:

```ts
import { describe, it, expect, vi } from "vitest";
import { createBookingClient } from "./index";

const cfg = { apiBase: "https://api.example.com/booking", slug: "acme" };

describe("booking-client", () => {
  it("rejects an incomplete payload before sending", async () => {
    const fetchMock = vi.fn();
    const c = createBookingClient({ ...cfg, fetch: fetchMock });
    await expect(c.createBooking({ service_id: "s1", start_utc: "2026-07-01T10:00:00Z",
      customer: { name: "", email: "bad" } } as never))
      .rejects.toThrow(/name|email/i);
    expect(fetchMock).not.toHaveBeenCalled(); // never hits the network when invalid
  });
  it("normalizes and routes a valid payload to the right slug", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: "b1" }) });
    const c = createBookingClient({ ...cfg, fetch: fetchMock });
    const res = await c.createBooking({ service_id: "s1", start_utc: "2026-07-01T10:00:00Z",
      customer: { name: " Jane ", email: "jane@x.com" } });
    expect(res.id).toBe("b1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://api.example.com/booking/acme");
    expect(JSON.parse(init.body).customer.name).toBe("Jane"); // trimmed/normalized
  });
});
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement `contract.ts` + `index.ts`** — `contract.ts` mirrors the backend `BOOKING_CONTRACT` (version + required fields + validators: non-empty name, email regex, ISO datetime, present service_id). `createBookingClient({ apiBase, slug, fetch? })` returns `{ createBooking, getConfig, getServices, getAvailability }`; `createBooking` validates+normalizes (trim strings, default optional fields) against the contract, throws a descriptive `Error` listing bad fields **before** any network call, then `POST`s to `${apiBase}/${slug}`. Zero React/DOM-specific imports; `fetch` injectable for tests. Add a top-of-file comment that this file is copied verbatim into client repos by the connector.
- [ ] **Step 4: Run → pass** + typecheck.
- [ ] **Step 5: Checkpoint.**

### 7C Connector enforcement (TDD)

- [ ] **Step 1: Write failing test** — `tests/test_output_writer_booking_contract.py` (mirror existing `test_output_writer_booking.py` style): given a detected booking block with a `field_mapping` covering all required contract fields, `output_writer` writes `cms.config.json` containing `booking.contractVersion` + `booking.fieldMapping`; given a mapping **missing** a required field (e.g. `customer.email`), the writer **raises/returns an error** (test matrix fails).
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** —
  - `prompts.py`: extend the booking detection schema to also emit `field_mapping` (client-form field → contract field) and instruct the model to map every required contract field.
  - `output_writer.py`: when writing the booking block, include `contractVersion` (import/duplicate the contract version constant) + `fieldMapping`; before writing, assert every required contract field is present in the mapping, else raise a clear error so the provisioning test matrix fails.
- [ ] **Step 4: Run → pass** — `python -m pytest tests -q` in the connector dir.
- [ ] **Step 5: Checkpoint.**

---

## Task 8 — Integration verification + Playwright user-stories

**Files:**
- Create: `frontend/tests/e2e/` user-story specs as the repo's Playwright convention dictates (check for existing e2e config; if Playwright isn't wired for the dashboard, write component-level integration tests instead and note the gap).

- [ ] **Step 1: Full backend suite** — `cd backend/auth_service && python -m pytest tests -q`. Expected: all green (≥ prior count + new tests).
- [ ] **Step 2: Full connector suite** — `python -m pytest tests -q` in `agents/CMS Connector - Website/`. Expected: green.
- [ ] **Step 3: Full frontend suite + build** — `cd frontend && npm run test && npm run typecheck && npm run build`. Expected: green.
- [ ] **Step 4: User-story coverage** — add/verify e2e (or integration) stories: (a) add a lead manually → it appears with the right Product badge; (b) Overview: select a staff member → calendar + stats scope to them, reload → scope persists; (c) Emails on mobile: tap Show preview → full-screen sheet appears without scrolling. Use the `playwright-user-stories` skill if Playwright is configured.
- [ ] **Step 5: Final checkpoint** — summarize results; await commit approval.

---

## Self-review notes (author)

- **Spec coverage:** §0→T0; §1→T1; §2→T2; §3.1→T3A/3B; §3.2→T3C; §3.3→T3D; §4.1→T4B; §4.2 calendar/by-staff→T4C/T4D; §4.3 scope+persistence→T4A/T4D; §5→T5; §6→T6; §7.1→T7A; §7.2→T7B; §7.3→T7C; §8→T8. All covered.
- **Type consistency:** `LEAD_TYPE_BADGE_CN`, `dashAccent`, `WidgetLayoutItem`/`DEFAULT_LAYOUT`, `OverviewWidget`/`OverviewWidgetCtx`, `BOOKING_CONTRACT`, `createBookingClient` used consistently across tasks.
- **No-migration invariant:** confirmed — `lead_type` (default `'website'`) and all booking tables already exist; `widget_color` column retained.
- **Commit policy:** checkpoints stage only; no `git commit` without explicit user approval (project rule overrides skill default).
