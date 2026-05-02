# Findings — CMS Login System

**Last updated:** 2026-04-13

---

## Phase 18 — Client Website Integration

### The contract: `cms.config.ts`

Every client website repo has exactly one CMS-aware file: `cms.config.ts` in the project root.
It declares which project this website belongs to and which services it uses.

```typescript
// cms.config.ts
export const cmsConfig = {
    projectSlug: "marios-restaurant",
    endpoint: "https://cms.romantechnologies.com/content",
    services: {
        hero:          "text_block",
        hero_image:    "image",
        about_section: "text_block",
        floor_plan:    "floor_plan",
        gallery:       "gallery",
        menu_pdf:      "file_download",
        contact_video: "video",
    },
} as const;

export type ServiceKey = keyof typeof cmsConfig.services;
```

- `projectSlug` must match the slug in the CMS dashboard exactly.
- `services` keys must match the `service_key` values the admin configured.
- `email_config` services are intentionally excluded — they are server-side only.
- This file is the only change needed in a client website to point it at the CMS.

### Setup steps for a new client website

1. Copy `cms-client-template/cms.config.example.ts` → `cms.config.ts`, fill in slug.
2. Copy `cms-client-template/lib/cms.ts` → `lib/cms.ts`.
3. Copy `cms-client-template/scripts/sync-cms-types.mjs` → `scripts/sync-cms-types.mjs`.
4. Add to `package.json`: `"cms:sync-types": "node scripts/sync-cms-types.mjs"`
5. Run `npm run cms:sync-types` — writes `cms.types.ts` with auto-generated TypeScript types.
6. Commit `cms.config.ts`, `lib/cms.ts`, `scripts/sync-cms-types.mjs`.
7. Add `cms.types.ts` to `.gitignore` (it's generated — regenerate on each deploy).

### Fetching content in Next.js (App Router)

```typescript
// app/page.tsx — server component
import { getCMSContent } from '@/lib/cms'

export default async function HomePage() {
    const cms = await getCMSContent()    // ISR: revalidates every 60 s
    return (
        <main>
            <h1>{cms.content.hero.title}</h1>
            <div dangerouslySetInnerHTML={{ __html: cms.content.hero.body ?? '' }} />
            <img src={cms.content.hero_image.url} alt={cms.content.hero_image.alt} />
        </main>
    )
}
```

### TypeScript types sync: `npm run cms:sync-types`

The script `scripts/sync-cms-types.mjs`:
1. Reads `projectSlug` and `endpoint` from `cms.config.ts` (regex parse) or `cms.config.json`.
2. Calls `GET {endpoint}/{slug}/types` on the CMS (public, no auth).
3. Writes the response body to `cms.types.ts`.

The generated file looks like:
```typescript
// Auto-generated — do not edit. Run: npm run cms:sync-types
export interface CMSContent {
  project_slug: "marios-restaurant";
  project_name: string;
  last_updated: string | null;
  content: {
    hero:       { _type: "text_block"; _label: string; title?: string; body?: string };
    hero_image: { _type: "image";      _label: string; url?: string;   alt?: string };
    floor_plan: { _type: "floor_plan"; _label: string; url?: string;   alt?: string };
    gallery:    { _type: "gallery";    _label: string; items?: string[] };
  };
}
```

Run on every deploy to keep types in sync with what the admin has configured.

### CMS API endpoints (public, no auth)

| Endpoint | Description |
|---|---|
| `GET /content/{slug}` | All public content as flat key→fields map |
| `GET /content/{slug}/types` | TypeScript `.d.ts` interface for the project |

Both return `Cache-Control: public, max-age=60, stale-while-revalidate=300` and an `ETag`.
Both allow `Access-Control-Allow-Origin: *`.

### Email form integration (Phase 19)

Contact forms on client websites should NOT call the CMS content endpoint.
Instead, the client website's form POSTs to `POST /forms/{slug}/{form_key}` on the CMS.
The CMS reads the `email_configs` table, sends the email via Resend, returns `{ success: true }`.
This keeps email logic and destinations entirely server-side.

---

---

## Phase 20–23 — Portfolio Integration & Auto-Config Agent (2026-04-14)

### Portfolio Website: Laurian Duma

**Location:** `../Laurian Duma - Portofolio Website/`
**Stack:** React + Vite, TypeScript, Tailwind CSS, Zustand
**Concept:** Ghost Shell OS — simulated desktop UI with draggable windows, taskbar, terminal

**Hard-coded content in `src/constants/`:**

| File | Type | CMS Mapping |
|------|------|-------------|
| `cv.ts` | `CV` object | → `key_value` service (`cv`) |
| `experience.ts` | `ExperienceEntry[]` | → `repeater` service (`experience`) |
| `projects.ts` | `Project[]` | → `repeater` service (`projects_list`) |
| `hobbies.ts` | `Hobby[]` | → `repeater` service (`hobbies`) |
| `AboutView.tsx` SKILLS | hard-coded array | → `key_value` service (`skills`) |
| `ContactView.tsx` form | no backend yet | → `email_config` service (`contact_form`) |
| `src/assets/hero.png` | local asset | → `image` service (`hero_image`) |

**Key types from `src/types/content.ts`:**
```typescript
CV         = { name, title, summary, email, github, linkedin }
ExperienceEntry = { id, company, role, period, bullets: string[] }
Project    = { id, name, description, tags: string[], url?, repo? }
Hobby      = { id, name, description, icon }
```

### Critical Gap Discovered: No `repeater` Service Type

Current service types only handle flat data or single assets. Arrays of structured objects
require a new `repeater` type. Without it, `experience`, `projects`, and `hobbies` cannot
be stored in the CMS in any meaningful, editable way.

**Repeater content schema:**
```json
{
  "_schema": [
    { "key": "company", "label": "Company", "type": "string" },
    { "key": "role",    "label": "Role",    "type": "string" },
    { "key": "period",  "label": "Period",  "type": "string" },
    { "key": "bullets", "label": "Bullets", "type": "tags"   }
  ],
  "items": [
    { "company": "Company Name", "role": "Senior Engineer", ... }
  ]
}
```

The `_schema` is embedded in `content_entries.content` at creation time — no new DB column needed.

### CMS Platform: What Already Exists (confirmed complete)

1. **Multi-tenant content API** — `GET /content/{slug}` is public, has ETag + Cache-Control, `Access-Control-Allow-Origin: *`. Any external website can call it. ✅
2. **TypeScript types API** — `GET /content/{slug}/types` generates `.d.ts` for the project. ✅
3. **cms-client-template** — has `lib/cms.ts`, `sync-cms-types.mjs`, config examples. ✅
4. **File uploads** — Supabase Storage via `/projects/{slug}/services/{key}/upload`. ✅
5. **Email forms** — `POST /forms/{slug}/{key}` via Resend. ✅
6. **Admin service management** — `POST/DELETE /projects/{slug}/services`. ✅
7. **Dashboard editors** — all 8 current service types have UI editors. ✅

### Auto-Config Agent Design

The agent is a Python CLI (`backend/agent/scan.py`) using the Anthropic SDK.

**Input:** path to client website directory + desired project slug
**Output:** two JSON files:

1. `cms.config.json` — drops into the website repo (projectSlug + services map)
2. `cms-provision.json` — admin uses this to see what services need to be created (includes `initial_content`)

**Agent workflow:**
```
1. Walk directory → read .ts/.tsx/.js/.jsx/.vue/.svelte files
   (exclude: node_modules/, dist/, .next/, .git/)
2. Send file contents to Claude (claude-sonnet-4-6) with structured output prompt
3. Claude identifies editable content, maps to service types, defines item_schema for repeaters
4. Agent writes cms.config.json + cms-provision.json
5. Optional --provision flag: calls admin API to create services + seed content
```

**Claude prompt strategy:**
- System prompt defines all 9 service types (including `repeater`) with examples
- User message includes all file contents + desired slug
- Output is JSON matching the provisioning manifest schema
- Use tool_use / structured output to guarantee valid JSON

### Fetch Strategy: React/Vite vs Next.js

| Framework | Fetch pattern | CMS helper to use |
|-----------|--------------|-------------------|
| Next.js App Router | Server component + ISR | `getCMSContent()` with `next: { revalidate: 60 }` |
| React/Vite (CSR) | `useEffect` hook | `useCMSContent()` (to be added in Phase 23) |
| Astro | SSR or SSG | `getCMSContentFresh()` |

**Fallback pattern (resilient client websites):**
```typescript
const { data: cms } = useCMSContent()
const name = cms?.content.cv?.entries?.name ?? CV_DATA.name  // constant fallback
```

Websites should always fall back to their hard-coded constants so they render correctly
even if the CMS API is unreachable. The CMS enhances — it doesn't break.

### Provisioning Flow (end-to-end)

```
Admin runs: python backend/agent/scan.py --dir "..." --slug "laurian-duma-portfolio"
  ↓
Agent generates cms.config.json + cms-provision.json
  ↓
Admin reviews cms-provision.json (optional)
  ↓
Admin runs with --provision flag (or manually calls API)
  ↓
CMS creates project + services in Supabase
  ↓
CMS seeds content from initial_content in provision manifest
  ↓
Developer copies cms.config.json + lib/cms.ts into website
  ↓
Developer runs `npm run cms:sync-types` → gets cms.types.ts
  ↓
Developer replaces hard-coded imports with useCMSContent() + fallback
  ↓
Client logs into CMS dashboard, edits content
  ↓
Website fetches fresh data (max 60s delay via Cache-Control)
```

---

## Existing Frontend

- Login page: `frontend/src/app/log-in/page.tsx`
  - Has email + password fields, remember me checkbox, password toggle
  - Currently uses a mock 1500ms delay; accepts any input
  - No real API call wired up
- Button component: `frontend/src/components/ui/button.tsx` — reusable with loading state
- No auth context, no middleware, no protected routes yet

## Existing Backend

- Django 6.0.2 + DRF 3.16.1
- `backend/core/settings.py` — CORS already configured for localhost:3000
- DB: currently SQLite — must migrate to Supabase PostgreSQL for production
- `core/urls.py` — only Django admin wired up, no auth endpoints
- No FastAPI service exists yet — must scaffold from scratch

## Supabase Integration Notes

- Supabase project name: **CMS**
- Supabase MCP is connected to the antigravity configuration — tables can be created directly via MCP tools
- Use `supabase-py` (official Python client) in FastAPI to query the `users` table
- For Django, connect directly via PostgreSQL connection string (psycopg2) — more efficient than HTTP API for ORM queries
- Supabase connection string format: `postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres`

### Tables to create in Supabase

**`users`**
```sql
CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email       TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,           -- Argon2id hash
  full_name   TEXT,
  is_active   BOOLEAN DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_users_email ON users(email);
```

**`projects`**
```sql
CREATE TABLE projects (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  description TEXT,
  slug        TEXT UNIQUE NOT NULL,
  is_active   BOOLEAN DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_projects_user_id ON projects(user_id);
```

**`refresh_tokens`** (for revocation/blacklisting)
```sql
CREATE TABLE refresh_tokens (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  TEXT UNIQUE NOT NULL,      -- SHA-256 hash of the token
  expires_at  TIMESTAMPTZ NOT NULL,
  revoked     BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
```

## JWT Strategy

- **RS256** (asymmetric): FastAPI holds `private.pem` (signs), Django holds `public.pem` (verifies)
- Access token: 15 minutes (short-lived, stored in memory or HttpOnly cookie)
- Refresh token: 7 days (no remember me) / 30 days (remember me) — stored in HttpOnly cookie
- Refresh token stored in Supabase `token_blacklist` table for revocation support

## Token Storage: Cookies vs localStorage

| Method | XSS Risk | CSRF Risk | Notes |
|---|---|---|---|
| localStorage | HIGH (JS can read) | None | Not recommended for auth |
| HttpOnly Cookie | None (JS can't read) | Possible (mitigated with SameSite) | **Recommended** |

Decision: HttpOnly cookies with `SameSite=Strict` and `Secure` flag.

## Password Hashing

- **Chosen algorithm: Argon2id** — current gold standard, winner of the 2015 Password Hashing Competition
- Resistant to GPU brute-force AND side-channel attacks (better than bcrypt/scrypt for both)
- FastAPI will use `argon2-cffi` library for hashing and verification
- Passwords stored in Supabase `users` table as `password_hash` (Argon2id string format)
- Argon2id parameters: memory=64MB, iterations=3, parallelism=4 (OWASP recommended minimums)

## CORS Configuration

- FastAPI must allow `http://localhost:3000` with `allow_credentials=True` (required for cookies)
- Django already has CORS configured — extend to also allow cookie credentials

## Rate Limiting

- Use `slowapi` library for FastAPI (wraps `limits` package)
- Recommended: 5 login attempts per IP per 15 minutes

## Dashboard Architecture Findings

### Current State
- `/dashboard/page.tsx` — exists, basic, uses `useLoading` context + Framer Motion fade-in. Has user email + project cards. Already imports `motion` from framer-motion.
- Root `layout.tsx` wraps **everything** (including dashboard) with Header + Footer — this must be bypassed for dashboard routes
- `context/loading.tsx` — LoadingContext with show/hide. Used by dashboard for loading overlay.

### Layout Bypass Strategy
Next.js App Router supports **route group layouts**. Creating `frontend/src/app/dashboard/layout.tsx` (a nested layout) will override what's rendered inside `/dashboard/*` — but the root layout still runs. To suppress Header/Footer for dashboard routes, the root layout needs to conditionally hide them.

Best approach: use a **route group** `(marketing)` for the public site (wraps Header/Footer) and `(app)` for the dashboard. This avoids conditional rendering hacks. But this would require moving existing routes.

**Simpler approach (no file moves):** In `frontend/src/app/layout.tsx`, wrap Header/Footer in a client component that reads `pathname` and skips rendering if pathname starts with `/dashboard`. This is clean and requires minimal changes.

### Framer Motion — AnimatePresence for Page Transitions
Current dashboard page already uses `motion.div`. For cross-page fade transitions:
- Wrap page content in `<motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}>`
- In `dashboard/layout.tsx`, wrap `{children}` with `<AnimatePresence mode="wait">`
- Need a `key` prop on the motion wrapper — use `usePathname()` as the key

### Theme Tokens (Light Dashboard)
```
Background:    bg-white / bg-zinc-50
Surface cards: bg-white border border-zinc-200
Text primary:  text-zinc-900
Text muted:    text-zinc-500
Sidebar bg:    bg-zinc-50 border-r border-zinc-200
Active nav:    bg-zinc-900 text-white
Hover nav:     hover:bg-zinc-100
```

### Sidebar Design
- Width: `w-64` (256px) on desktop, hidden on mobile (hamburger menu)
- Fixed height, full viewport: `h-screen sticky top-0`
- Top: logo/brand
- Middle: nav items with icons (lucide-react)
- Bottom: user email + sign out button

### New Supabase Table Needed
`project_requests` — client enquiry form submissions:
```sql
CREATE TABLE project_requests (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  type         TEXT NOT NULL,  -- 'website' | 'web_app' | 'mobile_app' | 'other'
  description  TEXT NOT NULL,
  budget_range TEXT,
  timeline     TEXT,
  status       TEXT DEFAULT 'pending',  -- 'pending' | 'reviewed' | 'approved'
  created_at   TIMESTAMPTZ DEFAULT NOW()
);
```

### New FastAPI Endpoint Needed
`POST /auth/change-password` — for Account Settings:
- Body: `{ current_password, new_password }`
- Verify current password against Supabase hash
- Hash new password (Argon2id)
- Update `users.password_hash` in Supabase

## Files to Create

```
backend/
  auth_service/
    main.py           ← FastAPI app entry point
    routers/
      auth.py         ← /auth/login, /auth/refresh, /auth/logout, /auth/me
    services/
      auth_service.py ← business logic (verify password, issue tokens)
      supabase.py     ← Supabase client singleton
    models/
      schemas.py      ← Pydantic models (LoginRequest, TokenResponse, UserOut)
    core/
      config.py       ← settings from env vars
      security.py     ← JWT sign/verify with RS256
    requirements.txt
    .env.example

  core/               ← existing Django project
    authentication.py ← new: JWTAuthentication class for DRF

  projects/           ← new Django app
    models.py         ← Project model
    views.py          ← ProjectListView
    urls.py
    serializers.py

frontend/src/
  lib/
    auth.ts           ← login(), logout(), getMe() helpers
  middleware.ts       ← Next.js route protection
  app/
    dashboard/
      page.tsx        ← protected projects page
```

---

## Phase 11 — Dashboard Theme Switching Research

### Current state of theming

- `globals.css` body background is `#000000` (public site is dark-first), but dashboard components all use light-theme Tailwind classes (`bg-white`, `text-zinc-900`, etc.)
- Tailwind version: **v4** — uses `@import "tailwindcss"` and `@theme inline {}` syntax, NOT a `tailwind.config.ts`
- No theme library installed (`next-themes` is NOT in `package.json`)
- No dark mode currently configured anywhere

### Tailwind v4 dark mode scoping

In Tailwind v4 the dark variant is configured via `@custom-variant` in CSS:

```css
/* Scope dark: utilities to any element inside a [data-theme=dark] ancestor */
@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));
```

This means `dark:bg-zinc-900` only fires when the element has a `[data-theme=dark]` ancestor — completely isolated from the public site.

### Where to apply `data-theme`

`dashboard/layout.tsx` renders a flex wrapper containing `<Sidebar>` and the content div. A thin `ThemeShell` client component sits here, reads the theme from context, and applies `data-theme={theme}` to that wrapper div plus `suppressHydrationWarning` (to prevent mismatch when localStorage differs from server-render default).

### Context / localStorage pattern

Existing contexts: `auth.tsx`, `loading.tsx`, `user.tsx` — all follow the same `createContext` + custom hook pattern. `ThemeContext` follows the same pattern: reads `localStorage.getItem("dashboard-theme")` on mount (guarded by `typeof window !== "undefined"`), stores `"light" | "dark"`, exposes `toggleTheme()`.

### No flash on load

`suppressHydrationWarning` on the wrapper div suppresses the React hydration mismatch warning. The div's `data-theme` will be set to `"light"` on server and corrected to localStorage value on client mount — the flash window is <1 frame and invisible in practice since the dashboard requires a navigation.

### Toggle UI

Framer Motion is already installed (`framer-motion ^12`). The toggle can use a `layout`-animated indicator that slides between "Light" and "Dark" slots — no extra animation library needed.

### Files that need dark: variants added

| File | Reason |
|---|---|
| `lib/styles.ts` | All dashboard constants need dark: variants appended |
| `components/dashboard/Sidebar.tsx` | Hardcoded light colors throughout |
| `components/dashboard/PageHeader.tsx` | `text-zinc-900` heading, `text-zinc-500` subtitle |
| `components/dashboard/FormField.tsx` | uses `dashboardInputCn` (via constant) + label |
| `components/dashboard/FormFeedback.tsx` | uses error/success constants |
| `app/dashboard/page.tsx` | search input, project cards, skeleton, empty state |
| `app/dashboard/account/page.tsx` | Row component, section card header, edit buttons |
| `app/dashboard/new-project/page.tsx` | success card, textarea, secondary button |

---

## Phase 12–19 Research — CMS Content Services Architecture

### Design goal recap

One platform, many client websites. Each client website:
1. Has one config file (`cms.config.ts`) declaring which services it uses
2. Fetches all its content from one public endpoint: `GET /content/{project_slug}`
3. Submits contact forms to one endpoint: `POST /forms/{project_slug}/{form_key}`

The CMS admin (stefanromanpers@gmail.com) provisions services for each project via the dashboard.

---

### Option A: Git-connected CMS (Contentful-style) — REJECTED

Store content as JSON files in the client website's git repo; CMS pushes commits. Rejected because:
- Requires GitHub/Git API integration, OAuth, webhooks
- Couples CMS to deployment pipeline
- Content updates require deploys → too slow for operational content (email addresses, floor plans)
- Complexity far exceeds benefit for a small-scale platform

### Option B: Per-client Supabase projects — REJECTED

Create a separate Supabase project per client. Rejected because:
- Free tier: only 2 projects; paid per project
- No shared auth; admin cannot see all clients from one backend
- Infrastructure overhead not justified

### Option C: One Supabase project, shared schema, service plugin architecture — CHOSEN

Single Supabase project owns all data. Service types are registered plugins. Each project instance declares which services it uses and stores content as JSONB.

**Advantages:**
- One backend serves all clients — O(1) operational complexity regardless of client count
- Adding a new client = one INSERT into `projects` + INSERTs into `project_services`
- Adding a new service type = one INSERT into `service_types` (no code changes)
- All files in one Supabase Storage bucket with path-based isolation
- Admin sees everything from one dashboard

---

### Supabase Schema Design (Final)

```
users                          (existing)
  id, email, password_hash, full_name, is_admin, created_at

projects                       (existing + new columns)
  id, user_id, name, description, slug, is_active,
  website_url, allowed_origins[], api_key, created_at

service_types                  (new — plugin registry)
  slug PK, name, description, icon, schema JSONB, created_at

project_services               (new — project ↔ service instances)
  id, project_id FK, service_type_slug FK, service_key, label, display_order

content_entries                (new — actual content per service instance)
  id, project_service_id FK (UNIQUE), content JSONB, updated_at, updated_by FK

email_configs                  (new — email destinations, not in public API)
  id, project_service_id FK (UNIQUE), destination_email, updated_at, updated_by

project_requests               (existing)
  id, user_id, name, type, description, budget_range, timeline

refresh_tokens                 (existing)
  id, user_id, token_hash, expires_at, revoked, remember_me
```

---

### Public Content API Response Format

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
      "url": "https://[supabase]/storage/v1/object/public/cms-files/marios-restaurant/hero_image/abc123.jpg",
      "alt": "Restaurant interior"
    },
    "floor_plan": {
      "_type": "floor_plan",
      "_label": "Floor Plan",
      "url": "https://...",
      "alt": "Dining room layout"
    }
  }
}
```

Key rules:
- `email_config` services NEVER appear in the public response
- `_type` and `_label` are always present (meta, not content)
- Content fields are merged from `content_entries.content JSONB` at the top level
- `last_updated` is the MAX of all `content_entries.updated_at` for this project

---

### File Storage Strategy

Supabase Storage bucket: `cms-files`
- **Policy:** Public read (no auth needed to fetch files)
- **Policy:** Authenticated write (only backend service role key can write)
- **Path structure:** `/{project_slug}/{service_key}/{uuid}.{ext}`
- **Example:** `marios-restaurant/floor_plan/a1b2c3d4.jpg`

Why UUID in filename:
- Prevents browser cache stale reads when file is replaced (new URL = fresh fetch)
- No collision risk on concurrent uploads

Why NOT delete old files automatically:
- If content entry is rolled back, old URL still works
- Storage is cheap; cleanup can be a periodic admin job

---

### Service Plugin Schema Convention

Each `service_types.schema` JSONB describes the fields the service stores:

```json
{
  "fields": {
    "title": { "type": "string", "label": "Title", "required": true },
    "body":  { "type": "richtext", "label": "Body text", "required": false }
  }
}
```

Field types: `string`, `email`, `richtext`, `file`, `file[]`, `url`, `object`

This schema drives:
1. The editor UI (which input component to render per field)
2. TypeScript type generation for client websites
3. Validation on save

---

### `cms.config.ts` Specification

```typescript
// cms.config.ts — place in client website project root
// This is the ONLY CMS-aware file in a client website repo.

