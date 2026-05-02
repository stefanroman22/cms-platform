# Task Plan — CMS Platform (Full)

**Goal:** Build a complete, reusable headless CMS platform where each client manages their website's content, email settings, and custom services through a dashboard, while their published website fetches everything from a single public API endpoint.

**Status:** Active — Phases 1–11 complete. Phases 12–19 planned.
**Last updated:** 2026-04-13

---

## Architecture Decision

```
Next.js (port 3000)
    │
    ├──► FastAPI Auth Service (port 8001)
    │       • POST /auth/login       → issues JWT pair (access + refresh)
    │       • POST /auth/refresh     → exchanges refresh token for new access token
    │       • POST /auth/logout      → blacklists refresh token
    │       Reads users from Supabase `users` table
    │       Signs JWTs with RS256 (asymmetric — private key signs, public key verifies)
    │
    └──► Django CMS API (port 8000)
            • GET /api/projects/     → returns projects for authenticated user
            • (future CMS endpoints)
            Validates JWT using FastAPI's PUBLIC key (no shared secret needed)
            Reads projects from Supabase `projects` table via Django ORM
```

**Why FastAPI for auth?**
FastAPI is async-native, lightweight, and ideal for a high-throughput auth microservice. Django handles the heavier CMS domain logic. This separation means auth can scale independently.

**Why RS256 (asymmetric JWT)?**
Both services need to verify tokens, but only the auth service should *issue* them. RS256 lets Django verify tokens using only the public key — the private key never leaves the FastAPI service. More secure than HS256 shared secrets.

---

## Phases

### Phase 0 — Prerequisites & Supabase Setup
- [ ] 0.1 Create `users` table in Supabase (id UUID, email, password_hash Argon2id, full_name, is_active, timestamps)
- [ ] 0.2 Create `projects` table in Supabase (id UUID, user_id FK → users, name, description, slug, timestamps)
- [ ] 0.3 Create `refresh_tokens` table in Supabase (id, user_id FK, token_hash SHA-256, expires_at, revoked)
- [ ] 0.4 Generate RS256 key pair (private.pem / public.pem) for JWT signing
- [ ] 0.5 Set up .env files for FastAPI auth service and Django

### Phase 1 — FastAPI Auth Service
- [ ] 1.1 Scaffold FastAPI app (`backend/auth_service/`)
- [ ] 1.2 Install dependencies: fastapi, uvicorn, python-jose[cryptography], passlib[bcrypt], supabase-py, python-dotenv
- [ ] 1.3 Supabase client setup — connect to `users` table
- [ ] 1.4 Implement `POST /auth/login`
       - Lookup user by email in Supabase
       - Verify bcrypt password hash
       - Issue access token (15 min expiry) + refresh token (7 or 30 days based on `remember_me`)
       - Return tokens as HttpOnly cookies (not localStorage — XSS protection)
- [ ] 1.5 Implement `POST /auth/refresh`
       - Read refresh token from HttpOnly cookie
       - Validate it hasn't been blacklisted (check Supabase `token_blacklist` table)
       - Issue new access token
- [ ] 1.6 Implement `POST /auth/logout`
       - Blacklist current refresh token in Supabase
       - Clear HttpOnly cookies
- [ ] 1.7 Implement `GET /auth/me`
       - Validate access token, return user info (id, email)
- [ ] 1.8 CORS configuration for Next.js origin
- [ ] 1.9 Rate limiting on login endpoint (prevent brute force)

### Phase 2 — Django JWT Middleware
- [ ] 2.1 Install dependencies: PyJWT, cryptography, psycopg2-binary (for Supabase PG connection)
- [ ] 2.2 Switch Django DB config from SQLite → Supabase PostgreSQL
- [ ] 2.3 Create Django `JWTAuthentication` class (reads access token from cookie or Authorization header, verifies with RS256 public key)
- [ ] 2.4 Create `projects` Django model mapped to Supabase `projects` table
- [ ] 2.5 Implement `GET /api/projects/` endpoint (returns projects for request.user)
- [ ] 2.6 Wire `JWTAuthentication` into DRF `DEFAULT_AUTHENTICATION_CLASSES`

### Phase 3 — Frontend Integration
- [ ] 3.1 Replace mock login logic in `frontend/src/app/log-in/page.tsx` with real API call to FastAPI `/auth/login`
- [ ] 3.2 Pass `remember_me` boolean in request body
- [ ] 3.3 Handle auth errors (invalid credentials, server errors) with user-facing messages
- [ ] 3.4 Create `frontend/src/lib/auth.ts` — helper functions: `login()`, `logout()`, `getMe()`
- [ ] 3.5 Create `frontend/src/middleware.ts` — Next.js route protection (redirect unauthenticated users from `/dashboard` to `/log-in`)
- [ ] 3.6 Create `frontend/src/app/dashboard/page.tsx` — protected page that fetches and displays projects from Django API
- [ ] 3.7 Update Header to show logout button when authenticated

### Phase 4 — Security Hardening
- [ ] 4.1 HttpOnly + Secure + SameSite=Strict cookies (prevent XSS and CSRF)
- [ ] 4.2 CSRF protection on FastAPI (double-submit cookie pattern or CSRF token)
- [ ] 4.3 Refresh token rotation (issue new refresh token on each refresh, invalidate old)
- [ ] 4.4 Login rate limiting (e.g., 5 attempts per IP per 15 min using slowapi)
- [ ] 4.5 Ensure passwords are bcrypt-hashed in Supabase (document migration if currently plaintext)
- [ ] 4.6 Add security headers (HSTS, X-Frame-Options, X-Content-Type-Options)

### Phase 5 — Testing
- [ ] 5.1 FastAPI: unit tests for login, refresh, logout
- [ ] 5.2 Django: unit tests for JWT middleware and projects endpoint
- [ ] 5.3 Frontend: test login flow (valid, invalid, remember me toggle)
- [ ] 5.4 End-to-end: login → see projects → logout → redirect to login

---

## Key Decisions Log

| Decision | Rationale |
|---|---|
| FastAPI for auth | Async, lightweight, ideal for high-throughput token operations |
| Django for CMS | Existing setup, DRF ecosystem, admin panel |
| RS256 JWT | Private key stays in auth service; Django only needs public key |
| HttpOnly cookies | Prevents XSS from stealing tokens (vs localStorage) |
| 15-min access token | Short-lived reduces blast radius if stolen |
| 7/30-day refresh token | Matches UX requirement; stored server-side for revocation |
| Supabase as DB | Single source of truth; users + projects + refresh_tokens all in one PG instance |
| Argon2id for passwords | Gold standard hashing; GPU-resistant + side-channel resistant |
| SHA-256 hash of refresh token in DB | Token itself never stored — even a DB breach can't reuse tokens |
| Token revocation table | Enables logout/revocation without shared state between services |

---

## Phase 6 — Client Dashboard Rebuild

### Goal
Replace the current bare-bones `/dashboard` with a full client portal — separate app shell (no site Header/Footer), light theme, left sidebar nav, animated right-panel transitions.

### Architecture

```
/dashboard/*  →  dashboard/layout.tsx   (no Header/Footer; own shell)
                  │
                  ├── Left Sidebar (fixed, always visible)
                  │     • Logo / brand mark
                  │     • Nav: Projects Overview, Account Settings, Create New Project
                  │     • Bottom: user email + Sign out
                  │
                  └── Right Content Panel (fades in/out on nav change)
                        • /dashboard              → ProjectsOverview
                        • /dashboard/account      → AccountSettings
                        • /dashboard/new-project  → CreateNewProject
```

**Routing strategy:** URL-based sub-routes (not state-based) so users can bookmark/share links and browser back works naturally. Left panel stays mounted; right content is a Next.js nested layout slot — Framer Motion `AnimatePresence` on the page wrapper handles fade.

**Theme:** White background (`#FFFFFF` / `zinc-50`), text `zinc-900`, accents `zinc-800`, borders `zinc-200`. Mirrors the website's zinc palette but inverted (light mode).

### Phase 6 Tasks

#### 6.1 — Dashboard Layout Shell
- [ ] Create `frontend/src/app/dashboard/layout.tsx` — wraps all `/dashboard/*` routes, renders Sidebar + `{children}` content slot, **no** site Header/Footer
- [ ] Create `frontend/src/components/dashboard/Sidebar.tsx` — left nav panel
- [ ] Add `AnimatePresence` page wrapper for fade transitions in layout

#### 6.2 — Projects Overview (update existing page)
- [ ] Rewrite `frontend/src/app/dashboard/page.tsx` — light theme, search filter input at top, project cards grid
- [ ] Projects fetched from Django `/api/projects/` → Supabase via supabase-py

