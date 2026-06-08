# Bookings — Embeddable Widget (Phase 3) Plan

> Design + plan combined (delegated build). Builds on P1 (public API) + P2. **Iframe delivery only** (no separate React package — the iframe works on any site, including your own Next.js client repos). No DB migration.

**Goal:** A copy-paste `<script src=".../embed.js" data-tenant="{slug}">` snippet that drops a branded, auto-resizing booking widget (served from this Next.js app at `/w/{slug}`) onto ANY website; a generalized manage page that works for any tenant; the `/contact` widget cut over to the slug API; and a dashboard "Embed" tab with the snippet + live preview.

**Architecture:** Generalize the existing `BookingCalendar` from tenant-#1/legacy-routes to **slug + service driven**, calling the Phase-1 public API (`/booking/{slug}/...`). A new full-page widget route `/w/[slug]` hosts it (branded via a new public config endpoint) and talks to its iframe parent via `postMessage` (auto-height + `booking_completed`). `/embed.js` is a Next.js route handler returning the loader script. `next.config.ts` header rules are split so `/w/*` + `/embed.js` are embeddable cross-origin while everything else keeps `X-Frame-Options: DENY`.

## Backend (small)

### Append to `routers/booking.py` (public, slug-scoped)
- `GET /booking/{slug}/config` → public-safe branding for the widget. Resolve `booking_tenant.load_tenant_by_slug(slug)` (404 if none); return `{public_slug, business_name, primary_color, accent_color, logo_url, locale}`. (Read these off the TenantConfig; TenantConfig already has business_name, locale; add `logo_url`/`primary_color`/`accent_color` to `TenantConfig` + `_FIELDS` in `booking_tenant.py` if not present — they ARE columns on booking_settings, so extend the dataclass + select list.)
- In `manage_get` (the `GET /booking/manage/{token}` handler), add `"public_slug": cfg.public_slug` and `"service_id": b["service_id"]` to the returned JSON (so the manage-page reschedule picker can fetch availability via `/booking/{slug}/availability?service_id=`).

### `booking_tenant.py`
Add `logo_url`, `primary_color`, `accent_color` to the `TenantConfig` dataclass + `_FIELDS` select + `_to_config` mapping (nullable str). Update the existing `TenantConfig(...)` constructions in tests if they break (they pass kwargs; add the new fields with defaults `None` — make them `str | None = None` with defaults so existing constructions still work — put them at the END of the dataclass with defaults).

### Tests — append to `test_booking_router.py` (or a small new file)
- `GET /booking/{slug}/config` returns branding for a known slug (mock `load_tenant_by_slug`); 404 for unknown.
- `manage_get` response now includes `public_slug` + `service_id` (extend the existing manage test, or add one).

## Frontend

### 1. Generalize `BookingCalendar` (`components/booking/BookingCalendar.tsx`)
New prop shape: `{ slug: string; embedded?: boolean; reschedule?: { token: string; serviceId: string; onDone?: () => void } }`.
- **Booking mode:** on mount, fetch `/api/booking/${slug}/config` (branding) and `/api/booking/${slug}/services`. If exactly one active service → auto-select it; if more → add a leading "pick service" step. Availability: `GET /api/booking/${slug}/availability?service_id=${sid}&from=&to=` → `{days, slots}` (replaces the old `/availability` + `/slots` calls). Create: `POST /api/booking/${slug}` with body `{ service_id, start_utc: selectedSlot, customer: { name, email, phone, tz: displayTz }, note, website }` (honeypot `website`). Success → confirmation screen; if `embedded`, also `window.parent.postMessage({type:'booking_completed', booking_id}, '*')`.
- **Reschedule mode:** availability via `/api/booking/${slug}/availability?service_id=${reschedule.serviceId}&...`; submit `POST /api/booking/manage/${token}/reschedule` body `{ slot_start }` (unchanged).
- **Branding:** apply `config.primary_color`/`accent_color` as inline CSS variables on the widget root (fallback to current zinc/gold theme when null); show `config.business_name` (+ `logo_url` if present) in the header. Keep the existing Motion step transitions, hidden-scrollbar slot list, reduced-motion.
- Keep the component framework-agnostic of tenant #1 — no hardcoded "Stefan"/Roman strings (move any to props/config; default copy can stay generic like "Book an appointment").