export const cmsConfig = {
  // Must match projects.slug in the CMS database
  projectSlug: "marios-restaurant",

  // Base URL of the CMS content API
  endpoint: "https://cms.romantechnologies.com/content",

  // Declares which services this site uses.
  // Keys must match project_services.service_key in the database.
  // Values are the service_type_slug (for TypeScript type safety).
  services: {
    hero:           "text_block",
    hero_image:     "image",
    about_section:  "text_block",
    floor_plan:     "floor_plan",
    gallery:        "gallery",
    menu_pdf:       "file_download",
  }
} as const

export type ServiceKey = keyof typeof cmsConfig.services
```

---

### Email Form Handler Research

Options considered:

| Provider | Free Tier | SDK | Verdict |
|---|---|---|---|
| Resend | 3,000/month | Python SDK ✓ | **CHOSEN** |
| SendGrid | 100/day | Python SDK ✓ | Too low for bursts |
| AWS SES | 62,000/month (from EC2) | boto3 | Overkill, AWS dependency |
| SMTP (Gmail) | 500/day | smtplib | No reliability, no analytics |

Resend setup: `pip install resend`, env var `RESEND_API_KEY`, `from` address = `noreply@romantechnologies.com`

---

### Admin Role Implementation

Simplest approach: `is_admin` boolean on `users` table.

Why not a roles/permissions table:
- Only two roles exist: admin and client
- RBAC adds 3+ tables and significant query complexity
- `is_admin` is read once on login and embedded in the JWT — zero overhead per request

Admin enforcement in FastAPI:
```python
async def require_admin(current_user: UserOut = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
```

---

### Django vs FastAPI for CMS Content

Current Django backend (`backend/` running on port 8000) is unused after the migration in Phase 4. The `projects/` app remains as dead code.

**Decision: migrate remaining CMS routes to FastAPI and deprecate Django entirely.**
- All routes (`/projects`, `/account`, `/project-requests`) already exist in FastAPI `routers/projects.py`
- Django is only alive for historical reasons; it adds ~200MB of dependencies and a separate process
- New routes (content API, forms, file upload) belong in FastAPI
- Django can be deleted when Phase 12 begins
