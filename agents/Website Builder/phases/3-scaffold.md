# Phase 3 — Scaffold

**Apply skills:** `nextjs-app-scaffolding` + `i18n-setup`.

**Do:**
- `cd` to the parent scratch directory FIRST, then `npx create-next-app@latest <folder>` with
  the flags in the scaffolding skill.
- Install Motion, next-intl, lucide-react, shadcn/ui, Playwright (per the skill).
- Wire next-intl: `i18n/routing.ts`, `request.ts`, `navigation.ts`, `middleware.ts`,
  `createNextIntlPlugin` in `next.config.ts`, messages files (`[XX]` placeholders for
  non-default locales).
- Set fonts via `next/font` in `app/[locale]/layout.tsx`.
- Create the canonical folder structure.
- Copy the design's mock images to `public/images/<section>/<filename>`.
- Copy `agents/Website Builder/learnings-template/*` into the new project's `.learnings/`.
- If `ui-ux-pro-max` is installed, run its design-system generator and reconcile with the
  manifest tokens — the design wins on direct conflicts; ui-ux-pro-max fills gaps.

**Gate:** `npm run dev` boots; `/` redirects to `/<default-locale>`; `.learnings/` has all
three template files; mock images are in place.

**Token tactics:** don't echo full create-next-app output; summarize success/failure.
