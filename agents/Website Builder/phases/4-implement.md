# Phase 4 — Implement

**Apply skill:** `motion-animations` (motion/react only). Use external `frontend-design` and
`ui-ux-pro-max` if present (Glob to check); else use the aesthetic fallback in AGENTS.md.

**Do, per section in `BUILD_PLAN.md`:**
- Build `components/sections/<name>.tsx`.
- Apply aesthetic direction (frontend-design) + section-type UX rules (ui-ux-pro-max).
- Add shadcn components via `shadcn/skills` if present, else `npx shadcn@latest add <c>`.
- Wire Motion via `components/motion/` wrappers — `motion/react` import only.
- All UI strings via next-intl `useTranslations()` / `getTranslations()` — never hardcoded.
- Mobile-first Tailwind (default = mobile; `md:`/`lg:`/`xl:` upscale).

**Gate:** Check off a `BUILD_PLAN.md` item ONLY after the section renders correctly for ALL
locales. Run the motion-animations grep: zero `framer-motion` matches.
