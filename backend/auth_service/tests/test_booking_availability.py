from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from auth_service.services.booking_availability import (
    ResourceAvailability,
    available_starts,
    free_resource_ids_at,
    open_windows_utc,
)

UTC = ZoneInfo("UTC")


def test_open_windows_converts_local_hours_to_utc():
    # Wednesday in Europe/Bucharest (EEST, +3 in June). 09:00-18:00 local.
    windows = open_windows_utc(
        day=date(2026, 6, 10),
        tz_name="Europe/Bucharest",
        hours=[(time(9, 0), time(18, 0))],
        exception=None,
    )
    assert windows == [
        (datetime(2026, 6, 10, 6, 0, tzinfo=UTC), datetime(2026, 6, 10, 15, 0, tzinfo=UTC))
    ]


def test_open_windows_split_shift():
    windows = open_windows_utc(
        day=date(2026, 6, 10),
        tz_name="Europe/Bucharest",
        hours=[(time(9, 0), time(12, 0)), (time(14, 0), time(18, 0))],
        exception=None,
    )
    assert len(windows) == 2


def test_open_windows_closed_exception_zeroes_day():
    windows = open_windows_utc(
        day=date(2026, 6, 10),
        tz_name="Europe/Bucharest",
        hours=[(time(9, 0), time(18, 0))],
        exception={"is_closed": True, "start_time": None, "end_time": None},
    )
    assert windows == []


def test_open_windows_custom_hours_exception_replaces():
    windows = open_windows_utc(
        day=date(2026, 6, 10),
        tz_name="Europe/Bucharest",
        hours=[(time(9, 0), time(18, 0))],
        exception={"is_closed": False, "start_time": time(10, 0), "end_time": time(12, 0)},
    )
    assert windows == [
        (datetime(2026, 6, 10, 7, 0, tzinfo=UTC), datetime(2026, 6, 10, 9, 0, tzinfo=UTC))
    ]


def test_dst_spring_forward_gap_is_skipped():
    # Europe/Berlin spring-forward 2026-03-29: 02:00->03:00 local. Hours 01:00-04:00
    # local => 00:00..02:00 UTC (no 02:xx local exists). One contiguous UTC window.
    windows = open_windows_utc(
        day=date(2026, 3, 29),
        tz_name="Europe/Berlin",
        hours=[(time(1, 0), time(4, 0))],
        exception=None,
    )
    # 01:00 CET = 00:00 UTC; 04:00 CEST = 02:00 UTC.
    assert windows == [
        (datetime(2026, 3, 29, 0, 0, tzinfo=UTC), datetime(2026, 3, 29, 2, 0, tzinfo=UTC))
    ]


def _res(rid, busy=()):
    return ResourceAvailability(
        resource_id=rid, hours=[(time(9, 0), time(18, 0))], exception=None, busy=list(busy)
    )


COMMON_STARTS = {
    "tz_name": "Europe/Bucharest",
    "duration_min": 45,
    "buffer_before_min": 0,
    "buffer_after_min": 0,
    "granularity_min": 45,
    "lead_time_min": 120,
    "max_advance_days": 120,
}


def test_available_starts_basic_count():
    starts = available_starts(
        day=date(2026, 6, 10),
        now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        resources=[_res("r1")],
        **COMMON_STARTS,
    )
    # 09:00-18:00, 45-min grid => 12 slots (last 17:15).
    assert len(starts) == 12
    assert starts[0] == datetime(2026, 6, 10, 6, 0, tzinfo=UTC)  # 09:00 EEST


def test_lead_time_drops_near_slots():
    starts = available_starts(
        day=date(2026, 6, 10),
        now_utc=datetime(2026, 6, 10, 5, 30, tzinfo=UTC),
        resources=[_res("r1")],
        **COMMON_STARTS,
    )
    assert datetime(2026, 6, 10, 6, 0, tzinfo=UTC) not in starts  # within 2h notice
    assert datetime(2026, 6, 10, 7, 30, tzinfo=UTC) in starts


def test_buffer_blocks_adjacent_slot():
    # An existing booking occupies the guard 07:15-08:30 UTC. With 15-min buffers,
    # the 06:45 UTC grid slot's guard is [06:30, 07:45) which overlaps it -> dropped.
    # The 06:00 grid slot's guard [05:45, 07:00) does NOT overlap -> stays free.
    busy = [(datetime(2026, 6, 10, 7, 15, tzinfo=UTC), datetime(2026, 6, 10, 8, 30, tzinfo=UTC))]
    starts = available_starts(
        day=date(2026, 6, 10),
        now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        resources=[_res("r1", busy)],
        **{**COMMON_STARTS, "buffer_before_min": 15, "buffer_after_min": 15},
    )
    assert datetime(2026, 6, 10, 6, 45, tzinfo=UTC) not in starts
    assert datetime(2026, 6, 10, 6, 0, tzinfo=UTC) in starts


def test_slot_offered_if_any_resource_free():
    busy = [(datetime(2026, 6, 10, 6, 0, tzinfo=UTC), datetime(2026, 6, 10, 6, 45, tzinfo=UTC))]
    starts = available_starts(
        day=date(2026, 6, 10),
        now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        resources=[_res("r1", busy), _res("r2")],
        **COMMON_STARTS,
    )
    # r1's 09:00 is taken but r2 is free -> still offered.
    assert datetime(2026, 6, 10, 6, 0, tzinfo=UTC) in starts


def test_free_resource_ids_excludes_busy_resource():
    busy = [(datetime(2026, 6, 10, 6, 0, tzinfo=UTC), datetime(2026, 6, 10, 6, 45, tzinfo=UTC))]
    free = free_resource_ids_at(
        start_utc=datetime(2026, 6, 10, 6, 0, tzinfo=UTC),
        day=date(2026, 6, 10),
        tz_name="Europe/Bucharest",
        duration_min=45,
        buffer_before_min=0,
        buffer_after_min=0,
        granularity_min=45,
        resources=[_res("r1", busy), _res("r2")],
    )
    assert free == ["r2"]


def test_max_advance_boundary():
    starts = available_starts(
        day=date(2026, 10, 10),
        now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        resources=[_res("r1")],
        **{**COMMON_STARTS, "max_advance_days": 30},
    )
    assert starts == []


def test_dst_fall_back_day_uses_post_transition_offset():
    # Europe/Berlin fall-back 2026-10-25 (03:00 CEST -> 02:00 CET). For hours well
    # after the transition the day is on CET (+1): 09:00 local = 08:00 UTC,
    # 17:00 local = 16:00 UTC.
    windows = open_windows_utc(
        day=date(2026, 10, 25),
        tz_name="Europe/Berlin",
        hours=[(time(9, 0), time(17, 0))],
        exception=None,
    )
    assert windows == [
        (datetime(2026, 10, 25, 8, 0, tzinfo=UTC), datetime(2026, 10, 25, 16, 0, tzinfo=UTC))
    ]
