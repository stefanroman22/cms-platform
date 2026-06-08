"""Pure-function tests for booking_stats.compute_booking_stats."""

from datetime import UTC, datetime

import pytest

from auth_service.services.booking_stats import compute_booking_stats

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _b(status: str, start_utc: str, service_name: str | None = "Cut") -> dict:
    return {"status": status, "start_utc": start_utc, "service_name": service_name}


# Fixed "now" for upcoming/today/this_week tests:
# 2024-03-15 10:00 UTC — a Friday.
NOW_UTC = datetime(2024, 3, 15, 10, 0, 0, tzinfo=UTC)
TZ = "Europe/Berlin"  # UTC+1 in March (CET)


# ---------------------------------------------------------------------------
# empty list → zeros
# ---------------------------------------------------------------------------


def test_empty_returns_zeros():
    result = compute_booking_stats([], now_utc=NOW_UTC, tz_name=TZ)
    assert result["kpis"]["total"] == 0
    assert result["kpis"]["upcoming"] == 0
    assert result["kpis"]["today"] == 0
    assert result["kpis"]["this_week"] == 0
    assert result["kpis"]["avg_per_day"] == 0.0
    assert result["cancellation_rate"] == 0.0
    assert result["no_show_rate"] == 0.0
    assert result["by_day"] == []
    assert result["by_service"] == []
    assert result["by_status"] == []
    assert result["heatmap"] == []


# ---------------------------------------------------------------------------
# status counts + cancellation / no_show rates
# ---------------------------------------------------------------------------


def test_status_counts_and_rates():
    bookings = [
        _b("confirmed", "2024-03-01T09:00:00+00:00"),
        _b("confirmed", "2024-03-02T09:00:00+00:00"),
        _b("completed", "2024-03-03T09:00:00+00:00"),
        _b("cancelled", "2024-03-04T09:00:00+00:00"),
        _b("no_show", "2024-03-05T09:00:00+00:00"),
        _b("no_show", "2024-03-06T09:00:00+00:00"),
    ]
    result = compute_booking_stats(bookings, now_utc=NOW_UTC, tz_name=TZ)
    assert result["kpis"]["total"] == 6
    # cancellation_rate = 1/6 * 100 ≈ 16.7
    assert result["cancellation_rate"] == pytest.approx(16.7, abs=0.1)
    # no_show_rate = 2/6 * 100 ≈ 33.3
    assert result["no_show_rate"] == pytest.approx(33.3, abs=0.1)

    status_map = {row["status"]: row["count"] for row in result["by_status"]}
    assert status_map["confirmed"] == 2
    assert status_map["completed"] == 1
    assert status_map["cancelled"] == 1
    assert status_map["no_show"] == 2


# ---------------------------------------------------------------------------
# by_service grouping
# ---------------------------------------------------------------------------


def test_by_service_grouping():
    bookings = [
        _b("confirmed", "2024-03-01T09:00:00+00:00", "Cut"),
        _b("confirmed", "2024-03-02T09:00:00+00:00", "Cut"),
        _b("confirmed", "2024-03-03T09:00:00+00:00", "Color"),
        _b("completed", "2024-03-04T09:00:00+00:00", None),  # None → "—"
    ]
    result = compute_booking_stats(bookings, now_utc=NOW_UTC, tz_name=TZ)
    services = {row["service"]: row["count"] for row in result["by_service"]}
    assert services["Cut"] == 2
    assert services["Color"] == 1
    assert services["—"] == 1
    # most_common order: Cut first
    assert result["by_service"][0]["service"] == "Cut"


# ---------------------------------------------------------------------------
# by_day tz bucketing — UTC time crossing local midnight
# ---------------------------------------------------------------------------


