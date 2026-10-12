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
- Every image and illustration reads its CMS image field through `resolveSite` (fallback: the
  `public/images/` mock, or an animated SVG component kept in code), rendered at its `hint` size
  (`width`/`height`, `object-fit: cover`); an empty image renders the fallback or nothing, never an
  empty box. Every content icon (on services, features, items, contact methods and the like)
  renders `<CmsIcon icon={readIcon(value)} size=… label=… fallback={<DesignedIcon/>} />` (the
  designed or matching Lucide icon is the fallback and the seed). Only favicon/OG generator assets
  and UI-control icons (menu, close, chevrons, arrows, spinners, form affordances) stay in code.
- CMS text rendering (kit: `src/lib/cms-rich-text/`, rules in `client-kit/rich-text/README.md`):
  | Use | How |
  |---|---|
  | Display prose (titles, bodies, descriptions) | `<RichText value={x} format="inline" />` or `format="rich"` |
  | Meta tags, JSON-LD, `alt`/`aria-label`, React keys, search, `tel:`/`mailto:`, `Number()` | `plainText(x)` |
  | Per-word animations, "last N words accented" | `splitRichWords` / `<RichWords>` |
  | Prose inside a link/button/clickable card | `links={false}` |
  | Internal links | `renderLink` with the router's `Link` |
  | Headings inside cards | `headingOffset={1}` |
  CMS prose is rendered with `<RichText>`, never `dangerouslySetInnerHTML`, never inside `<p>`
  (rich values are block-level; use `<RichText as="div" className=...>`; inline values may sit in
  `<p>`/`<h*>`). react-i18next values are read as raw strings (see `i18n-setup`). Content may
  carry span colours/fonts/sizes chosen by the client (ADR-0011, kit ≥ 1.1.0 renders them; never
  strip `style` yourself); the site's own emphasis stays themed by `--cms-rich-*`.
- Mobile-first Tailwind (default = mobile; `md:`/`lg:`/`xl:` upscale).

**Gate:** Check off a `BUILD_PLAN.md` item ONLY after the section renders correctly for ALL
locales. Run the motion-animations grep: zero `framer-motion` matches. Every CMS text render site uses `<RichText>`/`plainText`/`splitRichWords`. Every image and content icon in the section has a CMS field behind it.
