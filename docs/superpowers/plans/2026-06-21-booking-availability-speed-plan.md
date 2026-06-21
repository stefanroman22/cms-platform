# Booking Availability Speed — Implementation Plan

**Date:** 2026-06-21
**Status:** Implemented (uncommitted) — adversarial review verdict: ship, no confirmed issues
**Design:** [2026-06-21-booking-availability-speed-design.md](../specs/2026-06-21-booking-availability-speed-design.md)
**Branch:** feat/booking-per-staff-dynamic

## Goal

Kill the per-arrow availability delay on samir-kapsalon, speed the shared backend read for all tenants, and — beyond the original design — make the **reusable booking layer fast by default** so future connector-generated client sites inherit the speed instead of re-introducing the per-week refetch.

## Confirmed facts (from the deep-map)

- **samir `BookingForm.tsx`** refetches the visible 7-day week on every arrow click (`useEffect` deps include `weekStart`). It calls the backend **directly** via `NEXT_PUBLIC_BOOKING_API_BASE` (no Next proxy in between).
- **Backend `/{slug}/availability`** (booking.py ~408) is gated by `Depends(_public_read_limit)` — a per-request Postgres rate-limit round-trip — and returns `JSONResponse(content=_range_to_grouped(rng))` with no cache header. The range query `_availability_for_range` is already batched (4 DB round-trips regardless of range length).
- **Next proxy** `frontend/src/app/api/[...path]/route.ts` forces `cache:"no-store"` on **all** requests (line ~38) and forwards only `content-type`/`set-cookie` from upstream — it **drops `Cache-Control`**. Used by tenant #1's widget, not by samir.
- **Reusable layer:** `BookingCalendar.tsx` (embeddable `/w/[slug]` widget) already preloads 120 days. The connector's `lib/booking.ts` template (`scan.py` ~480-537) emits raw API wrappers with **no preload guidance**; Phase 4 integration guide (4.2.e) does not mandate preload-once. samir's `BookingForm` is hand-written, not generated.

## Reasoned deviation from design

Design Section 2 says "preload 56 days" but also "arrows clamp to `[0, MAX_AHEAD_DAYS=182]`". Those conflict: weeks 9–26 would render empty. **Resolution:** preload the full navigable horizon (`MAX_AHEAD_DAYS + WEEK` days) so preload window == navigation window — no empty-beyond-preload gap, existing 6-month browse preserved, now instant. Backend cost is unchanged; payload is sparse (only days-with-slots returned).

## Workstreams

### W1 — samir `BookingForm.tsx`: preload-once (the per-arrow win)
- `components/sections/BookingForm.tsx` availability `useEffect` (~236-263):
  - `from = shopDate(today)`, `to = shopDate(today + (MAX_AHEAD_DAYS + WEEK)d)`.
  - Remove `weekStart` from the dependency array → effect fires only on `(serviceId, barberId)` change.
  - Keep the `alive` race guard (now keyed to service/barber re-selection).
- Arrows (~537-560), `canNextWeek` (~273), day strip (~575-593), `daySlots` (~282): **unchanged** — they already read `slotsByDate` and do pure date math; they become instant once the effect stops depending on `weekStart`.
- No proxy involvement (samir is direct-to-backend); samir's edge caching now comes from W2's `Cache-Control`.

### W2 — Backend `/{slug}/availability`: drop per-read limiter + edge cache
- `backend/auth_service/routers/booking.py`:
  - Remove `dependencies=[Depends(_public_read_limit)]` from **only** the `/{slug}/availability` route (~408). `/config`, `/services`, `/resources`, `/contract` keep it.
  - Add `headers={"Cache-Control": "s-maxage=30, stale-while-revalidate=60"}` to the availability `JSONResponse` (~433).
- Write paths (create/reschedule/cancel) untouched — they remain the double-booking boundary (btree_gist exclusion).

### W3 — Next proxy: honor edge cache for availability GET (tenant #1)
- `frontend/src/app/api/[...path]/route.ts`:
  - Compute `isAvailabilityGet = method === "GET" && targetPath.endsWith("/availability")`.
  - Use `cache: isAvailabilityGet ? "force-cache" : "no-store"` (or `undefined` to inherit) for the upstream fetch.
  - **Pass through** upstream `Cache-Control` to the response **only** for `isAvailabilityGet` (otherwise the edge never sees the directive). All other routes unchanged (still `no-store`, no cache-control passthrough).
- Use exact-segment match (`endsWith`/segment compare), not substring, to avoid `/unavailability` false positives.

### W4 — Reusable layer: fast-by-default for future clients
- `agents/CMS Connector - Website/scan.py` (lib/booking.ts template ~480-537): add a framework-agnostic `getAvailabilityHorizon(serviceId, resourceId?, days?)` helper that fetches the whole horizon **once** and returns `Record<string, string[]>` (date → ISO starts). Zero React/Next coupling so any client framework can use it.
- `agents/CMS Connector - Website/phases/4-integration.md` (4.2.e): mandate preload-once — "fetch the whole horizon once via `getAvailabilityHorizon`; arrows/month nav are pure in-memory date math; never refetch per week/month." Reference `BookingCalendar.tsx` as the canonical pattern.
- `agents/CMS Connector - Website/LEARNINGS.md`: add a CONFIRMED-GOOD rule pinning preload-once as the required availability pattern.
- (Mirror) add the same `getAvailabilityHorizon` helper to samir's `lib/booking.ts` for parity so samir demonstrates the reusable pattern (optional, low-risk).

### W5 — Tests + verification
- **Backend (pytest, runnable here):**
  - New `test_booking_availability_cache.py`: assert `/{slug}/availability` returns `Cache-Control: s-maxage=30, stale-while-revalidate=60`.
  - Same file: assert availability is **not** rate-limited (patch `pg_rate_limit.enforce` to raise 429 → availability still 200, `/config` 429).
  - Existing `test_booking_availability.py` / `test_booking_resource_selection.py` stay green.
- **CMS frontend (vitest, runnable here):** route-handler test that mocks `global.fetch` and asserts availability GET is **not** sent with `cache:"no-store"` and that upstream `Cache-Control` is passed through; a non-availability GET still uses `no-store`.
- **samir (playwright):** spec using `page.route` to count `/availability` requests — exactly one on `(service, barber)` selection, **zero** on arrow clicks. Written; run requires samir dev server + mocked backend (manual/CI).
- **Manual:** samir fast-arrow click-through (no per-arrow spinner); tenant #1 unchanged + edge-cache warm on second load.

## Risks & rollback
- **Staleness (accepted):** availability cached ≤ ~90s (s-maxage 30 + swr 60). A just-booked slot may show briefly; create-time btree_gist still rejects double-books.
- **Rate-limit removal:** availability loses the 120/60s limiter; the edge cache absorbs repeat reads. Write paths keep their limiter. If abuse appears, re-add a lighter limiter or rely on edge.
- **Rollback:** each workstream is independent; revert per file. W1 alone fixes the user-visible samir delay.

## Out of scope
- `_availability_for_range` query optimization (already batched).
- Tenant #1 frontend preload model (already correct).
- Cold-start/serverless warm-up.
- Write-path rate limiting and the double-booking constraint.