def test_by_day_tz_bucketing():
    # 2024-03-10 23:30 UTC = 2024-03-11 00:30 CET (Europe/Berlin)
    # So this booking should land on 2024-03-11 in local time, not 2024-03-10.
    bookings = [
        _b("confirmed", "2024-03-10T23:30:00+00:00"),
    ]
    result = compute_booking_stats(bookings, now_utc=NOW_UTC, tz_name=TZ)
    assert len(result["by_day"]) == 1
    assert result["by_day"][0]["date"] == "2024-03-11"


def test_by_day_sorting():
    bookings = [
        _b("confirmed", "2024-03-05T10:00:00+00:00"),
        _b("confirmed", "2024-03-02T10:00:00+00:00"),
        _b("confirmed", "2024-03-07T10:00:00+00:00"),
    ]
    result = compute_booking_stats(bookings, now_utc=NOW_UTC, tz_name=TZ)
    dates = [row["date"] for row in result["by_day"]]
    assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# heatmap weekday/hour
# ---------------------------------------------------------------------------


def test_heatmap_weekday_hour():
    # 2024-03-11 10:00 UTC → 11:00 CET → Monday (weekday=0), hour=11
    bookings = [
        _b("confirmed", "2024-03-11T10:00:00+00:00"),
        _b("confirmed", "2024-03-11T10:00:00+00:00"),  # duplicate → count=2
        _b("completed", "2024-03-12T14:00:00+00:00"),  # Tuesday 15:00 CET → weekday=1, hour=15
    ]
    result = compute_booking_stats(bookings, now_utc=NOW_UTC, tz_name=TZ)
    heat_map = {(row["weekday"], row["hour"]): row["count"] for row in result["heatmap"]}
    assert heat_map[(0, 11)] == 2
    assert heat_map[(1, 15)] == 1


# ---------------------------------------------------------------------------
# upcoming / today / this_week with fixed now_utc
# ---------------------------------------------------------------------------
# now_utc = 2024-03-15 10:00 UTC → local (CET, UTC+1) = 2024-03-15 11:00
# today = 2024-03-15, week_end = 2024-03-22


def test_upcoming_today_this_week():
    bookings = [
        # past confirmed — NOT upcoming
        _b("confirmed", "2024-03-15T08:00:00+00:00"),
        # future confirmed — upcoming, today, this_week
        _b("confirmed", "2024-03-15T12:00:00+00:00"),
        # future pending — upcoming, this_week (not today)
        _b("pending", "2024-03-18T12:00:00+00:00"),
        # future pending — upcoming, this_week (last day = 2024-03-21, week_end=2024-03-22 so < week_end)
        _b("pending", "2024-03-21T12:00:00+00:00"),
        # future pending — NOT this_week (2024-03-22 = week_end, not < week_end)
        _b("pending", "2024-03-22T12:00:00+00:00"),
        # cancelled future — NOT upcoming (status not confirmed/pending)
        _b("cancelled", "2024-03-16T12:00:00+00:00"),
        # completed future — NOT upcoming
        _b("completed", "2024-03-16T12:00:00+00:00"),
    ]
    result = compute_booking_stats(bookings, now_utc=NOW_UTC, tz_name=TZ)
    kpis = result["kpis"]
    assert kpis["upcoming"] == 4  # 4 confirmed/pending with start >= now_utc
    assert kpis["today"] == 1  # only the 12:00 UTC on 2024-03-15 (local = same day)
    assert kpis["this_week"] == 3  # 2024-03-15, 2024-03-18, 2024-03-21 (not 2024-03-22)


def test_avg_per_day():
    # 3 bookings on 2 distinct days → avg = 3/2 = 1.5
    bookings = [
        _b("confirmed", "2024-03-01T10:00:00+00:00"),
        _b("confirmed", "2024-03-01T11:00:00+00:00"),
        _b("confirmed", "2024-03-02T10:00:00+00:00"),
    ]
    result = compute_booking_stats(bookings, now_utc=NOW_UTC, tz_name=TZ)
    assert result["kpis"]["avg_per_day"] == 1.5
