# Project View — Section Navigation Redesign

**Date:** 2026-06-05
**Status:** Approved (design), pending implementation plan
**Area:** `frontend/src/app/dashboard/[projectSlug]/` + `frontend/src/components/dashboard/`

## Goal

Replace the single long-scroll project view with a clearly separated, switchable
section layout. A client opening a project should immediately understand *where*
each kind of work happens — view analytics, edit content, request automatic fixes,
manage settings — instead of scrolling past everything stacked vertically.

The top of the page (Preview/Publish bar, breadcrumb, project name, live-website
card) is **unchanged**. Everything currently below it (CMS grid, issues, settings)
moves into a sidebar-driven section shell.

## Current state

`frontend/src/app/dashboard/[projectSlug]/page.tsx` renders, top to bottom, in one
scroll:

1. `PreviewPublishBar` — sticky preview/publish controls.
2. Breadcrumb + project name + subtitle + animated live-website card.
3. `ServiceGrid` — the CMS area: `PageTabs` (About/Contact/Footer/Home/General,
   animated sliding underline via `layoutId="page-tabs-underline"`) + service cards.
   Content swaps with `AnimatePresence mode="wait"`, `opacity 0→1`, `y 6→0`, 180ms,
   ease `[0.32, 0.72, 0, 1]`.
4. `IssueForm` + `IssueList` — the issue/"agentic solver" area.
5. Admin-only project settings form (website URL + allowed origins).

All of this is currently inlined in `page.tsx` (419 lines), which is doing too much.

## Target design

A two-column **section shell** sits below the live-website card:

- **Left:** a sticky vertical **sidebar rail** listing the sections.
- **Right:** a content panel rendering only the active section, with the existing
  fade-in/out transition between sections.

### Sections (rail order, top → bottom)

| Order | Icon (lucide) | Label | `view` key | Contents | Visibility |
|-------|---------------|-------|------------|----------|------------|
| 1 | `LayoutDashboard` | **Dashboard** | `dashboard` | Polished "Coming soon" analytics empty state (Vercel analytics later) + a "Go to CMS" shortcut button | All users |
| 2 | `Pencil` (or `FileText`) | **CMS** | `cms` | Existing `ServiceGrid` (page tabs + service cards), relocated verbatim, including its loading skeleton + error message | All users |
| 3 | `Sparkles` (or `Wand2`) | **Auto-Fix** | `autofix` | `IssueForm` (top) + `IssueList` (below), relocated verbatim. Section header explains: describe a problem, an agent fixes it automatically | All users |
| 4 | `Settings` | **Settings** | `settings` | Admin-only website URL + allowed-origins form, relocated verbatim | Admin only |

The **default** active section is `dashboard` (the landing view). Because its
analytics are not built yet, its empty state must be welcoming, not a dead end —
it includes a short explanation and a primary "Go to CMS" action.

## Component architecture

Goal: shrink `page.tsx` from a 419-line god component into a thin orchestrator,
and isolate each concern into a focused, independently-understandable unit.

### New components (all under `frontend/src/components/dashboard/`)

- **`SectionRail.tsx`** — the sidebar navigation.
  - Props: `{ sections: SectionDef[]; activeView: string; onSelect: (view: string) => void }`
  - `SectionDef = { key: string; label: string; icon: LucideIcon; adminBadge?: boolean }`
  - Renders a vertical list of buttons. The active item shows a filled "pill"
    background driven by a shared `layoutId="section-rail-active"` so it slides
    between items with the same spring as `PageTabs`
    (`type: "spring", stiffness: 480, damping: 36, mass: 0.6`).
  - `role="tablist"` with `aria-orientation="vertical"`; each button
    `role="tab"`, `aria-selected`, roving `tabIndex`, arrow-key (Up/Down) navigation.
  - Responsive: below `md`, the same component renders as a horizontal,
    horizontally-scrollable strip (`flex-row overflow-x-auto`) above the panel;
    the active-pill `layoutId` animation still applies.

