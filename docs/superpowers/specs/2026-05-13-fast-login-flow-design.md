# Fast Login Flow — Design Spec

**Date:** 2026-05-13
**Branch:** `feat/fast-login-flow`
**Author:** Stefan + Claude (Opus 4.7)
**Status:** Design — pending review

---

## 1. Problem

In production (https://roman-technologies.dev), navigating from `/` to `/log-in` and onward to `/dashboard` shows visible delay before the next page renders. Several seconds of blank screen on cold loads. Bad client experience.

The marketing layer (root, log-in) carries unnecessary client-side weight: every page is `"use client"`, framer-motion ships in the shared chunk, and the login card adds a hard-coded 0.5s entrance delay before becoming interactive.

## 2. Goal

For the login-flow path only — `/` → `/log-in` → `/dashboard` — hit:

- **Perceived first paint < 500ms** on production, mid-tier laptop, decent network.
- **Time-to-interactive ~1s.**
- **Lighthouse mobile LCP < 1s** on `/log-in`.
- **First-load JS for `/log-in` < 100KB** (currently ~200KB+).

Out of scope: dashboard internal refactor, `/about`, `/contact`, deep dashboard routes.

## 3. Approach

Combination of (a) Server Component + client island split and (b) defer / dynamic-import heavy code. Animation kept but with zero entrance delay.

### 3.1 Route group restructure

Today, the conditional in `SiteShell` ("if dashboard, no header") is what keeps the Header off `/dashboard`. Once the marketing tree and the dashboard tree each have their own layout, that conditional is no longer needed.

Move marketing pages into a route group:

```
frontend/src/app/
├── layout.tsx                       ← Server (root). Fonts + theme boot script + <html>/<body> only.
├── (marketing)/
│   ├── layout.tsx                   ← Server. Renders <MarketingProviders> + <Header /> + main + <Footer />
│   ├── providers.tsx                ← Client. AuthProvider + LoadingProvider (scoped to marketing routes)
│   ├── page.tsx                     ← Server. Root /
│   └── log-in/
│       ├── page.tsx                 ← Server shell (static card chrome, copy)
│       └── LoginForm.tsx            ← Client island (form state, submit handler, framer slide-in)
└── dashboard/
    ├── layout.tsx                   ← Unchanged. Owns its own providers.
    ├── loading.tsx                  ← NEW. Skeleton (sidebar + topbar + content placeholders).
    └── …                            ← Unchanged.
```

`SiteShell.tsx` is deleted. `Providers.tsx` is split into `(marketing)/providers.tsx` and (eventually) `dashboard/providers.tsx`. Dashboard already has its own provider needs handled inside `dashboard/layout.tsx`; no change there for this branch.

### 3.2 Server Component conversions

| File | Today | New |
|---|---|---|
| `frontend/src/app/page.tsx` | client (uses `next/image`, no state) | Server (`(marketing)/page.tsx`) |
| `frontend/src/app/log-in/page.tsx` | client, full form + framer + state | Server `(marketing)/log-in/page.tsx` renders static markup + `<LoginForm />` island |
| `frontend/src/components/SiteShell.tsx` | client, branches on pathname | **deleted** |
| `frontend/src/components/Header.tsx` | client, framer on every nav item | Server-rendered shell (logo + nav links static markup) + small client island for mobile drawer + auth badge |
| `frontend/src/components/Providers.tsx` | client, mounts global AuthProvider | **replaced** by `(marketing)/providers.tsx` (and any dashboard equivalent if needed) |

### 3.3 Header split

Header today is a single `"use client"` component with a framer entrance for the bar plus a per-link staggered entrance (delays cascading up to ~0.5s). Split:

- `Header.tsx` — Server Component. Renders the bar layout, logo, nav links as plain anchors, slot for the right-hand cluster.
- `HeaderRightCluster.tsx` — Client island. Mobile drawer button + state, auth badge (`useAuth`), drawer overlay.

Header bar entrance: replace framer `motion.header` with a single CSS `@keyframes fadeDown` animation in `globals.css`. Nav-link stagger entrance: removed. Static render is fast enough that entrance animation on the bar reads as "polish", not "wait".

### 3.4 LoginForm island

`LoginForm.tsx` is a `"use client"` component that owns:

- Local state: `email`, `password`, `rememberMe`, `showPassword`, `isLoading`, `error`.
- Submit handler — unchanged logic (calls `login()` then `window.open("/dashboard", "cms-dashboard")`).
- Entrance: pure CSS via `.animate-fade-down` utility (from §3.6 globals.css). No framer-motion in this island. Form HTML paints immediately on hydration; the fade plays on top, so perceived appearance is instant.
- Success view (`Successfully Logged In` panel) — co-located, same CSS entrance.
- Remove `useEffect(() => { hide(); }, [hide]);` — Loading screen lingering from sign-out is no longer relevant once `AuthProvider` is scoped properly (see §3.5).

Static markup (heading "Access CMS", subtitle, label text, form layout) lives in the parent Server Component and is sent as HTML.

### 3.5 Auth context scoping

Today `AuthProvider` is mounted at root and runs `getMe()` on every page mount.

New: mount `AuthProvider` inside `(marketing)/providers.tsx` only. The dashboard tree already has its own user/auth handling via its own layout; no change needed for this branch. Marketing routes still get `isLoggedIn` for the Header badge.

**Cookie-sniff optimization dropped.** The backend session cookie (`sid`) is `HttpOnly=True` (backend/auth_service/routers/auth.py:32-40), so `document.cookie` cannot read it from JS. The `getMe()` call stays as-is: fires once on marketing-route mount, async, non-blocking — does not gate first paint. Only effect is that the Header badge flips `Log In` → user icon ~100-300ms after the page lands for logged-in users. Acceptable trade-off; avoids weakening cookie security with a non-HttpOnly companion just for a UI shimmer.

### 3.6 Bundle / runtime cuts

- `LoadingScreen` import → `next/dynamic({ ssr: false })`. Only loaded when `show()` is called. Removes framer + the spinner CSS from initial chunk.
- `framer-motion` not imported by any Server Component, the marketing layout, or the `LoginForm` island. Stays only in the Header right-cluster island (for the mobile drawer animation) and in the dashboard tree.
- Login card entrance: pure CSS `.animate-fade-down` utility (defined in `globals.css`). Replaces the old framer `createSlideIn({ delay: 0.5 })` entirely — form HTML appears at hydration, fade plays on top.
- `prefetchAll()` post-login: **kept**. Dashboard cache warm-up is exactly the perceived-speed win for the next hop.

### 3.7 Dashboard treatment

In-scope changes only:

- Add `frontend/src/app/dashboard/loading.tsx`. Renders a skeleton matching the dashboard layout grid (sidebar block + topbar bar + 2-3 content placeholder cards). Streams to the browser while the route segment compiles and data fetches.
- `router.prefetch("/dashboard")` called from a `useEffect` on the login form's mount. Warms the dashboard JS chunk before the user submits, so when the post-login `window.open("/dashboard", "cms-dashboard")` fires, the new tab paints without a chunk fetch. Keeps the existing `window.open` named-window behavior intact and avoids nested-interactive-element accessibility issues that come from wrapping a `<Button>` in `<Link>`.

Dashboard page internals — untouched.

## 4. File-by-file checklist

| Action | Path |
|---|---|
| New | `frontend/src/app/(marketing)/layout.tsx` |
| New | `frontend/src/app/(marketing)/providers.tsx` |
| Move + convert to Server | `frontend/src/app/page.tsx` → `frontend/src/app/(marketing)/page.tsx` |
| Move + split | `frontend/src/app/log-in/page.tsx` → `frontend/src/app/(marketing)/log-in/page.tsx` (Server) + `LoginForm.tsx` (Client) |
| Convert to Server | `frontend/src/components/Header.tsx` |
| New | `frontend/src/components/HeaderRightCluster.tsx` (Client) |
| Delete | `frontend/src/components/SiteShell.tsx` |
| Delete | `frontend/src/components/Providers.tsx` |
| Slim down | `frontend/src/app/layout.tsx` — remove `<Providers>` + `<SiteShell>` wrap |
| Edit | `frontend/src/context/auth.tsx` — cookie-sniff early return |
| Edit | `frontend/src/app/globals.css` — add `@keyframes fadeDown` for Header |
| New | `frontend/src/app/dashboard/loading.tsx` |
| Dynamic-import | `LoadingScreen` consumers — wrap import via `next/dynamic({ ssr: false })` |

## 5. Verification

- `next build` and inspect the route summary: `/log-in` first-load JS must be < 100KB.
- Lighthouse mobile, prod URL `/` and `/log-in`: LCP < 1s, TBT < 100ms, Performance score >= 90.
- WebPageTest from US-East, throttled 4G: capture filmstrip before merge vs `dev` baseline. Attach to PR.
- Manual smoke on Vercel preview: `/` cold load, navigate to `/log-in`, submit credentials, land on `/dashboard`. Each hop visibly < 500ms paint.
- Existing E2E login test (`.github/workflows/` E2E) must remain green.
- `npm run typecheck` clean. `npm run lint` clean. `npm test` green.

## 6. Risks & mitigations

1. **Route group refactor breaks imports.** `SiteShell` and `Providers` are imported by `frontend/src/app/layout.tsx` only — confirmed via grep. Other files that reference them: none expected; full grep in implementation phase.
2. **`useAuth` consumer scope.** Today: `auth.tsx` (definition), `Header.tsx`, `log-in/page.tsx`. All three live on marketing routes. After provider scope change, all three remain inside `(marketing)`. Safe.
3. ~~**Cookie name unknown.**~~ **Resolved 2026-05-13:** Backend cookie is `sid`, `HttpOnly=True`. JS sniff impossible. Decision: keep `getMe()` unconditional — async, non-blocking, no first-paint regression. See §3.5.
4. **Theme boot script position.** Stays in `frontend/src/app/layout.tsx` `<head>`. The script must run before any rendered children — unchanged.
5. **Header animation regression.** Replacing framer with CSS keyframes may render slightly differently on Safari. Visual diff on mobile + desktop before merge.
6. **`router.prefetch` timing.** `router.prefetch("/dashboard")` runs on form mount. If the user submits before prefetch resolves on a slow network, the post-login tab still has to fetch the chunk. Acceptable — worst case is the same behavior as today. No regression risk.
7. **`prefetchAll` import on login.** Currently dynamic. Stays dynamic. No bundle impact.
8. **Vercel deployment URL slug-redirect** (see `reference_vercel_deployment.md` memory): performance must be measured on canonical `https://roman-technologies.dev`, not a preview slug, to avoid the slug-redirect hop skewing numbers.

## 7. Rollout

1. Branch `feat/fast-login-flow` off `dev` (done).
2. Implement per writing-plans output, step-by-step with tests at each stage.
3. Open PR `feat/fast-login-flow` → `dev`. Run CI + E2E + Lighthouse-CI.
4. Manual review on Vercel preview deployment.
5. Merge to `dev`. Auto-merge `dev` → `master` carries to prod (per existing pipeline).
6. Post-deploy: re-run WebPageTest on prod URL, attach to PR comment.

## 8. Non-goals

- Dashboard internal performance work.
- Server Components for `/about` and `/contact` (not in flow).
- Edge-runtime conversion. Node runtime stays.
- Replacing framer-motion entirely.
- Service worker / PWA pre-cache.
