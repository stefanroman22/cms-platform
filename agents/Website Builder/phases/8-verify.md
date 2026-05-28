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

**Report to the user:** output folder path, what was built, locales scaffolded (which still need
translation), test results, what's mock vs real, any silent judgment calls.