- **`SectionPanel.tsx`** — wraps the active section's content in the section-swap
  animation so every section transitions identically.
  - Props: `{ activeView: string; children: ReactNode }` (children keyed by caller),
    or it accepts a `view` key and a render map. Implementation detail for the plan;
    interface must let `page.tsx` pass already-built section bodies.
  - `AnimatePresence mode="wait" initial={false}`, `motion.div` keyed on `activeView`,
    `initial={{ opacity: 0, y: 6 }}`, `animate={{ opacity: 1, y: 0 }}`,
    `exit={{ opacity: 0, y: -6 }}`, `transition={{ duration: 0.18, ease: [0.32, 0.72, 0, 1] }}`.
    (Identical to `ServiceGrid`'s existing swap.)

- **`DashboardSection.tsx`** — the "coming soon" analytics empty state.
  - Props: `{ onGoToCms: () => void }`.
  - Centered card: icon, "Coming soon" badge, "Website analytics" heading, one
    explanatory sentence, and a primary "Go to CMS" button wired to `onGoToCms`.

- **`AutoFixSection.tsx`** — thin wrapper composing `IssueForm` + `IssueList` with
  a short section header ("Describe a problem and our agent fixes it automatically").
  - Props mirror what the two children already need:
    `{ projectSlug, refreshTrigger, onSubmitted, isAdmin, currentUserId }`.

- **`ProjectSettingsSection.tsx`** — the admin settings form extracted from
  `page.tsx` (website URL + allowed origins + save handler + cache writeback).
  - Props: `{ projectSlug: string }`. Owns its own `useQuery`/draft/save state that
    currently lives inline in `page.tsx`.

### `useProjectView` hook (URL state)

`frontend/src/components/dashboard/hooks/useProjectView.ts` (or inline in `page.tsx`
if small) — manages the active section via the URL query param `?view=`, mirroring
the existing `?tab=` pattern in `ServiceGrid`:

- Reads `searchParams.get("view")`; falls back to `"dashboard"` when missing/invalid.
- `setView(view)` does `router.replace(`${pathname}?${params}`, { scroll: false })`,
  preserving the existing `tab` param so a deep link like `?view=cms&tab=Contact` works.
- Admin gating: if a non-admin lands on `?view=settings`, fall back to `dashboard`.

### `page.tsx` after refactor

Becomes an orchestrator: fetch project/services, render the unchanged top
(PreviewPublishBar + breadcrumb + name + live card), then render
`<SectionRail>` + `<SectionPanel>` with the four section bodies. The settings
state/handlers, issue-refresh state, and service-removal handler move into the
relevant section components (settings → `ProjectSettingsSection`; issue refresh →
`AutoFixSection`; service removal stays near `ServiceGrid`/CMS section).

## Navigation state & data flow

- Single source of truth for "which section": URL `?view=` param.
- `?tab=` continues to drive the CMS page tabs **inside** the CMS section,
  untouched.
- Switching sections never refetches services/issues/settings — each child keeps
  its own cached `useQuery`, so section switches are instant.
- The "Go to CMS" button in `DashboardSection` calls `setView("cms")`.

## Motion specification

| Element | Animation | Values |
|---------|-----------|--------|
| Section content swap | fade + lift | `AnimatePresence mode="wait"`, opacity 0→1, y 6→0 (enter) / -6 (exit), 180ms, ease `[0.32,0.72,0,1]` |
| Rail active pill | spring slide | shared `layoutId="section-rail-active"`, `spring` stiffness 480 / damping 36 / mass 0.6 |
| Rail item hover/focus | color transition | `transition-colors duration-150`, focus ring `focus-visible:ring-2 ring-zinc-400/40` |

All motion respects `prefers-reduced-motion` (Framer honors it via reduced-motion;
where we add custom variants, guard with the existing project convention).
Library/import stays `framer-motion` (project convention; not `motion/react`).

## Styling

Reuse existing tokens from `frontend/src/lib/styles.ts` (`dashboardSectionCardCn`,
`dashboardPrimaryBtnCn`, `dashboardInputCn`, `dashboardFieldLabelCn`,
`dashboardErrorBannerCn`) and the zinc + emerald palette. Rail pill uses zinc
surfaces (`bg-zinc-100 dark:bg-zinc-800` active) consistent with the rest of the
dashboard. No new color system. A UI/UX polish pass (spacing, hierarchy,
interaction states) runs via the `ui-ux-pro-max` skill during implementation.

## Responsive behavior

- `md` and up: sidebar rail (fixed width ~`14rem`/`w-56`) left, panel right,
  rail `sticky top-*` so it stays visible while the panel scrolls.
- below `md`: rail becomes a horizontal scrollable strip above the panel; panel
  full width. Active-pill animation preserved.

## Accessibility

- Rail = `role="tablist"` (`aria-orientation` vertical/horizontal per breakpoint);
  items `role="tab"` + `aria-selected` + roving `tabIndex`; panel `role="tabpanel"`
  with `aria-labelledby` tying it to the active tab.
- Arrow keys move between tabs; Enter/Space activate; visible focus rings.
- Settings tab is omitted from the DOM for non-admins (not just hidden).

## Out of scope

- The actual Vercel analytics integration — Dashboard ships as the "coming soon"
  empty state only. (Future spec.)
- Any change to `PreviewPublishBar`, the live-website card, `IssueForm`,
  `IssueList`, `ServiceGrid`, `PageTabs`, or `ServiceCard` internals. They are
  relocated/wrapped, not rewritten.
- Backend, routing, or data-model changes. This is a frontend-only restructure.

## Testing

- Component tests for `SectionRail`: renders all sections, hides Settings for
  non-admins, calls `onSelect` with the right key, keyboard navigation moves focus.
- `useProjectView` / URL behavior: default is `dashboard`, invalid/`settings`
  (non-admin) falls back to `dashboard`, `setView` preserves `tab`.
- Smoke: each section renders its expected child (Dashboard empty state, CMS grid,
  Auto-Fix form+list, Settings form) and section switches animate without overlap.
- Existing CMS/issue/settings behavior is unchanged (regression check).

## File-level change summary

**New:**
- `components/dashboard/SectionRail.tsx`
- `components/dashboard/SectionPanel.tsx`
- `components/dashboard/DashboardSection.tsx`
- `components/dashboard/AutoFixSection.tsx`
- `components/dashboard/ProjectSettingsSection.tsx`
- `components/dashboard/hooks/useProjectView.ts` (or inline)
- Test files for the above.

**Modified:**
- `app/dashboard/[projectSlug]/page.tsx` — slimmed to orchestrator; settings/issue
  state extracted into sections; renders rail + panel.

**Unchanged:** `PreviewPublishBar`, live-website card markup, `ServiceGrid`,
`PageTabs`, `ServiceCard`, `IssueForm`, `IssueList`, `styles.ts`.
