# Booking Availability Speed — Design

**Date:** 2026-06-21
**Status:** Approved (design)
**Scope:** Make public booking availability load faster, especially week-to-week date navigation on samir-kapsalon, without weakening double-booking correctness.

## Problem

Public booking has two distinct slow paths:

1. **samir-kapsalon (`calendar_provider="none"`)** — the booking form refetches the *visible 7-day week* on **every** arrow click. There is no cache, no prefetch, no debounce. Result: "very big delay, especially when the user uses the arrows to change between dates… needs to wait to see the dates become available." Once a day is selected, *times* render instantly (they are already in memory for that week) — confirming the bottleneck is **day/date-range availability**, not slot computation.

2. **roman-technologies.dev (tenant #1, `calendar_provider="google"`)** — booking "takes some time to load." Its CMS widget already preloads a wide horizon once, so the slowness is the single cold-start preload plus per-read overhead, not per-navigation refetching.

### Root-cause asymmetry (confirmed by reading the code)

- `frontend/src/components/booking/BookingCalendar.tsx` (CMS widget, tenant #1) **preloads ~120 days in one request** on selection (`loadAllAvailability`, ~lines 169–207), then `changeMonth` is pure date math (~258–262) and `pickDay` reads `slotsByDate.get(...)` (~264–269). **This frontend is already correct.**
- `samir-kapsalon/components/sections/BookingForm.tsx` fetches only the visible week (`useEffect` ~234–263, dependency `weekStart`). Each arrow handler (~537–561) mutates `weekStart`, which fires a **fresh network request**. The `alive` flag (~241/261) guards races but does not abort.

The backend range query is **already efficient**: `_availability_for_range` (booking.py ~239) does ~4 DB round-trips per range (+ optional Google Calendar fetch when `provider="google"`), then a pure-Python per-day loop with **no per-day DB hits**. So the latency is dominated by **network round-trips on a cold serverless function plus a per-read rate-limit round-trip**, not query cost.

**Therefore the fix is frontend caching (samir) + per-read overhead reduction (all tenants), not query optimization.**

## Decisions

- **Staleness tradeoff (accepted):** availability reads may be cached ~30–60s. A slot booked seconds ago may briefly still show as free. This is safe because the **create** call still enforces the `btree_gist` exclusion on `(resource_id, guard_range)` and rejects double-books at write time.
- **Approach A (samir frontend):** adopt the CMS widget's preload-once model.
- **Approach C (backend/edge/proxy):** reduce per-read overhead for the availability read only.
- **Tenant #1 frontend is left untouched** — it already preloads once. Only Approach C touches its read path (shared backend).

## Section 1 — Architecture & Data Flow (approved)

Two independent changes, no shared new code:

1. **samir `BookingForm.tsx`** stops being week-scoped. On `(service, resource)` selection it issues **one** availability request for a wide horizon and holds the whole horizon in memory. Arrows become pure date math over the in-memory map. Day selection is an in-memory lookup.

2. **Backend `/availability` read** drops the per-read Postgres rate-limit round-trip and emits an edge `Cache-Control` header so Vercel's edge serves repeat reads. The Next.js catch-all proxy stops forcing `cache:"no-store"` on availability GETs so the edge cache is actually honored.

Write endpoints (create/reschedule/cancel) are **unchanged** — they keep the rate limiter and remain the correctness boundary.

## Section 2 — Component Responsibilities

- **samir `BookingForm.tsx`** (Approach A target):
  - Preload horizon: **56 days (8 weeks)** in a single request on `(service, resource)` selection.
  - Build `slotsByDate: Map<string, string[]>` (date → slot start times) and `bookableDays: Set<string>` (days with ≥1 slot) once per preload.
  - Remove `weekStart` from the fetch effect's dependency list; arrows mutate only the in-memory `weekStart` window (`weekStart ± 7`, clamped to `[0, MAX_AHEAD_DAYS]`) with **zero network**.
  - Day pick reads `slotsByDate.get(date)` (already the pattern, ~line 282).
  - Replace the per-week `alive` race guard with a single preload guard (AbortController / `alive`) keyed to `(service, resource)` re-selection.

- **CMS widget `BookingCalendar.tsx`** (tenant #1): **untouched.** Already preloads 120 days once.

- **Backend `booking.py` `/availability`** (Approach C):
  - Remove `dependencies=[Depends(_public_read_limit)]` from the `/{slug}/availability` route (booking.py ~408). The other public reads (`/config`, `/services`, `/resources`, `/contract`) keep it.
  - Add `headers={"Cache-Control": "s-maxage=30, stale-while-revalidate=60"}` to the availability `JSONResponse`.

- **Next proxy `frontend/src/app/api/[...path]/route.ts`** (~line 38): stop sending `cache:"no-store"` for availability GET requests so the edge `Cache-Control` is honored. Non-GET and non-availability requests keep their current behavior.

## Section 3 — Detailed Data Flow (samir, new)

1. User selects service → selects barber (or "No preference").
2. `(service, resource)` change triggers **one** `GET {BASE}/booking/samir-kapsalon/availability?service_id=…&from={today}&to={today+55d}&resource_id=…`.
3. Response (grouped by date) is folded into `slotsByDate` + `bookableDays` once.
4. The week strip renders from `bookableDays` for the current `weekStart` window.
5. **Arrow click** → `weekStart ± 7` (clamped) → re-render from the in-memory map. **No request.**
6. **Day click** → `slotsByDate.get(date) ?? []` → times render instantly.
7. **Submit** → unchanged create call; still authoritative for double-booking.

Edge cache behavior (all tenants): first read for an `(slug, service, resource, from, to)` tuple hits the function; subsequent identical reads within `s-maxage=30` are served from the edge; for the next 60s `stale-while-revalidate` serves stale instantly while revalidating in the background.

## Section 4 — Error Handling

- **Preload request fails:** show the existing error/empty state; offer retry (re-trigger the preload). Do not fall back to per-week fetching.
- **Race / re-selection:** a single `alive`/AbortController guard tied to `(service, resource)`; if the user changes service or barber mid-flight, the in-flight preload is ignored/aborted.
- **Stale slot already booked:** handled by the existing create-conflict path (write-time `btree_gist` rejection → user re-picks). No new handling.
- **Empty horizon (no availability in 56 days):** existing "no availability" messaging; arrows still work (all weeks simply show no bookable days).
- **Beyond the 56-day horizon:** `MAX_AHEAD_DAYS` clamp already bounds navigation; if policy allows booking past 56 days in future, that is out of scope here (current samir horizon is well within 56 days).

## Section 5 — Testing Strategy

- **Backend (`booking.py`):**
  - Assert the `/availability` response carries `Cache-Control: s-maxage=30, stale-while-revalidate=60`.
  - Assert `/availability` no longer enforces `_public_read_limit` (rapid repeated reads do not 429), while `/config`/`/services`/`/resources` still do.
  - Existing availability-correctness tests stay green (grouping, per-resource, no-preference).

- **samir `BookingForm.tsx`:**
  - Assert exactly **one** availability request fires on `(service, resource)` selection.
  - Assert **zero** network on arrow clicks.
  - Assert `slotsByDate` / `bookableDays` are built correctly from a mocked grouped response.
  - Assert day pick reads from the in-memory map.

- **Next proxy `route.ts`:** assert availability GETs are not sent with `cache:"no-store"`; other routes unchanged.

- **Manual:** prod-like click-through on samir (fast arrow navigation, no per-arrow spinner) and tenant #1 (unchanged behavior, edge cache warm on second load).

## Out of Scope

- Query optimization of `_availability_for_range` (already batched).
- Changing tenant #1's frontend preload model.
- Cold-start elimination (serverless warm-up) — a separate, larger effort.
- Any change to write-path rate limiting or the double-booking constraint.
