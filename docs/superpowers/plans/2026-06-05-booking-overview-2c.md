# Bookings — Overview / Stats (Phase 2c) Plan

> Design + plan combined (delegated build). Builds on 2a/2b. No DB migration.

**Goal:** An "Overview" tab in the Bookings dashboard with KPIs + charts: bookings over time, by service, by status, cancellation & no-show rates, a day-of-week × hour peak heatmap, and upcoming-load KPI cards.

**Architecture:** A **pure** aggregation function `compute_booking_stats(bookings, now_utc, tz_name)` (no I/O, unit-tested) + a thin owner endpoint that loads the tenant's bookings and returns the stats JSON. Frontend renders it with `recharts` (mirroring `admin/leads/RevenueOverTimeChart` + `BreakdownChart`).

## Backend

### Pure stats module — `backend/auth_service/services/booking_stats.py`
```python
"""Pure booking statistics aggregation (no I/O, unit-tested)."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_UTC = ZoneInfo("UTC")


def compute_booking_stats(bookings: list[dict], *, now_utc: datetime, tz_name: str) -> dict:
    """bookings: rows with status, start_utc (ISO), service_name. Returns KPIs +
    chart series. Times bucketed in the tenant timezone."""
    tz = ZoneInfo(tz_name)
    total = len(bookings)
    active = [b for b in bookings if b["status"] in ("confirmed", "completed")]
    cancelled = [b for b in bookings if b["status"] == "cancelled"]
    no_show = [b for b in bookings if b["status"] == "no_show"]

    by_status = Counter(b["status"] for b in bookings)
    by_service = Counter(b.get("service_name") or "—" for b in bookings)

    by_day: Counter = Counter()
    heat: Counter = Counter()  # key (weekday 0=Mon..6=Sun, hour)
    today = now_utc.astimezone(tz).date()
    week_end = today + timedelta(days=7)
    upcoming = today_count = week_count = 0
    for b in bookings:
        start = datetime.fromisoformat(b["start_utc"]).astimezone(tz)
        by_day[start.date().isoformat()] += 1
        heat[(start.weekday(), start.hour)] += 1
        if b["status"] in ("confirmed", "pending") and start.astimezone(_UTC) >= now_utc:
            upcoming += 1
            if start.date() == today:
                today_count += 1
            if today <= start.date() < week_end:
                week_count += 1

    distinct_days = max(len(by_day), 1)
    return {
        "kpis": {
            "total": total, "upcoming": upcoming, "today": today_count,
            "this_week": week_count, "avg_per_day": round(total / distinct_days, 1),
        },
        "cancellation_rate": round(100 * len(cancelled) / total, 1) if total else 0.0,
        "no_show_rate": round(100 * len(no_show) / total, 1) if total else 0.0,
        "by_day": [{"date": d, "count": c} for d, c in sorted(by_day.items())],
        "by_service": [{"service": s, "count": c} for s, c in by_service.most_common()],
        "by_status": [{"status": s, "count": c} for s, c in by_status.items()],
        "heatmap": [{"weekday": w, "hour": h, "count": c} for (w, h), c in heat.items()],
    }
```

### Tests — `backend/auth_service/tests/test_booking_stats.py`
Pure-function tests: empty → zeros; status counts + cancellation/no_show rates; by_service grouping; by_day bucketing in tz (a UTC time that crosses local midnight buckets to the local day); heatmap weekday/hour; upcoming/today/this_week using a fixed `now_utc`. No mocks needed.

### Endpoint — append to `routers/booking_admin.py`
- `GET /projects/{slug}/bookings/stats?from=&to=` → `_tenant` auth; load the tenant's bookings via a repo helper `booking_admin_repo.list_bookings_for_stats(tenant_id, date_from, date_to)` (select `status, start_utc, booking_services(name)` → flatten `service_name`); `cfg = booking_tenant.load_tenant_by_id`; return `compute_booking_stats(rows, now_utc=datetime.now(UTC), tz_name=cfg.timezone)`. Default range = last 90 days … +90 days if `from`/`to` omitted.
- Repo helper appended to `booking_admin_repo.py`:
```python
def list_bookings_for_stats(tenant_id: str, date_from: str | None, date_to: str | None) -> list[dict]:
    sb = get_supabase_admin()
    q = sb.table("bookings").select("status, start_utc, booking_services(name)").eq("tenant_id", tenant_id)
    if date_from:
        q = q.gte("start_utc", date_from)
    if date_to:
        q = q.lte("start_utc", date_to)
    rows = q.execute().data or []
    for r in rows:
        r["service_name"] = (r.get("booking_services") or {}).get("name")
    return rows
```
- A small endpoint test in `test_booking_admin_router.py` (or the appointments test file): stats endpoint returns the computed shape (mock `list_bookings_for_stats` + `load_tenant_by_id`).

## Frontend

### `components/dashboard/booking/OverviewPanel.tsx` (+ small chart components)
- Add an **Overview** tab to `BookingsSection` (make it first, before Appointments) → `<OverviewPanel projectSlug={slug} />`.
- `booking/api.ts`: add `getStats(slug, from?, to?)` + types (`BookingStats`).
- `OverviewPanel`: `useQuery` the stats; render:
  - **KPI cards** row (total upcoming, today, this week, avg/day) + two rate cards (cancellation %, no-show %) using `dashboardSectionCardCn`.
  - **Bookings over time** — `recharts` AreaChart/LineChart on `by_day` (mirror `RevenueOverTimeChart`).
  - **By service** — BarChart on `by_service`.
  - **By status** — donut (PieChart) on `by_status`.
  - **Peak times heatmap** — a 7×24 grid (CSS grid; cell opacity scaled to count) from `heatmap`; not a recharts chart. Label rows Mon–Sun, columns hours.
  - Empty state when `total === 0`.
- Charts use the existing chart styling (zinc tooltip, responsive container, `motion/react` wrapper as in the leads charts). Reduced-motion respected. Responsive.

## Verify
- Backend: `pytest auth_service/tests/test_booking_stats.py auth_service/tests/test_booking_admin_router.py -v` green; full suite green.
- Frontend: `npx tsc --noEmit` clean; `npm test -- --run` green. (Build at end-of-push milestone.)
- No commit.
