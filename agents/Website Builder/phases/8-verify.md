# Phase 8 — Verify & learn

**No skill.** Runs commands + records lessons.

**Do:**
- `npm run build` (vite-react-ssg) — must exit 0 (no TypeScript or build errors).
- Optionally `npx unlighthouse-ci --site http://127.0.0.1:5173`; note scores in `BUILD_PLAN.md`.
- Final grep gates:
  - FAIL (must return zero matches): `framer-motion`, `next-intl`, `generateMetadata`,
    `app/[locale]`, `next/image`, `NEXT_PUBLIC_`, `react-markdown`, and `dangerouslySetInnerHTML`
    outside the JSON-LD `<script>`.
  - REQUIRE (must return at least one match each): `react-i18next`, `vite-react-ssg`,
    `VITE_CMS_ENDPOINT`, `cms-rich-text` (an import of the vendored kit), `--cms-rich-strong`
    defined in the site CSS, `<ThemeStyles`, and `var(--cms-font-body` in the site CSS; plus
    `<CmsIcon` when `_design-manifest.json` (or the connector report) lists content icons.
  - Zero raw `<img ` outside `src/seo/og.gen.ts` / `public/og/` (OG generation; raw `<img>` is
    correct there — do not flag it) and the vendored `src/lib/cms-rich-text/` (`CmsIcon`'s
    `original` mode).
  - Every image and content icon has a CMS field behind it: no `/images/…` path and no content icon
    (`lucide-react` or inline `<svg>` on services, features, items or contact methods) rendered
    outside a resolver fallback / `<CmsIcon fallback>`. Only favicon/OG assets and UI-control icons
    (menu, close, chevrons, arrows, spinners, form affordances) stay in code; do not flag them.
- Playwright check: a `.cms-rich` element on a CMS-driven page renders with the themed `strong`
  colour (`getComputedStyle(strong).color` equals the surface's `--cms-rich-strong`, not the
  browser default), and no literal tags or `&amp;` are visible.
- Playwright checks for theme, images and icons (ADR-0011), against the draft with
  `VITE_CMS_PREVIEW_TOKEN` (restore every original afterwards; once the connector has run, its
  5i probe repeats them): swap an image in draft → preview shows the new URL; set an icon (Lucide
  pick) with a colour → preview shows a `.cms-icon` with that `background-color`; set `body_font`
  to a different Google font → computed `font-family` of `body` starts with it; save a title with a
  span colour → rendered span has that colour; empty image/icon → fallback renders, no layout gap.
  Before the site is connected, check the last one only (no theme → `@fontsource` fonts, mock
  images and designed icons render).
- If a build/test failure is hard to diagnose and `superpowers` is installed, use its debugging
  methodology (root-cause-first).
- Append at least one generalizable lesson to `agents/Website Builder/LEARNINGS.md`. If the
  lesson should apply to every future build, also append it to
  `agents/Website Builder/learnings-template/conventions.md`.

**Motion & performance checklist** (see the "Motion & Performance Standards" in `learnings-template/conventions.md`):
- [ ] Single animation library (`motion/react`); zero `framer-motion` imports (covered by the grep gate above).
- [ ] One app-level `LazyMotion` + `MotionConfig reducedMotion="user"`; no `m` component renders outside it.
- [ ] A page-load / navigation spinner exists and triggers on route change (min-display, no flash).
- [ ] Entrance motion is restrained: 16–40px travel, 0.3–0.6s, fires once, 1–2 elements per view; page transition is opacity-only (and stays opacity-only if any sticky/fixed scroll scene exists).
- [ ] Heavy/3D modules are `ssr:false` + skeleton + mobile fallback; render loops are viewport-aware / on-demand.
- [ ] Reduced-motion verified; build + tests green.

**Report to the user:** output folder path, what was built, locales scaffolded, test results, what's mock vs real, any silent judgment calls. Note whether `VITE_CMS_ENDPOINT` is set (messages live from CMS) or unset (seed files active).
