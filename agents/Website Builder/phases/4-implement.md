# Phase 4 — Implement

**Apply skill:** `motion-animations` (motion/react only). Use external `frontend-design` and
`ui-ux-pro-max` if present (Glob to check); else use the aesthetic fallback in AGENTS.md.

**Do, per section in `BUILD_PLAN.md`:**
- Build `components/sections/<name>.tsx`.
- Apply aesthetic direction (frontend-design) + section-type UX rules (ui-ux-pro-max).
- Add shadcn components via `shadcn/skills` if present, else `npx shadcn@latest add <c>`.
- Wire Motion via `components/motion/` wrappers — `motion/react` import only. Follow the
  "Motion & Performance Standards" in `learnings-template/conventions.md`: one shared token set,
  one app-level `LazyMotion` + `reducedMotion="user"`, restrained scroll reveals (1–2 per view),
  opacity-only page transitions, a branded nav spinner, on-demand 3D, and server-first data.
  For the concrete component shapes (provider stack order, the delegated-click page-change
  spinner + pure `shouldTriggerRouteLoad`, header container-stagger that does NOT wrap the
  right cluster, per-word hero `TextReveal` + multi-beat choreography, the GRID = one
  container-stagger rule, the `first:pl-0` underline gotcha, 3D dual-trigger mount +
  `frameloop="demand"`, SWR `useQuery`), copy from `learnings-template/frontend-patterns.md`.
- All UI strings via react-i18next `useTranslation()` + `t("ns.key")` — never hardcoded.
- Mobile-first Tailwind (default = mobile; `md:`/`lg:`/`xl:` upscale).

**Gate:** Check off a `BUILD_PLAN.md` item ONLY after the section renders correctly for ALL
locales. Run the motion-animations grep: zero `framer-motion` matches.
