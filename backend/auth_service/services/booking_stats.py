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
    cancelled = [b for b in bookings if b["status"] == "cancelled"]
    no_show = [b for b in bookings if b["status"] == "no_show"]

    by_status = Counter(b["status"] for b in bookings)
    by_service = Counter(b.get("service_name") or "—" for b in bookings)

    # by_staff: count bookings per assigned staff resource, keeping the resolved
    # name. Rows without a resource_id (legacy / generic) are skipped.
    by_staff_count: Counter = Counter()
    staff_names: dict[str, str] = {}
    for b in bookings:
        rid = b.get("resource_id")
        if not rid:
            continue
        by_staff_count[rid] += 1
        staff_names[rid] = b.get("resource_name") or "—"

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
            "total": total,
            "upcoming": upcoming,
            "today": today_count,
            "this_week": week_count,
            "avg_per_day": round(total / distinct_days, 1),
        },
        "cancellation_rate": round(100 * len(cancelled) / total, 1) if total else 0.0,
        "no_show_rate": round(100 * len(no_show) / total, 1) if total else 0.0,
        "by_day": [{"date": d, "count": c} for d, c in sorted(by_day.items())],
        "by_service": [{"service": s, "count": c} for s, c in by_service.most_common()],
        "by_status": [{"status": s, "count": c} for s, c in by_status.items()],
        "by_staff": [
            {"resource_id": rid, "resource_name": staff_names[rid], "count": c}
            for rid, c in by_staff_count.most_common()
        ],
        "heatmap": [{"weekday": w, "hour": h, "count": c} for (w, h), c in heat.items()],
    }