#### 6.3 — Account Settings page
- [ ] Create `frontend/src/app/dashboard/account/page.tsx`
- [ ] Display: email (read-only), full_name, date joined, projects count
- [ ] Change password form → calls `POST /auth/change-password` on FastAPI (new endpoint)
- [ ] FastAPI: add `POST /auth/change-password` endpoint (verify current pw, hash new pw, update Supabase)

#### 6.4 — Create New Project page
- [ ] Create `frontend/src/app/dashboard/new-project/page.tsx`
- [ ] Form fields: Project Name, Type (Website / Web App / Mobile App / Other), Description, Budget range (optional), Timeline (optional)
- [ ] On submit: insert row into Supabase `project_requests` table (not `projects` — this is an enquiry, not a confirmed project)
- [ ] Create `project_requests` table in Supabase

#### 6.5 — Supabase: confirm projects table + add project_requests
- [ ] Confirm `projects` table exists (already created in Phase 0)
- [ ] Create `project_requests` table: id, user_id FK, name, type, description, budget_range, timeline, status (pending/reviewed/approved), created_at

#### 6.6 — Login redirect
- [ ] Update `frontend/src/app/log-in/page.tsx`: open `/dashboard` in a **new tab** on success (`window.open('/dashboard', '_blank')`)

---

## Phase 9 — Client-Side Caching (Stale-While-Revalidate)

### Problem
Every navigation to `/dashboard` re-mounts the Projects page and fires a fresh fetch.
Account data is already persistent (lives in `UserProvider` for the session), but projects are not.

### Strategy: Stale-While-Revalidate (SWR)
No external library. A module-level Map acts as the cache store.
- **On mount with fresh cache** → return immediately, 0ms wait, no loading spinner
- **On mount with stale cache** → return stale data immediately (still 0ms), fire silent background revalidation, swap in new data when it arrives
- **On mount with no cache** → show loading, fetch, cache result
- **Periodic background refresh** → interval-based silent revalidation while dashboard is open
- **On logout** → wipe the entire cache so the next user starts clean

### TTLs
| Data | TTL | Refetch interval |
|---|---|---|
| `/api/account` | 5 min | 5 min |
| `/api/projects` | 2 min | 2 min |

### Prefetch on login
After `login()` succeeds, fire both fetches immediately in the login tab.
By the time the dashboard window opens and components mount, data is already cached → 0ms first-load.

### 9.1 — `frontend/src/lib/cache.ts`
- Module-level `Map<string, { data, fetchedAt, inflight? }>` (survives re-renders, cleared on logout)
- `get<T>(key)`, `set(key, data)`, `isStale(key, ttlMs)`, `invalidate(key)`, `clearAll()`
- `getInflight<T>(key)` / `setInflight(key, p)` — deduplicates concurrent fetches

### 9.2 — `frontend/src/hooks/useQuery.ts`
- `useQuery<T>(key, fetcher, { ttl, refetchInterval? })` → `{ data, loading, error, refresh }`
- On mount: serve cache if fresh, serve-and-revalidate if stale, fetch if empty
- `refetchInterval`: sets up `setInterval` for silent background refresh while mounted
- `refresh()`: force-refetch regardless of staleness (e.g. manual pull-to-refresh)

### 9.3 — Wire `useQuery` into UserContext (`context/user.tsx`)
- Replace raw `useEffect`+`fetch` with `useQuery("account", fetchAccount, { ttl: 5min, refetchInterval: 5min })`
- `updateFullName` keeps optimistic update in cache via `cache.set()`

### 9.4 — Wire `useQuery` into Projects page (`dashboard/page.tsx`)
- Replace raw `useEffect`+`fetch` with `useQuery("projects", fetchProjects, { ttl: 2min, refetchInterval: 2min })`
- Remove redundant `getMe()` call (middleware protects the route)

### 9.5 — Prefetch on login (`log-in/page.tsx`)
- After `login()` resolves, call `prefetchAll()` from `cache.ts`
- `prefetchAll()` fires both `/api/account` and `/api/projects` and caches results

### 9.6 — Clear cache on logout (`lib/auth.ts`)
- `logout()` calls `cache.clearAll()` before/after the API call

---

## Phase 8 — Instant Navigation (Performance)

### 8.1 Optimistic Update Hook (Frontend)
- [ ] `useOptimistic<T>(value, serverFn)` hook
  - Applies update to local state before server responds
  - Rolls back to previous value on server error
  - Returns `{ optimisticValue, update, isPending, error }`
- [ ] Wire into account page: full_name update uses hook

### 8.2 Prefetch Store (Frontend)
- [ ] `frontend/src/lib/prefetch-store.ts` — module-level Map<string, Promise<unknown>>
  - `prefetch(key, fetcher)` — fires fetch, stores Promise
  - `consume(key)` — returns stored Promise and deletes entry (one-use)
- [ ] `auth.tsx` (AuthProvider) — when `isLoggedIn` flips true, call `prefetch("account", ...)`
- [ ] `user.tsx` (UserProvider) — `consume("account")` first; only fire own fetch if nothing stored

### 8.3 Redis Partial Cache (Backend)
- [ ] Install `redis[hiredis]` in FastAPI venv
- [ ] `backend/auth_service/services/cache.py`
  - `get_redis()` singleton — connects if `REDIS_URL` is set, returns `None` otherwise (graceful no-op)
  - `cache_get(user_id, key)` / `cache_set(user_id, key, data, ttl)`
  - Keys: `cms:user:{user_id}:account` / `cms:user:{user_id}:projects:partial`
  - UUID validation on `user_id` before constructing keys (safety)
- [ ] `GET /account` — serve from cache if hit, populate on miss (TTL 5 min)
- [ ] `GET /projects` — serve partial (id, name, slug, is_active) from cache on hit
  - Full metadata (description, timestamps) added only when partial miss
  - TTL 2 min
- [ ] `PATCH /auth/profile` — invalidate `cms:user:{id}:account` on name change
- [ ] `PATCH /auth/change-password` — no cache invalidation needed (not cached)

### 8.4 Safety
- [ ] UUID regex guard before every Redis key construction
- [ ] Keys never contain user-supplied strings (only UUID + fixed suffixes)
- [ ] TTL on every key (no unbounded cache growth)

### Decisions
| Decision | Rationale |
|---|---|
| Graceful Redis degradation | App works without Redis; cache is enhancement not dependency |
| Module-level prefetch store | Simpler than context; Promise shared across module boundary |
| Partial projects cache | Saves ~60% memory vs caching full objects with descriptions |
| consume() is one-use | Prevents stale prefetch being re-used after data changes |

---

## Phase 7 — Change Full Name Feature

### 7.1 Backend — FastAPI
- [ ] Add `ChangeNameRequest` schema (`full_name: str`)
- [ ] Add `PATCH /auth/profile` endpoint
  - Requires valid access_token cookie
  - Strip whitespace, reject empty, enforce max 100 chars
  - Update `users.full_name` + `users.updated_at` in Supabase
  - Return `{ full_name }` on 200

### 7.2 Frontend — UserContext
- [ ] Expose `updateFullName(name: string)` on context value type + implementation

### 7.3 Frontend — Account page inline edit
- [ ] Pencil icon on Full name row opens inline input
- [ ] Save disabled when: empty, whitespace-only, unchanged from current
- [ ] Cancel restores original value
- [ ] On success: update context + collapse form
- [ ] On error: inline error message, form stays open
- [ ] Loading lock prevents double-submit

### Edge Cases
- Empty / whitespace-only → button disabled (client + server)
- Unchanged → button disabled (no pointless request)
- Name > 100 chars → maxLength + server 422
- Network failure → error, form stays open
- Double-click submit → loading lock
- XSS → React escapes output; server stores raw text

---

### Key Design Decisions

| Decision | Rationale |
|---|---|
| Separate layout (no Header/Footer) | Dashboard is a different product context — SaaS portal feel |
| Light theme | Contrast with the dark marketing site; makes data-dense UI easier to read |
| URL-based routing (not state) | Bookmarkable, back-button works, clean architecture |
| AnimatePresence on page wrapper | Only right panel fades — sidebar stays fixed, no layout shift |
| `project_requests` ≠ `projects` | Enquiries are unconfirmed; keeps confirmed project data clean |

---

## Phase 11 — Dashboard Theme Switching

**Goal:** Let users toggle between light and dark themes inside the dashboard. Preference persists across sessions via localStorage. No visual change on the public marketing site.

### Architecture decisions