### 2. Widget route — `app/(widget)/w/[slug]/page.tsx` (+ minimal layout)
- A standalone, full-bleed page (its own route group/layout WITHOUT the marketing header/footer) that renders `<BookingCalendar slug={slug} embedded />` centered, on a transparent/white background.
- A small client effect posts the document height to `window.parent` via `postMessage({type:'booking_resize', height}, '*')` on mount + on a ResizeObserver, so `embed.js` can auto-size the iframe.
- The page reads `slug` from the route param. If the slug is unknown the widget shows a friendly "booking unavailable" state (the config fetch 404s).

### 3. Loader — `app/embed.js/route.ts` (Next.js Route Handler, GET)
Return `new NextResponse(js, { headers: { "Content-Type": "application/javascript", "Cache-Control": "public, max-age=300" } })` where `js` is a self-executing script that:
- finds its own `<script>` tag (`document.currentScript`), reads `data-tenant`.
- creates a sandboxed `<iframe>` → `${origin}/w/${tenant}` (origin derived from the script `src`), styled width:100%, border:0, and inserts it after the script tag.
- listens for `message` events from the iframe origin: `booking_resize` → set `iframe.style.height`; `booking_completed` → dispatch a `CustomEvent('booking_completed')` on the host document so the host page can react.
Keep it dependency-free, ES5-safe-ish (works on any site).

### 4. Generalize the manage page — `app/(marketing)/manage/[token]/page.tsx`
- It already fetches `/api/booking/manage/${token}`; now also reads `public_slug` + `service_id` from that response and passes them to `<BookingCalendar slug={data.public_slug} reschedule={{ token, serviceId: data.service_id, onDone }} />` in reschedule mode. Remove any tenant-#1 hardcoding; use the returned `name`/`timezone`. (Branding for the manage page can stay neutral; full per-tenant manage branding is P4.)

### 5. `/contact` cutover — `components/.../ContactChannel.tsx` (or wherever `<BookingCalendar/>` is used on /contact)
- Pass tenant #1's slug: `<BookingCalendar slug="roman-technologies-website" />`. This moves the live widget onto the slug API; the legacy `/booking/availability|slots|POST /booking` routes become unused (leave them — harmless backward-compat).

### 6. CSP / headers — `next.config.ts`
Split the `headers()` rules so the embeddable paths are framable:
```typescript
async headers() {
  const embeddable = securityHeaders
    .filter((h) => h.key !== "X-Frame-Options")
    .map((h) => h.key === "Content-Security-Policy"
      ? { key: h.key, value: h.value.replace("frame-ancestors 'none'", "frame-ancestors *") }
      : h);
  return [
    { source: "/embed.js", headers: embeddable },
    { source: "/w/:path*", headers: embeddable },
    // everything else keeps the strict headers (X-Frame-Options: DENY etc.)
    { source: "/((?!w/|embed\\.js).*)", headers: securityHeaders },
  ];
}
```
(Verify the negative-lookahead source compiles with Next's path-to-regexp; if it rejects the literal dot, use `/((?!w/|embed).*)` and accept that `/embed*` is permissive — acceptable.)

### 7. Dashboard "Embed" tab — add to `BookingsSection.tsx`
- New **Embed** tab (after Settings). Shows the snippet (read `public_slug` from settings + `window.location.origin`):
  `<script src="${origin}/embed.js" data-tenant="${public_slug}" async></script>`
  with a copy-to-clipboard button, plus a **live preview** (`<iframe src="/w/${public_slug}" style="width:100%;border:0" />`). Brief instructions ("paste this on any page of the client's site").

## Verify
- Backend: `pytest auth_service/tests/ -q` green (config + manage_get changes; fix any TenantConfig-construction breakage in tests).
- Frontend: `npx tsc --noEmit` clean; `npm test -- --run` green. **Milestone build** `npm run build` succeeds (catches the route-handler + route-group wiring). Manually reason that `/w/{slug}` renders the widget and `/embed.js` returns JS.
- No commit.

## Notes
- Per-tenant email branding + widget i18n strings are **P4** (the widget here is branded by color/name/logo but copy stays English).
- `frame-ancestors *` intentionally lets any site embed the public booking widget (that's the point); the booking actions are already public + rate-limited. Tightening to per-tenant `allowed_origins` is a future enhancement (would need dynamic headers).
