# Phase 8 — Verify & learn

**No skill.** Runs commands + records lessons.

**Do:**
- `npm run build` — must exit 0 (no TypeScript or build errors).
- Optionally `npx unlighthouse-ci --site http://127.0.0.1:3000`; note scores in `BUILD_PLAN.md`.
- Final grep gates: zero `framer-motion`, zero `next-i18next`/`react-i18next`, zero raw `<img `
  outside `app/opengraph-image.tsx` / `app/og/`.
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

**Report to the user:** output folder path, what was built, locales scaffolded, test results, what's mock vs real, any silent judgment calls. Note whether `NEXT_PUBLIC_CMS_ENDPOINT` is set (messages live from CMS) or unset (seed files active).