| Decision | Rationale |
|---|---|
| Custom `ThemeContext`, no `next-themes` | Follows the existing context pattern; avoids a new dependency for a small feature |
| Tailwind v4 `@custom-variant dark` scoped to `[data-theme=dark]` | Scopes dark classes to the dashboard wrapper only — public site stays permanently dark unaffected |
| `data-theme` on the dashboard layout wrapper div | Single attribute flip triggers all `dark:` utilities without touching `<html>` |
| `suppressHydrationWarning` on wrapper div | Prevents React hydration mismatch when localStorage value differs from server default |
| Default theme: `light` | Matches current dashboard appearance; dark is opt-in |
| Sun icon = light mode active, Moon icon = dark mode active | Standard convention — icon shows what the current mode is, not what clicking will switch to |

### Color mapping (light → dark)

| Element | Light | Dark |
|---|---|---|
| Dashboard shell bg | `bg-zinc-50` body | `dark:bg-zinc-950` |
| Sidebar bg | `bg-white` | `dark:bg-zinc-950` |
| Sidebar border | `border-zinc-200` | `dark:border-zinc-800` |
| Section dividers | `border-zinc-100 / divide-zinc-100` | `dark:border-zinc-800 dark:divide-zinc-800` |
| Section card | `bg-white border-zinc-200` | `dark:bg-zinc-900 dark:border-zinc-800` |
| Card header bg | implicit white | `dark:bg-zinc-900` |
| Active nav item | `bg-zinc-900 text-white` | unchanged (already dark) |
| Inactive nav item | `text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900` | `dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100` |
| Sign out button | `text-zinc-400 hover:bg-zinc-100` | `dark:text-zinc-500 dark:hover:bg-zinc-800 dark:hover:text-zinc-100` |
| Page h1 | `text-zinc-900` | `dark:text-zinc-50` |
| Page subtitle / muted text | `text-zinc-500` | `dark:text-zinc-400` |
| Section heading `text-zinc-700` | `dark:text-zinc-300` |
| Input / select / textarea | `bg-zinc-50 border-zinc-200 text-zinc-900` | `dark:bg-zinc-800 dark:border-zinc-700 dark:text-zinc-100 dark:placeholder:text-zinc-500` |
| Input focus | `focus:border-zinc-400 focus:bg-white` | `dark:focus:border-zinc-500 dark:focus:bg-zinc-750` (or zinc-800) |
| Field label | `text-zinc-500` | `dark:text-zinc-400` |
| Primary button | `bg-zinc-900 text-white hover:bg-zinc-700` | unchanged (already dark) |
| Error banner | `bg-red-50 text-red-700` | `dark:bg-red-950 dark:text-red-400` |
| Success banner | `bg-emerald-50 text-emerald-700` | `dark:bg-emerald-950 dark:text-emerald-400` |
| Brand icon bg | `bg-zinc-900` | unchanged |
| Row icon color | `text-zinc-400` | `dark:text-zinc-500` |
| Row label | `text-zinc-500` | `dark:text-zinc-400` |
| Row value | `text-zinc-900` | `dark:text-zinc-100` |
| Search input | `bg-white border-zinc-200` | `dark:bg-zinc-900 dark:border-zinc-700` |
| Project card | `bg-white border-zinc-200 shadow-sm` | `dark:bg-zinc-900 dark:border-zinc-800` |
| Project slug badge | `bg-zinc-100 text-zinc-500` | `dark:bg-zinc-800 dark:text-zinc-400` |
| Active badge | `bg-emerald-50 text-emerald-700` | `dark:bg-emerald-950 dark:text-emerald-400` |
| Skeleton pulse | `bg-zinc-200` | `dark:bg-zinc-700` |

---

### 11.1 — Configure Tailwind v4 dark variant (`globals.css`)

Add one line to `globals.css` after the `@import`:

```css
@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));
```

This makes every `dark:` utility in Tailwind activate when a `[data-theme=dark]` ancestor is present — scoped to the dashboard wrapper only.

### 11.2 — `ThemeContext` (`frontend/src/context/theme.tsx`)

```ts
type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}
```

- Reads initial value from `localStorage.getItem("dashboard-theme")` (default `"light"`)
- `toggleTheme()` flips state and writes back to localStorage
- Wrapped in a check for `typeof window !== "undefined"` to avoid SSR errors
- Exported: `ThemeProvider`, `useTheme`

### 11.3 — Wire into `dashboard/layout.tsx`

- Import `ThemeProvider` and `useTheme`
- Render a `ThemeShell` client component that reads from `useTheme` and applies `data-theme={theme}` to its wrapper div
- The wrapper div carries `suppressHydrationWarning` and wraps both `<Sidebar>` and the content div
- `ThemeProvider` wraps the whole layout (alongside `UserProvider`)

Layout structure after:
```tsx
<ThemeProvider>
  <UserProvider>
    <ThemeShell>          {/* client: data-theme={theme}, suppressHydrationWarning */}
      <Sidebar />
      <div className="flex-1 overflow-y-auto">
        <DashboardContent>{children}</DashboardContent>
      </div>
    </ThemeShell>
  </UserProvider>
</ThemeProvider>
```

The `ThemeShell` component lives in `components/dashboard/ThemeShell.tsx` (client component, reads `useTheme`).

### 11.4 — Appearance toggle in Account Settings (`account/page.tsx`)

New "Appearance" section card, below "Change Password":

```
┌─────────────────────────────────────────────────┐
│ Appearance                                       │
├─────────────────────────────────────────────────┤
│  [Sun/Moon icon]  Theme    [Light ○ ● Dark]     │
└─────────────────────────────────────────────────┘
```

Toggle pill design:
- A `<button>` with `role="switch"` and `aria-checked={theme === "dark"}`
- Contains two slots: `[Sun icon + "Light"]` and `[Moon icon + "Dark"]`
- Active slot: `bg-white shadow-sm text-zinc-900` (light mode) / `bg-zinc-700 text-white` (dark mode)
- Pill track: `bg-zinc-100` (light) / `dark:bg-zinc-800` (dark)
- Framer Motion `layout` animation on the moving indicator for smooth slide
- Calls `toggleTheme()` from `useTheme`
- No server call needed — localStorage only

### 11.5 — Update `Sidebar.tsx`

Apply `dark:` variants to every color class per the mapping table above. No logic changes.

### 11.6 — Update shared style constants (`lib/styles.ts`)

Add `dark:` variants to each dashboard constant:
- `dashboardInputCn` — add dark background/border/text variants
- `dashboardInputLgCn` — same
- `dashboardFieldLabelCn` — `dark:text-zinc-400`
- `dashboardSectionCardCn` — `dark:bg-zinc-900 dark:border-zinc-800`
- `dashboardErrorBannerCn` — `dark:bg-red-950 dark:text-red-400`
- `dashboardSuccessBannerCn` — `dark:bg-emerald-950 dark:text-emerald-400`
- `dashboardPrimaryBtnCn` — no change (already dark)

### 11.7 — Update shared dashboard components

- `PageHeader.tsx` — add `dark:text-zinc-50` / `dark:text-zinc-400`
- `FormField.tsx` — dark: variants on label (uses constant) and input (uses constant)
- `FormFeedback.tsx` — uses constants (updated in 11.6, no extra changes)

### 11.8 — Update dashboard pages

Apply `dark:` variants to any inline classes not covered by shared constants:

**`dashboard/page.tsx`** (Projects Overview):
- Search input, project cards, skeleton loaders, empty state, badge colors

**`account/page.tsx`** (Account Settings):
- `Row` component colors, section card header, inline name edit button, cancel button, edit/pencil button
- Add Appearance section (task 11.4)

**`new-project/page.tsx`** (Create New Project):
- Success state card (`border-emerald-200 bg-emerald-50`) → dark variants
- "Submit another request" button

### Completion checklist
- [x] 11.1 `globals.css` — add `@custom-variant dark`
- [x] 11.2 `context/theme.tsx` — ThemeContext + ThemeProvider
- [x] 11.3 `dashboard/layout.tsx` + `ThemeShell.tsx` — wire provider and `data-theme`
- [x] 11.4 `account/page.tsx` — Appearance section + toggle button
- [x] 11.5 `Sidebar.tsx` — dark: variants
- [x] 11.6 `lib/styles.ts` — dark: variants on all dashboard constants
- [x] 11.7 Shared components (`PageHeader`, `FormField`, `FormFeedback`) — dark: variants
- [x] 11.8 Dashboard pages (`page.tsx`, `new-project/page.tsx`, `account/page.tsx`) — remaining inline dark: variants

---

## Phase 12 — Database Schema: Services, Content & Admin Role

