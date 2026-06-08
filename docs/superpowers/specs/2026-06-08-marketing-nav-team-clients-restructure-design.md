# Marketing nav restructure + Team, About, Clients pages

**Date:** 2026-06-08
**Status:** Approved (design) — pending implementation plan
**Scope:** `frontend/` marketing routes only. No backend, i18n, booking, or auth changes.

## Overview

Restructure the marketing site's top navigation and redistribute content across
pages:

- **Nav:** remove `Projects`, add `Team` and `Clients`. Final order:
  `About · Clients · Team · Contact`. Applies to desktop bar **and** mobile drawer
  (both already map over the single `NAV_LINKS` source).
- **Team page (new `/team`):** the team section (moved off the About page) plus a
  new framer-animated **Values** section.
- **About page:** drop the team section and the existing values grid; replace with
  the home page's **"What do we do"** block, rendered full-width.
- **Clients page (new `/clients`):** the projects showcase as an enhanced,
  filterable **card grid** (search by name, detailed cards with key info).
- **Home page:** unchanged visually. The "What do we do" block is extracted into a
  reusable component first; home keeps its current combined section.

## Decisions (resolved during brainstorming)

1. **About values grid → removed.** Values now live only on the Team page (a new,
   distinct set). The orphaned `values` data + types are cleaned up.
2. **Nav order:** `About · Clients · Team · Contact` (user-specified).
3. **Home combined section:** kept unchanged; reusable sub-components are extracted
   so About/Clients consume shared pieces instead of duplicating markup.
4. **Clients layout:** filterable card grid (not a carousel).

## Architecture / approach

Reuse by **extraction**, not duplication. The "What do we do" block is pulled into
a shared component with a `layout` prop so home stays pixel-identical while About
gets a full-width variant. The Clients grid and the home carousel both read the
same `content/projects.ts` data (shared data is the reuse point).

Theme is preserved throughout: dark surfaces (`bg-black` / `#0e0e10`), gold accent
(`#c9a961` / `text-accent`), `font-display`, `border-border`, `rounded-2xl`, the
gold radial-glow motif, and the shared `Reveal` / `REVEAL_EASE` motion primitives
under `MotionConfig reducedMotion="user"`.

## File-by-file changes

### Modified

- **`src/lib/nav-links.ts`** — replace `NAV_LINKS` with:
  ```ts
  export const NAV_LINKS = [
    { label: "About", href: "/about" },
    { label: "Clients", href: "/clients" },
    { label: "Team", href: "/team" },
    { label: "Contact", href: "/contact" },
  ] as const;
  ```
  No edits needed in `Header.tsx` or `HeaderRightCluster.tsx` — both iterate
  `NAV_LINKS`.

- **`src/components/work/WorkSection.tsx`** — move `SERVICES` into the new
  `WhatWeDo` component; render `<WhatWeDo layout="split" />` in the left column
  (markup must reproduce the current left column exactly) beside the existing
  `<ProjectsCarousel />`. Home output stays identical. Keeps `id="projects"` anchor.

- **`src/app/(marketing)/about/page.tsx`** — compose `AboutStory` (story only) +
  `WhatWeDo` (full layout). Remove `TeamSection` import/usage and the `values`
  prop.

- **`src/components/about/AboutStory.tsx`** — drop the `values` prop and the
  values-grid markup; render the story block only.

- **`src/content/about.ts`** — remove the `values` field and the `Value` interface
  from `AboutContent` (orphaned once AboutStory stops rendering them).

- **`src/content/about.json`** — remove the `values` array (orphaned data).

### New

- **`src/components/work/WhatWeDo.tsx`** — owns the `SERVICES` const; prop
  `layout: "split" | "full"`.
  - `"split"`: reproduces the current home left column (eyebrow "What we build",
    heading "What do we do?", lead, vertical service list with icon pills + staggered
    `Reveal`s). Drop-in so home is unchanged.
  - `"full"`: full-width — centered heading/lead + a responsive multi-column grid
    (1 / 2 / 4) of the four service cards, with extended staggered reveals and hover
    states. Used on About.

- **`src/components/team/ValuesSection.tsx`** — new framer-animated values block.
  Four values as a typed local const (mirrors how `WorkSection` keeps `SERVICES`
  locally). Each: icon (lucide), title, description. Staggered card entrance via
  `Reveal`, icon pop on enter, hover lift; gold-glow background motif.

  | Order | Title | Icon | Description (draft) |
  |---|---|---|---|
  | 1 | Client comes first | `HeartHandshake` | We start from your goals, not our stack. Every decision is measured by what moves your business forward. |
  | 2 | Teamwork | `Users` | Engineering, security and strategy work as one team, so nothing falls between the cracks. |
  | 3 | Ownership | `KeyRound` | You own everything we build — code, data and roadmap. No lock-in, no black boxes. |
  | 4 | Transparency | `Eye` | Clear quotes, honest timelines, and a human who answers. You always know where things stand. |

- **`src/components/work/ProjectsGrid.tsx`** — client component for the Clients
  page. Search box filters `projects` by name (`useState`, case-insensitive
  substring on `name` + `short`). Responsive card grid (1 / 2 / 3 cols). Each card:
  screenshot, name, tagline, the `keyInfo` rows (Type / Stack / Focus — currently
  in data but never rendered), and the live-site "open" link (reusing the gold
  `ArrowUpRight` button style from the carousel). Empty-state line when no match.
  Cards stagger in; `AnimatePresence` + layout animation re-flows on filter change.

- **`src/app/(marketing)/team/page.tsx`** — `Metadata` + composition: small hero
  (eyebrow/title/lead, gold glow, Contact-page hero pattern) → `TeamSection` (reads
  `about.team`) → `ValuesSection`.

- **`src/app/(marketing)/clients/page.tsx`** — `Metadata` + small hero →
  `ProjectsGrid`.

### Not moved (surgical)

`TeamSection.tsx` and `TeamMemberCard.tsx` stay in `components/about/` and are
imported by `/team`. A folder move to `components/team/` is optional cleanup,
skipped to minimize churn.

## Hero copy (draft — editable)

- **Team** — eyebrow "Our team"; title "A small, senior team that ships.";
  lead "The people behind every build — engineering, security and strategy under
  one roof, and the principles that guide how we work."
- **Clients** — eyebrow "Our work"; title "Built for ambitious companies.";
  lead "A selection of websites, applications and AI workflows we've designed,
  built and now keep running for clients across the EU."

## Styling

Run **ui-ux-pro-max** during implementation to keep `ValuesSection`, full-layout
`WhatWeDo`, and `ProjectsGrid` on-theme (dark + gold, spacing, typography, motion
polish) and consistent with existing sections.

## Animations (Motion / `motion/react`)

- Reuse `Reveal` + `REVEAL_EASE` for all entrances; wrap in
  `MotionConfig reducedMotion="user"`.
- `ValuesSection`: staggered card entrance, icon pop, hover lift.
- `WhatWeDo` full: per-card staggered reveal + hover.
- `ProjectsGrid`: staggered entrance + smooth filter layout transitions.

## Testing

Follow existing component-test patterns (Vitest + Testing Library):

- `ValuesSection` — renders all four values + descriptions.
- `WhatWeDo` — both layouts render the four services; `full` renders grid markup.
- `ProjectsGrid` — typing in the search filters the rendered cards; empty state
  shows when nothing matches; key-info rows render.
- Sanity: `/team` and `/clients` routes render their sections; nav exposes the four
  new links (desktop + mobile).

## Out of scope

Home page visuals, backend, i18n, booking, auth, Footer. No folder moves. No
changes to project/team data beyond removing the orphaned About `values`.
