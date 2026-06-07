"""Pure multi-resource availability math for booking — no I/O, fully unit-tested.

All instants in and out are tz-aware UTC. Working hours are tenant-local `time`s
converted to UTC per day (DST-aware via zoneinfo). A booking occupies a *guard*
interval = [start - buffer_before, start + duration + buffer_after); a slot is
free on a resource when its guard interval overlaps none of that resource's
existing guard intervals. A slot is OFFERED when >= 1 eligible resource is free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

_UTC = ZoneInfo("UTC")

# Window/interval = (start_utc, end_utc), both tz-aware UTC.
Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class ResourceAvailability:
    """One eligible resource's inputs for a single day."""

    resource_id: str
    hours: list[tuple[time, time]]  # local opening hours for this weekday
    exception: dict | None  # {"is_closed", "start_time", "end_time"} or None
    busy: list[Interval] = field(default_factory=list)  # existing guard intervals (UTC)


def open_windows_utc(
    *, day: date, tz_name: str, hours: list[tuple[time, time]], exception: dict | None
) -> list[Interval]:
    """Open intervals for `day` in UTC. `exception` (if given) overrides: closed
    => [] ; custom start/end => replaces `hours`."""
    if exception is not None:
        if exception.get("is_closed"):
            return []
        if exception.get("start_time") and exception.get("end_time"):
            hours = [(exception["start_time"], exception["end_time"])]
    tz = ZoneInfo(tz_name)
    out: list[Interval] = []
    for start_t, end_t in hours:
        s = datetime.combine(day, start_t, tzinfo=tz).astimezone(_UTC)
        e = datetime.combine(day, end_t, tzinfo=tz).astimezone(_UTC)
        if e > s:
            out.append((s, e))
    return out


def _candidate_starts(
    *, windows: list[Interval], duration_min: int, granularity_min: int
) -> list[datetime]:
    starts: list[datetime] = []
    for w_start, w_end in windows:
        cursor = w_start
        while cursor + timedelta(minutes=duration_min) <= w_end:
            starts.append(cursor)
            cursor += timedelta(minutes=granularity_min)
    return starts


def _guard(
    start_utc: datetime, *, duration_min: int, buffer_before_min: int, buffer_after_min: int
) -> Interval:
    return (
        start_utc - timedelta(minutes=buffer_before_min),
        start_utc + timedelta(minutes=duration_min + buffer_after_min),
    )


def _overlaps_any(interval: Interval, busy: list[Interval]) -> bool:
    g0, g1 = interval
    return any(b0 < g1 and g0 < b1 for (b0, b1) in busy)


def _free_starts_for_resource(
    *,
    day: date,
    tz_name: str,
    res: ResourceAvailability,
    duration_min: int,
    buffer_before_min: int,
    buffer_after_min: int,
    granularity_min: int,
) -> set[datetime]:
    windows = open_windows_utc(day=day, tz_name=tz_name, hours=res.hours, exception=res.exception)
    free: set[datetime] = set()
    for s in _candidate_starts(
        windows=windows, duration_min=duration_min, granularity_min=granularity_min
    ):
        g = _guard(
            s,
            duration_min=duration_min,
            buffer_before_min=buffer_before_min,
            buffer_after_min=buffer_after_min,
        )
        if not _overlaps_any(g, res.busy):
            free.add(s)
    return free


def available_starts(
    *,
    day: date,
    now_utc: datetime,
    tz_name: str,
    duration_min: int,
    buffer_before_min: int,
    buffer_after_min: int,
    granularity_min: int,
    lead_time_min: int,
    max_advance_days: int,
    resources: list[ResourceAvailability],
) -> list[datetime]:
    """Sorted unique UTC starts where >= 1 eligible resource is free, after
    lead-time and max-advance filters."""
    today_host = now_utc.astimezone(ZoneInfo(tz_name)).date()
    if day < today_host or day > today_host + timedelta(days=max_advance_days):
        return []
    earliest = now_utc + timedelta(minutes=lead_time_min)
    horizon = now_utc + timedelta(days=max_advance_days)
    union: set[datetime] = set()
    for res in resources:
        union |= _free_starts_for_resource(
            day=day,
            tz_name=tz_name,
            res=res,
            duration_min=duration_min,
            buffer_before_min=buffer_before_min,
            buffer_after_min=buffer_after_min,
            granularity_min=granularity_min,
        )
    return sorted(s for s in union if earliest <= s <= horizon)


def free_resource_ids_at(
    *,
    start_utc: datetime,
    day: date,
    tz_name: str,
    duration_min: int,
    buffer_before_min: int,
    buffer_after_min: int,
    granularity_min: int,
    resources: list[ResourceAvailability],
) -> list[str]:
    """Resources whose schedule offers `start_utc` and whose guard interval is
    free. Used to assign a concrete resource at booking time."""
    out: list[str] = []
    for res in resources:
        if start_utc in _free_starts_for_resource(
            day=day,
            tz_name=tz_name,
            res=res,
            duration_min=duration_min,
            buffer_before_min=buffer_before_min,
            buffer_after_min=buffer_after_min,
            granularity_min=granularity_min,
        ):
            out.append(res.resource_id)
    return out