**Goal:** Lay the database foundation. Every subsequent phase builds on these tables.

### Architecture decisions

| Decision | Rationale |
|---|---|
| `service_types` table seeds built-in service plugins | Decouples "what a service is" from "what a project uses" — new service types can be added without code changes |
| `project_services` links a project to a named service instance | One project can have `hero` (text_block) AND `about` (text_block) — same type, different keys |
| `content_entries` stores content as JSONB | Flexible schema per service type; avoids one table per type |
| `is_admin` boolean on `users` table | Simplest approach; no RBAC overhead for a two-role system (admin / client) |
| Supabase Storage bucket `cms-files` with path `/{project_slug}/{service_key}/` | One bucket, path-based isolation per project; easy signed URLs |
| `email_configs` as separate table | Email addresses are sensitive config, not content — kept separate for clarity and audit |

### 12.1 — Supabase schema migrations

**`users` table** — add column:
```sql
ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE users SET is_admin = TRUE WHERE email = 'stefanromanpers@gmail.com';
```

**`service_types` table** — registry of all available service plugins:
```sql
CREATE TABLE service_types (
  slug        VARCHAR PRIMARY KEY,   -- 'text_block', 'image', 'email_config', etc.
  name        VARCHAR NOT NULL,
  description TEXT,
  icon        VARCHAR,               -- lucide icon name for dashboard UI
  schema      JSONB NOT NULL,        -- JSON Schema describing the fields this service stores
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

**`project_services` table** — which services a project has enabled:
```sql
CREATE TABLE project_services (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  service_type_slug VARCHAR NOT NULL REFERENCES service_types(slug),
  service_key       VARCHAR NOT NULL,   -- unique name within the project: 'hero', 'menu', etc.
  label             VARCHAR,            -- human label shown in dashboard
  display_order     INT NOT NULL DEFAULT 0,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(project_id, service_key)
);
```

**`content_entries` table** — stores the actual content for each service instance:
```sql
CREATE TABLE content_entries (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_service_id UUID NOT NULL REFERENCES project_services(id) ON DELETE CASCADE,
  content            JSONB NOT NULL DEFAULT '{}',
  updated_at         TIMESTAMPTZ DEFAULT NOW(),
  updated_by         UUID REFERENCES users(id)
);
CREATE UNIQUE INDEX content_entries_service_unique ON content_entries(project_service_id);
```

**`email_configs` table** — email destination per form per project service:
```sql
CREATE TABLE email_configs (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_service_id UUID NOT NULL REFERENCES project_services(id) ON DELETE CASCADE,
  destination_email  VARCHAR NOT NULL,
  updated_at         TIMESTAMPTZ DEFAULT NOW(),
  updated_by         UUID REFERENCES users(id)
);
CREATE UNIQUE INDEX email_configs_service_unique ON email_configs(project_service_id);
```

**Supabase Storage:** Create bucket `cms-files` (public read, authenticated write).

### 12.2 — Seed built-in service types

```sql
INSERT INTO service_types (slug, name, description, icon, schema) VALUES
('text_block',   'Text Block',    'Editable rich text content for a page section', 'FileText', '{"fields": {"title": "string", "body": "richtext"}}'),
('image',        'Image',         'A single image with alt text', 'Image', '{"fields": {"url": "file", "alt": "string"}}'),
('gallery',      'Gallery',       'Multiple images', 'Images', '{"fields": {"items": "file[]"}}'),
('email_config', 'Email Config',  'Contact form destination email address', 'Mail', '{"fields": {"destination_email": "email"}}'),
('floor_plan',   'Floor Plan',    'Restaurant/venue floor plan image', 'LayoutGrid', '{"fields": {"url": "file", "alt": "string"}}'),
('video',        'Video',         'Embedded or uploaded video', 'Video', '{"fields": {"url": "string", "poster": "file"}}'),
('file_download','File Download', 'A downloadable file attachment', 'Download', '{"fields": {"url": "file", "filename": "string"}}'),
('key_value',    'Key-Value Store','Arbitrary named fields', 'Hash', '{"fields": {"entries": "object"}}');
```

### 12.3 — Expose `is_admin` in FastAPI

- Add `is_admin: bool` field to `UserOut` Pydantic schema
- `authenticate_user()` / `get_user_from_access_token()` reads `is_admin` from Supabase `users` row
- Include `is_admin` in the JWT access token payload
- Expose via `GET /auth/me` response
- `UserContext` on the frontend stores `is_admin` — Sidebar shows Admin section conditionally

### Completion checklist
- [ ] 12.1 Supabase: add `is_admin` column, set admin flag for stefanromanpers@gmail.com
- [ ] 12.2 Supabase: create `service_types`, `project_services`, `content_entries`, `email_configs`
- [ ] 12.3 Supabase: create `cms-files` storage bucket
- [ ] 12.4 Seed `service_types` with 8 built-in types
- [ ] 12.5 FastAPI: add `is_admin` to `UserOut` schema + JWT payload + `/auth/me` response
- [ ] 12.6 Frontend: `UserContext` stores `is_admin`; Sidebar conditionally renders Admin section

---

## Phase 13 — Public Content API Endpoint

**Goal:** One public GET endpoint that client websites call to fetch all their content.

### Architecture decisions

| Decision | Rationale |
|---|---|
| `GET /content/{project_slug}` — no auth required | Client websites are public; requiring auth would block SSG/ISR |
| Response is a flat key→content map keyed by `service_key` | Simple to consume: `content.hero.title`, `content.logo.url` — no nesting |
| CORS allows `*` on this endpoint only | Other endpoints remain locked to known origins; public content is genuinely public |
| Email configs excluded from public response | Email destinations must never be exposed to website visitors |
| `Cache-Control: public, max-age=60, stale-while-revalidate=300` | Reduces load; CDN can cache; content changes propagate within ~5 minutes |
| `ETag` / `Last-Modified` headers | Allows client websites to use conditional requests for efficiency |

### 13.1 — FastAPI router `content.py`

New file: `backend/auth_service/routers/content.py`

```python
GET /content/{project_slug}
```

Response shape:
```json
{
  "project_slug": "marios-restaurant",
  "project_name": "Mario's Restaurant",
  "last_updated": "2026-04-13T10:00:00Z",
  "content": {
    "hero": {
      "_type": "text_block",
      "_label": "Hero Section",
      "title": "Welcome to Mario's",
      "body": "<p>Fine Italian Dining...</p>"
    },
    "hero_image": {
      "_type": "image",
      "_label": "Hero Image",
      "url": "https://[supabase-url]/storage/v1/object/public/cms-files/marios-restaurant/hero_image/image.jpg",
      "alt": "Restaurant interior"
    },
    "floor_plan": {
      "_type": "floor_plan",
      "_label": "Floor Plan",
      "url": "https://...",
      "alt": "Dining room floor plan"
    }
  }
}
```

Note: `email_config` service types are NEVER included in the public response.

### 13.2 — Client website usage

```typescript
// In client website (separate repo)
import type { CMSContent } from './cms.types'  // generated types

const content: CMSContent = await fetch(
  'https://cms.romantechnologies.com/content/marios-restaurant'
).then(r => r.json())

// Use: content.content.hero.title
//      content.content.hero_image.url
//      content.content.floor_plan.url
```

### 13.3 — `cms.config.ts` specification (client website config file)

One file in the root of every client website repo:

```typescript
// cms.config.ts
export const cmsConfig = {
  projectSlug: "marios-restaurant",
  endpoint: "https://cms.romantechnologies.com/content",
  // Optional: declare expected services for TypeScript type safety
  services: {
    hero:        "text_block",
    hero_image:  "image",
    floor_plan:  "floor_plan",
    contact_cta: "text_block",
    gallery:     "gallery",
  }
} as const
```

This file is the only CMS-aware file in a client website. It declares the contract. The CMS admin provisions matching services in the dashboard when setting up the project.

### Completion checklist
- [ ] 13.1 `routers/content.py` — `GET /content/{project_slug}` with correct response shape
- [ ] 13.2 Register content router in `main.py` with CORS `allow_origins=["*"]` scoped to `/content/*`
- [ ] 13.3 Exclude `email_config` from public response
- [ ] 13.4 Add `Cache-Control` + `ETag` response headers
- [ ] 13.5 Define `cms.config.ts` specification + example in `findings.md`
- [ ] 13.6 Write TypeScript type generator: `GET /content/{slug}/types` returns a `.d.ts` string

---

## Phase 14 — Project Workspace (Dashboard Routes)

**Goal:** When a client clicks their project, they enter a workspace showing all enabled services.

### Routes

```
/dashboard/[projectSlug]                    → Project home (service cards grid)
/dashboard/[projectSlug]/[serviceKey]       → Individual service editor
```

### 14.1 — Next.js dynamic routes

- `frontend/src/app/dashboard/[projectSlug]/page.tsx` — Project workspace
- `frontend/src/app/dashboard/[projectSlug]/[serviceKey]/page.tsx` — Service editor
- `frontend/src/app/dashboard/[projectSlug]/layout.tsx` — Shared layout (project header + breadcrumb)

### 14.2 — Project home page

Fetches: `GET /api/projects/{projectSlug}/services` (authenticated)

Renders a grid of service cards, each showing:
- Service type icon (from `service_types.icon`)
- Service label (from `project_services.label`)
- Service type name
- Last updated timestamp
- "Edit" button → navigates to service editor

### 14.3 — FastAPI endpoints for project workspace

```
GET  /projects/{project_slug}/services               → list all services for a project
GET  /projects/{project_slug}/services/{service_key} → get content for one service
PUT  /projects/{project_slug}/services/{service_key} → save content for one service
```

Admin-only:
```
POST   /projects/{project_slug}/services             → add a new service to a project
DELETE /projects/{project_slug}/services/{service_key} → remove a service
GET    /admin/projects                               → all projects for all clients
GET    /admin/service-types                          → all available service types
```

### 14.4 — Project access control

- User can only access their own project workspace
- Admin can access all projects
- Middleware check: `project.user_id == current_user.id OR current_user.is_admin`

### 14.5 — Projects list page update (`dashboard/page.tsx`)

- Project cards become clickable → navigates to `/dashboard/{slug}`
- Add "Open website" icon button (if project has a website URL stored)

### Completion checklist
- [ ] 14.1 Next.js routes: `[projectSlug]/page.tsx`, `[projectSlug]/[serviceKey]/page.tsx`, `[projectSlug]/layout.tsx`
- [ ] 14.2 `GET /projects/{slug}/services` FastAPI endpoint
- [ ] 14.3 `GET /projects/{slug}/services/{key}` FastAPI endpoint
- [ ] 14.4 `PUT /projects/{slug}/services/{key}` FastAPI endpoint (content save)
- [ ] 14.5 Admin endpoints: `POST/DELETE /projects/{slug}/services`, `GET /admin/projects`
- [ ] 14.6 Access control middleware (own project or admin)
- [ ] 14.7 Project cards in dashboard/page.tsx become clickable links

---

## Phase 15 — Service Editors

**Goal:** Each service type has a purpose-built editor UI in the dashboard.

### 15.1 — Editor component map

| Service Type | Editor Component | Fields |
|---|---|---|
| `text_block` | `TextBlockEditor` | Title (text input) + Body (textarea or markdown editor) |
| `image` | `ImageEditor` | File upload + URL preview + Alt text input |
| `gallery` | `GalleryEditor` | Multiple file uploads, reorder, delete individual |
| `email_config` | `EmailConfigEditor` | Email address input + validation |
| `floor_plan` | `FloorPlanEditor` | Single image upload + preview (same as ImageEditor, different label) |
| `video` | `VideoEditor` | URL input (YouTube/Vimeo/direct) + optional poster image upload |
| `file_download` | `FileDownloadEditor` | File upload + display filename override |
| `key_value` | `KeyValueEditor` | Dynamic rows of key + value inputs |

### 15.2 — Shared editor shell

`components/dashboard/ServiceEditorShell.tsx`:
- Breadcrumb: Projects → {Project Name} → {Service Label}
- Save button (top right) — calls PUT endpoint
- Success/error feedback banner
- Last saved timestamp

### 15.3 — Auto-save vs manual save

Decision: **Manual save** (explicit button press).
- Reason: file uploads need atomic commit; partial saves would corrupt content
- UX: button shows "Unsaved changes" indicator when content is dirty

### 15.4 — Reusability pattern

Each editor is a React component with props:
```typescript
interface EditorProps {
  projectSlug: string
  serviceKey: string
  initialContent: Record<string, unknown>
  onSave: (content: Record<string, unknown>) => Promise<void>
}
```

The `[serviceKey]/page.tsx` route looks up the service type and renders the correct editor component via a registry map:
```typescript
const EDITOR_MAP: Record<string, React.ComponentType<EditorProps>> = {
  text_block:   TextBlockEditor,
  image:        ImageEditor,
  gallery:      GalleryEditor,
  email_config: EmailConfigEditor,
  floor_plan:   FloorPlanEditor,
  video:        VideoEditor,
  file_download: FileDownloadEditor,
  key_value:    KeyValueEditor,
}
```

### Completion checklist
- [ ] 15.1 `ServiceEditorShell.tsx` — shared layout shell with breadcrumb + save button
- [ ] 15.2 `TextBlockEditor.tsx` — title + body textarea
- [ ] 15.3 `EmailConfigEditor.tsx` — email input + save
- [ ] 15.4 `ImageEditor.tsx` — file upload + preview + alt text
- [ ] 15.5 `FloorPlanEditor.tsx` — reuses ImageEditor with floor plan label
- [ ] 15.6 `GalleryEditor.tsx` — multi-file upload + reorder
- [ ] 15.7 `VideoEditor.tsx` — URL input + poster upload
- [ ] 15.8 `FileDownloadEditor.tsx` — file upload + filename
- [ ] 15.9 `KeyValueEditor.tsx` — dynamic key-value rows
- [ ] 15.10 `EDITOR_MAP` registry in `[serviceKey]/page.tsx`

---

## Phase 16 — File Upload (Supabase Storage)

**Goal:** Editors can upload files (images, PDFs, audio, video) which are stored in Supabase Storage and served via public CDN URLs.

### 16.1 — Upload flow

```
Client browser
  → POST /api/projects/{slug}/services/{key}/upload  (Next.js proxy)
  → POST /projects/{slug}/services/{key}/upload       (FastAPI)
  → Supabase Storage: PUT cms-files/{slug}/{key}/{filename}
  → Returns: { url: "https://[supabase-url]/storage/v1/object/public/cms-files/..." }
```

### 16.2 — FastAPI upload endpoint

```python
POST /projects/{project_slug}/services/{service_key}/upload
Content-Type: multipart/form-data

Response: { "url": "https://...", "filename": "...", "size": 1234, "mime_type": "image/jpeg" }
```

Constraints:
- Max file size: 50 MB
- Allowed MIME types per service type:
  - `image`, `floor_plan`, `gallery`: `image/*`
  - `video`: `video/*`
  - `file_download`: `*/*`
  - Others: rejected

### 16.3 — File naming

Files stored as: `{project_slug}/{service_key}/{uuid}.{extension}`
- UUID prevents collisions on re-upload
- Old files are NOT deleted automatically (prevents broken links if content is rolled back)
- Cleanup: admin can trigger storage cleanup via API

### 16.4 — Next.js proxy for uploads

The existing `app/api/[...path]/route.ts` handles multipart automatically — no changes needed as long as body is forwarded as-is.

### Completion checklist
- [ ] 16.1 Supabase Storage: configure `cms-files` bucket with public read policy
- [ ] 16.2 FastAPI: `POST /projects/{slug}/services/{key}/upload` endpoint
- [ ] 16.3 MIME type validation per service type
- [ ] 16.4 Storage path: `{slug}/{key}/{uuid}.{ext}`
- [ ] 16.5 Frontend: file upload `<input>` component with progress indicator
- [ ] 16.6 Frontend: replace URL field with uploaded URL after successful upload

---

## Phase 17 — Admin Panel

**Goal:** Admin user (stefanromanpers@gmail.com) can see and manage all clients' projects.

### 17.1 — Admin detection

- `UserContext.user.is_admin` drives all admin UI
- FastAPI enforces `is_admin` on all `/admin/*` routes via dependency injection
- Non-admin accessing admin routes → `403 Forbidden`

### 17.2 — Admin sidebar section

When `user.is_admin`:
```
Navigation
  Projects Overview
  Account Settings
  Create New Project

Admin
  All Clients          → /dashboard/admin/clients
  All Projects         → /dashboard/admin/projects
  Service Types        → /dashboard/admin/service-types
```

### 17.3 — Admin pages

**`/dashboard/admin/projects`**
- Table of all projects across all clients
- Columns: client name/email, project name, slug, created date, # services
- Clickable → goes to `/dashboard/{slug}` workspace

**`/dashboard/admin/clients`**
- Table of all users
- Columns: email, full_name, is_admin, joined date, # projects
- Click → view their projects

**`/dashboard/admin/service-types`**
- List all registered service types
- Future: add custom service types (Phase 20+)

### 17.4 — Service management (admin only in workspace)

Inside any project workspace (`/dashboard/{slug}`), admin sees an additional **"Add Service"** button that opens a modal:
- Select service type from dropdown
- Enter `service_key` (URL-safe identifier: `hero`, `menu`, `gallery_1`)
- Enter display label
- Set display order
- Submit → calls `POST /projects/{slug}/services`

Admin also sees a **"Remove"** button on each service card.

### Completion checklist
- [ ] 17.1 FastAPI: `is_admin` dependency for `/admin/*` routes
- [ ] 17.2 `GET /admin/projects` — all projects with user info joined
- [ ] 17.3 `GET /admin/clients` — all users
- [ ] 17.4 Frontend: Admin sidebar section (conditional on `user.is_admin`)
- [ ] 17.5 `dashboard/admin/projects/page.tsx` — all projects table
- [ ] 17.6 `dashboard/admin/clients/page.tsx` — all clients table
- [ ] 17.7 `dashboard/admin/service-types/page.tsx` — service types list
- [ ] 17.8 Admin "Add Service" modal in project workspace
- [ ] 17.9 Admin "Remove Service" button per card

---

## Phase 18 — Client Website Integration

**Goal:** Define the complete integration story for a client website built in a separate repo.

### 18.1 — The contract: `cms.config.ts`

Every client website has exactly one file that describes its CMS relationship:

```typescript
// cms.config.ts — place in project root
export const cmsConfig = {
  projectSlug: "marios-restaurant",
  endpoint: "https://cms.romantechnologies.com/content",
  services: {
    hero:           "text_block",
    hero_image:     "image",
    about_section:  "text_block",
    floor_plan:     "floor_plan",
    gallery:        "gallery",
    menu_pdf:       "file_download",
    contact_video:  "video",
  }
} as const

export type ServiceKey = keyof typeof cmsConfig.services
```

### 18.2 — TypeScript types generation

`GET /content/{slug}/types` returns a TypeScript declaration file body:

```typescript
// Auto-generated — do not edit. Run: npm run cms:sync-types
export interface CMSContent {
  project_slug: string
  project_name: string
  last_updated: string
  content: {
    hero: { _type: "text_block"; _label: string; title: string; body: string }
    hero_image: { _type: "image"; _label: string; url: string; alt: string }
    floor_plan: { _type: "floor_plan"; _label: string; url: string; alt: string }
    gallery: { _type: "gallery"; _label: string; items: Array<{ url: string; alt: string }> }
  }
}
```

### 18.3 — Fetching content (Next.js example)

```typescript
// lib/cms.ts — in client website repo
import { cmsConfig } from '../cms.config'

export async function getCMSContent() {
  const res = await fetch(
    `${cmsConfig.endpoint}/${cmsConfig.projectSlug}`,
    { next: { revalidate: 60 } }  // ISR: revalidate every 60 seconds
  )
  if (!res.ok) throw new Error('Failed to fetch CMS content')
  return res.json()
}
```

### 18.4 — Email form integration

The client website's contact form should NOT expose the email destination. Instead:
- Contact form POSTs to `POST /api/contact` on the client website's own server
- That server calls `GET /email/{project_slug}/{form_key}` on the CMS (authenticated with a project API key)
- CMS returns `{ destination: "contact@client.com" }`
- Client server sends email via its preferred provider

OR simpler: the contact form POSTs directly to a CMS endpoint:
```
POST /forms/{project_slug}/{form_key}
Body: { name, email, message, ... }
→ CMS reads destination from email_configs, sends email via SMTP/Resend
→ Returns 200 on success
```

**Decision: CMS handles form submission directly** (Phase 19).
- Reason: the client website stays purely static/presentational; the CMS owns email logic

### Completion checklist
- [ ] 18.1 Document `cms.config.ts` spec in `findings.md`
- [ ] 18.2 `GET /content/{slug}/types` TypeScript declaration endpoint
- [ ] 18.3 Example `lib/cms.ts` for Next.js client websites
- [ ] 18.4 `npm run cms:sync-types` script spec

---

## Phase 19 — Email Form Handler

**Goal:** Client website forms submit to the CMS, which handles email delivery. No email logic in client repos.

### 19.1 — Endpoint

```
POST /forms/{project_slug}/{form_key}
Content-Type: application/json
Body: { [fieldName: string]: string }
```

- Looks up `email_configs` for the given `project_service_id` matching `project_slug` + `form_key`
- Validates required fields (configurable per service)
- Sends email via Resend (or SMTP) to `destination_email`
- Returns `200 { success: true }` or error
- Rate limited: 5 submissions per IP per 10 minutes
- CORS: allows the client's website domain (stored in `projects.allowed_origins`)

### 19.2 — Email provider

**Decision: Resend** (`resend` Python SDK)
- Modern API, excellent deliverability
- Free tier: 3,000 emails/month
- Simple SDK: `resend.Emails.send({ from, to, subject, html })`

### 19.3 — `projects` table update

Add columns:
```sql
ALTER TABLE projects ADD COLUMN website_url VARCHAR;
ALTER TABLE projects ADD COLUMN allowed_origins TEXT[];  -- CORS whitelist for /forms/
ALTER TABLE projects ADD COLUMN api_key VARCHAR UNIQUE;  -- for future authenticated reads
```

### 19.4 — Form submission flow

```
Client website form
  → POST https://cms.romantechnologies.com/forms/marios-restaurant/contact
  → FastAPI validates rate limit, reads email_configs
  → Sends email via Resend
  → Returns { success: true }
```

### Completion checklist
- [ ] 19.1 Install `resend` in FastAPI venv
- [ ] 19.2 Supabase: add `website_url`, `allowed_origins`, `api_key` to `projects`
- [ ] 19.3 `routers/forms.py` — `POST /forms/{slug}/{form_key}`
- [ ] 19.4 CORS scoped to `projects.allowed_origins` for `/forms/*`
- [ ] 19.5 Rate limiting: 5/IP/10min per form endpoint
- [ ] 19.6 Email template: HTML with sender name, form fields, project branding
- [ ] 19.7 Admin: configure `allowed_origins` per project in dashboard

---

## Implementation Order & Dependencies

```
Phase 12 (DB Schema) ──► Phase 13 (Public API) ──► Phase 18 (Client Integration)
      │
      ▼
Phase 14 (Project Workspace) ──► Phase 15 (Service Editors)
      │                                   │
      ▼                                   ▼
Phase 17 (Admin Panel)          Phase 16 (File Upload)

Phase 19 (Email Forms) — depends on Phase 12 + Phase 13

Phase 20 (Repeater Type) — depends on Phase 12 + Phase 15
Phase 21 (Auto-Config Agent) — depends on Phase 20
Phase 22 (Portfolio Integration) — depends on Phase 20 + Phase 21
Phase 23 (Client SDK Improvements) — depends on Phase 18
```

**Start with Phase 12** — all other phases depend on the database schema being in place.

---

## Phase 20 — `repeater` Service Type

**Goal:** Add a new service type that handles arrays of structured objects. Required for portfolio-style
sites whose content is lists (experience entries, projects, hobbies).

### Why it's needed

Existing types only cover flat data (`key_value` = `Record<string, unknown>`) or
single assets (`image`, `video`). A portfolio's experience section is an `ExperienceEntry[]` —
an ordered list of objects with heterogeneous fields. No current type handles this.

### Architecture decision

| Decision | Rationale |
|---|---|
| Schema stored per service (at creation time) | Each repeater instance defines its own field schema; different projects use different field sets |
| Content stored as `{ items: [...] }` JSONB | Consistent with other types; items are free-form JSONB objects |
| Fields defined by admin at service creation | Admin specifies `[{ key, label, type }]` — avoids generic catch-all editor |
| Field types: `string`, `richtext`, `url`, `tags` | Covers 95% of portfolio use cases without overgeneralising |

### 20.1 — Supabase: add `repeater` to `service_types`

```sql
INSERT INTO service_types (slug, name, description, icon, schema) VALUES (
  'repeater',
  'Repeater',
  'An ordered list of structured items, each with the same fields (e.g. experience entries, projects, hobbies)',
  'List',
  '{
    "fields": {
      "items": {
        "type": "array",
        "description": "Array of objects; field keys are defined per service instance in item_schema"
      }
    },
    "item_schema": {
      "type": "array",
      "description": "Array of { key, label, type } field definitions. Set at service creation time.",
      "example": [
        { "key": "company", "label": "Company", "type": "string" },
        { "key": "role",    "label": "Role",    "type": "string" },
        { "key": "period",  "label": "Period",  "type": "string" },
        { "key": "bullets", "label": "Bullets", "type": "tags"   }
      ]
    }
  }'
);
```

### 20.2 — `ServiceCreateRequest` schema update (FastAPI)

When creating a repeater service, the `item_schema` must be provided:

```python
class RepeaterItemField(BaseModel):
    key: str
    label: str
    type: Literal["string", "richtext", "url", "tags"]

class ServiceCreateRequest(BaseModel):
    service_type_slug: str
    service_key: str
    label: str | None = None
    display_order: int = 0
    item_schema: list[RepeaterItemField] | None = None  # required for repeater type
```

On `POST /projects/{slug}/services`, if `service_type_slug == "repeater"`:
- Validate `item_schema` is provided and non-empty
- Store `item_schema` in `project_services` metadata (new JSONB column) OR embed in `content_entries.content` as `{ "_schema": [...], "items": [] }`
- Decision: **embed in content** as `{ "_schema": [...], "items": [] }` — avoids adding a column

### 20.3 — `RepeaterEditor` component (CMS dashboard)

`frontend/src/components/dashboard/editors/RepeaterEditor.tsx`:

```
┌─────────────────────────────────────┐
│  + Add Item                         │
├─────────────────────────────────────┤
│  Item 1                    [↑] [↓] [✕] │
│   Company: _______________          │
│   Role:    _______________          │
│   Period:  _______________          │
│   Bullets: _______________          │
│                                     │
│  Item 2                    [↑] [↓] [✕] │
│   ...                               │
└─────────────────────────────────────┘
```

- Reads `_schema` from `service.content._schema` to know which fields to render
- Stores `{ _schema: [...], items: [...] }` as the content
- `tags` type renders a comma-separated string input, stored as `string[]`
- Reorder via up/down buttons (no drag-and-drop to avoid extra dependencies)

### 20.4 — TypeScript type generation update

In `content.py`, add `repeater` to `_TS_TYPE_MAP`:
```python
"repeater": '{ _type: "repeater"; _label: string; items?: Record<string, unknown>[] }',
```

### 20.5 — `EDITOR_MAP` update

In `frontend/src/components/dashboard/editors/index.ts`:
```typescript
import { RepeaterEditor } from './RepeaterEditor'
export const EDITOR_MAP = {
  ...,
  repeater: RepeaterEditor,
}
```

### Completion checklist
- [x] 20.1 Supabase: INSERT `repeater` into `service_types`
- [x] 20.2 FastAPI: update `ServiceCreateRequest` to accept `item_schema` for repeater
- [x] 20.3 FastAPI: embed `_schema` + `items` in initial content entry when creating repeater service
- [x] 20.4 FastAPI: add `repeater` to `_TS_TYPE_MAP` in `content.py`
- [x] 20.5 Frontend: `RepeaterEditor.tsx` — dynamic fields from `_schema`, add/remove/reorder items
- [x] 20.6 Frontend: add `repeater` to `EDITOR_MAP` in `editors/index.ts`
- [x] 20.7 CMS dashboard: "Add Service" modal passes `item_schema` when repeater type selected

---

## Phase 21 — Auto-Config Agent (AI Website Scanner)

**Goal:** A Claude-powered CLI agent that scans a client website's source code,
identifies hard-coded content, maps it to CMS service types, and produces:
1. A `cms.config.json` ready to drop into the website repo
2. A provisioning manifest (`cms-provision.json`) that the admin uses to create services in the CMS
3. Initial content seeds extracted from the existing constants

### Why this exists

Manually mapping a client website's sections to CMS services is tedious and error-prone.
The agent automates the discovery step — the admin only needs to review the output and
click "provision", not reverse-engineer the codebase.

### Architecture decision

| Decision | Rationale |
|---|---|
| Standalone Python CLI (`backend/agent/scan.py`) | Fast to build; doesn't block the rest of the CMS; runnable in any context |
| Uses Claude API (`claude-sonnet-4-6` via `anthropic` SDK) | Best at code understanding; structured JSON output via tool use |
| Two output files (config + provision) | Config goes into the client website; provision stays with the admin |
| Agent does NOT call the CMS API directly | Admin reviews before provisioning — safety gate |
| Framework detection heuristic | Different fetch patterns for Next.js vs React/Vite vs Astro |

### 21.1 — Install Anthropic SDK in FastAPI venv

```bash
pip install anthropic
```

Add to `backend/auth_service/requirements.txt`.

### 21.2 — Create `backend/agent/` directory

```
backend/agent/
  __init__.py
  scan.py          ← main CLI entrypoint
  prompts.py       ← system prompt + analysis prompt
  file_reader.py   ← walks website directory, reads relevant files
  output_writer.py ← writes cms.config.json and cms-provision.json
  requirements.txt ← anthropic + click
```

### 21.3 — `file_reader.py` — what to read

```python
INCLUDE_EXTENSIONS = {'.ts', '.tsx', '.js', '.jsx', '.vue', '.svelte', '.astro'}
INCLUDE_PATTERNS   = ['constants/', 'data/', 'content/', 'config/', 'lib/', 'src/']
EXCLUDE_PATTERNS   = ['node_modules/', 'dist/', '.next/', '.git/', '__pycache__/', 'venv/']
MAX_FILE_SIZE_KB   = 100  # skip huge generated files
MAX_FILES          = 50   # safety cap
```

Produces a flat dict: `{ "relative/path.ts": "file contents..." }`.

### 21.4 — `prompts.py` — the analysis prompt

The system prompt instructs Claude to:
1. Identify all hard-coded content that a non-developer would want to edit
2. Group content into "services" — each service is one editable section
3. Map each service to one of the known CMS service types
4. For `repeater` services: define the `item_schema` (list of fields)
5. Extract current values as `initial_content`
6. Assign a `service_key` (snake_case, URL-safe) and a human `label`
7. Return a JSON object matching the provisioning manifest schema

Available service types are passed in the prompt (fetched from `GET /admin/service-types` or hard-coded).

Output schema:
```json
{
  "project_slug": "laurian-duma-portfolio",
  "services": [
    {
      "service_key": "cv",
      "service_type_slug": "key_value",
      "label": "Personal Info (CV)",
      "display_order": 1,
      "initial_content": {
        "entries": { "name": "Laurian Duma", "title": "...", "email": "..." }
      }
    },
    {
      "service_key": "experience",
      "service_type_slug": "repeater",
      "label": "Work Experience",
      "display_order": 2,
      "item_schema": [
        { "key": "company", "label": "Company", "type": "string" },
        { "key": "role",    "label": "Role",    "type": "string" },
        { "key": "period",  "label": "Period",  "type": "string" },
        { "key": "bullets", "label": "Bullets", "type": "tags"   }
      ],
      "initial_content": {
        "_schema": [...],
        "items": [{ "company": "...", "role": "...", "period": "...", "bullets": [...] }]
      }
    }
  ],
  "framework": "react-vite",
  "cms_endpoint": "https://cms.romantechnologies.com/content"
}
```

### 21.5 — `scan.py` — CLI interface

```bash
python backend/agent/scan.py --dir "../Laurian Duma - Portofolio Website" --slug "laurian-duma-portfolio"

# Options:
#   --dir         Path to the client website directory (required)
#   --slug        Project slug to use in output config (required)
#   --out         Output directory for generated files (default: same as --dir)
#   --endpoint    CMS content endpoint URL (default: https://cms.romantechnologies.com/content)
#   --provision   After generating, call CMS admin API to create services (requires --api-token)
#   --api-token   Admin JWT for provisioning (only used with --provision)
```

### 21.6 — Output files

**`cms.config.json`** (goes into the client website repo):
```json
{
  "projectSlug": "laurian-duma-portfolio",
  "endpoint": "https://cms.romantechnologies.com/content",
  "services": {
    "cv": "key_value",
    "experience": "repeater",
    "projects": "repeater",
    "hobbies": "repeater",
    "contact_form": "email_config"
  }
}
```

**`cms-provision.json`** (admin keeps this, uses it to provision):
```json
{
  "project_slug": "laurian-duma-portfolio",
  "framework": "react-vite",
  "services": [ ... full service definitions with initial_content ... ]
}
```

### 21.7 — Optional: `--provision` flag

With `--provision`, after generating the manifest the agent:
1. Creates services via `POST /projects/{slug}/services` (one per service)
2. Seeds initial content via `PUT /projects/{slug}/services/{key}` (one per service)
3. Prints a summary: "Created 5 services, seeded 4 with initial content."

Requires `--api-token` (admin's access token) and the project to already exist in the CMS.

### Completion checklist
- [x] 21.1 `pip install anthropic click` → `backend/agent/requirements.txt`
- [x] 21.2 Scaffold `backend/agent/` directory with `__init__.py`
- [x] 21.3 `file_reader.py` — directory walker with extension + path filters
- [x] 21.4 `prompts.py` — system prompt defining service type mappings + output schema
- [x] 21.5 `scan.py` — CLI entrypoint (click), orchestrates file_reader → Claude → output_writer
- [x] 21.6 `output_writer.py` — writes `cms.config.json` and `cms-provision.json`
- [x] 21.7 (Optional) `--provision` flag: calls CMS admin API with generated manifest
- [ ] 21.8 Test on Laurian Duma portfolio; validate Claude's output matches expected services

---

## Phase 22 — Portfolio Website Integration (Laurian Duma)

**Goal:** Connect the Laurian Duma portfolio website to the CMS. Replace hard-coded constants
with live CMS data. Demonstrate the end-to-end flow as the first real client integration.

### Current state of the portfolio

- Framework: React + Vite
- Hard-coded in `src/constants/`: `cv.ts`, `experience.ts`, `projects.ts`, `hobbies.ts`
- Views: `AboutView`, `ExperienceView`, `ProjectsView`, `HobbiesView`, `ContactView`
- No CMS integration yet; skills are hard-coded inside `AboutView.tsx` component

### Planned CMS services (mapped by agent in Phase 21)

| `service_key` | `service_type_slug` | Source file |
|---|---|---|
| `cv` | `key_value` | `src/constants/cv.ts` |
| `skills` | `key_value` | Hard-coded in `AboutView.tsx` (entries map) |
| `experience` | `repeater` | `src/constants/experience.ts` |
| `projects_list` | `repeater` | `src/constants/projects.ts` |
| `hobbies` | `repeater` | `src/constants/hobbies.ts` |
| `hero_image` | `image` | `src/assets/hero.png` |
| `contact_form` | `email_config` | Contact form destination |

### 22.1 — Provision services in CMS

Steps:
1. Create project in Supabase: `INSERT INTO projects (name, slug, user_id, ...)` for Laurian Duma
2. Run agent (Phase 21): `python backend/agent/scan.py --dir "..." --slug "laurian-duma-portfolio" --provision`
3. OR: manually call admin API endpoints to create each service

### 22.2 — Copy `cms-client-template` into portfolio

```
cms-client-template/lib/cms.ts         → [portfolio]/src/lib/cms.ts
cms-client-template/scripts/sync-cms-types.mjs → [portfolio]/scripts/sync-cms-types.mjs
[generated by agent] cms.config.json   → [portfolio]/cms.config.json
```

Adapt `lib/cms.ts` for Vite (no `next: { revalidate }` — use plain `fetch`).

### 22.3 — Create `useCMSContent` React hook

Since the portfolio is React/Vite (client-side), it cannot do server-side fetch with ISR.
Add a React hook to `src/lib/cms.ts`:

```typescript
// src/lib/cms.ts
import { useState, useEffect } from 'react'
import { cmsConfig } from '../../cms.config.json'
import type { CMSContent } from './cms.types'  // generated by npm run cms:sync-types

export function useCMSContent() {
  const [data, setData] = useState<CMSContent | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${cmsConfig.endpoint}/${cmsConfig.projectSlug}`)
      .then(r => {
        if (!r.ok) throw new Error(`CMS fetch failed: ${r.status}`)
        return r.json()
      })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return { data, loading, error }
}
```

### 22.4 — Update views to use CMS data

**`AboutView.tsx`:**
- Remove `import { CV_DATA } from '../constants/cv'`
- Use `useCMSContent()` → `cms.content.cv.entries.name`, `.title`, etc.
- Remove hard-coded `SKILLS` array; use `cms.content.skills.entries`
- Show loading skeleton while fetching

**`ExperienceView.tsx`:**
- Remove `EXPERIENCE` import
- Use `cms.content.experience.items` (typed as repeater items)

**`ProjectsView.tsx`:**
- Remove `PROJECTS` import
- Use `cms.content.projects_list.items`

**`HobbiesView.tsx`:**
- Remove `HOBBIES` import
- Use `cms.content.hobbies.items`

**`ContactView.tsx`:**
- Submit form to `POST https://cms.romantechnologies.com/forms/laurian-duma-portfolio/contact_form`

### 22.5 — Package.json additions

```json
{
  "scripts": {
    "cms:sync-types": "node scripts/sync-cms-types.mjs"
  }
}
```

Add `cms.config.json` (committed). Add `cms.types.ts` to `.gitignore` (generated).

### 22.6 — Loading strategy

Since React/Vite has no SSR, the page renders with skeleton/fallback first.
Use the **stale constant fallback** pattern:
- Default state: hard-coded constants (instant render, no flash)
- After CMS fetch: swap in live data
- Error: silently keep showing the constants (website never breaks if CMS is down)

```typescript
const { data: cms } = useCMSContent()
const name = cms?.content.cv?.entries?.name ?? CV_DATA.name  // fallback to constant
```

This means the portfolio is resilient — it always has content to show.

### Completion checklist
- [x] 22.1 Create Laurian Duma project in CMS Supabase (`projects` table)
- [x] 22.2 Run agent (Phase 21) or manually provision 7 services
- [x] 22.3 Seed initial content from existing constants
- [x] 22.4 Copy and adapt `lib/cms.ts` to `src/lib/cms.ts` (Vite variant with module-level cache)
- [ ] 22.5 Run `npm run cms:sync-types` → write `cms.types.ts`
- [x] 22.6 Update `AboutView.tsx` — cv + skills from CMS with constant fallback
- [x] 22.7 Update `ExperienceView.tsx` — experience from CMS
- [x] 22.8 Update `ProjectsView.tsx` — projects from CMS
- [x] 22.9 Update `HobbiesView.tsx` — hobbies from CMS
- [x] 22.10 Update `ContactView.tsx` — form posts to CMS `/forms/` endpoint
- [ ] 22.11 Test: edit content in CMS dashboard → verify portfolio reflects change

---

## Phase 23 — CMS Client SDK Improvements

**Goal:** Make the `cms-client-template` a polished, framework-agnostic integration kit
usable with Next.js, React/Vite, Astro, or vanilla JS.

### Current state

`cms-client-template/` has:
- `lib/cms.ts` — Next.js-only (uses `next: { revalidate }`)
- `scripts/sync-cms-types.mjs` — good, framework-agnostic
- `cms.config.example.json` and `cms.config.example.ts` — good examples

### What needs to change

#### 23.1 — Framework variants in `lib/cms.ts`

Split into two exported functions:

```typescript
// SSR (Next.js App Router) — uses ISR
export async function getCMSContent(): Promise<CMSContent>

// CSR (React/Vite, Astro client) — plain fetch, no ISR
export async function getCMSContentFresh(): Promise<CMSContent>

// React hook (React/Vite client components)
export function useCMSContent(): { data: CMSContent | null; loading: boolean; error: string | null }
```

The hook is guarded by a comment: "Only use in React projects. Import React separately."

#### 23.2 — Fallback pattern helper

```typescript
// Returns live CMS value or falls back to provided default
export function withFallback<T>(live: T | null | undefined, fallback: T): T {
  return live ?? fallback
}
```

Encourages the resilient pattern from Phase 22.

#### 23.3 — README for `cms-client-template/`

Document:
- What files to copy
- How to configure `cms.config.json`
- How to run `npm run cms:sync-types`
- Next.js example (SSR + ISR)
- React/Vite example (hook + fallback)
- Form submission example

### Completion checklist
- [x] 23.1 `lib/cms.ts` — add `useCMSContent` React hook export
- [x] 23.2 `lib/cms.ts` — add `withFallback` helper
- [x] 23.3 `lib/cms.ts` — ensure `getCMSContentFresh` uses plain fetch (no `next:`)
- [x] 23.4 Write `cms-client-template/README.md` with usage examples per framework
- [x] 23.5 Update `cms.config.example.ts` to show `services` map (useful for TS users)

---

## Revised Implementation Order (Phases 20–23)

```
Phase 20 (Repeater Type)
  ↓
Phase 21 (Auto-Config Agent)    ←── requires repeater to be a valid type
  ↓
Phase 22 (Portfolio Integration) ←── uses agent output; validates full end-to-end flow
  ↓
Phase 23 (SDK Improvements)     ←── polish the client kit based on Phase 22 learnings
```

Run Phase 20 first. Everything else depends on `repeater` being a known service type.
