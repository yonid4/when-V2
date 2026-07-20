"""Unit tests for app.utils.dates — the single home for tz conversion.

Covers DST boundaries, invalid/missing tz fallback to UTC, local_today midnight
shifts, and format_utc_in_tz rendering. Pure functions, no network/Supabase.
"""

from datetime import date, datetime, time, timezone

from app.utils.dates import (
    format_utc_in_tz,
    is_valid_timezone,
    local_today,
    local_window_to_utc,
)


# ─── local_window_to_utc: DST boundary ───────────────────────────────────────

def test_window_straddles_spring_forward_uses_correct_offset_each_side():
    """America/New_York springs forward 2026-03-08. A window from 2026-03-07 to
    2026-03-09 must use EST (-05:00) on the start and EDT (-04:00) on the end."""
    start_utc, end_utc = local_window_to_utc(
        date(2026, 3, 7),
        date(2026, 3, 9),
        time(12, 0),
        time(12, 0),
        "America/New_York",
    )
    # 2026-03-07 12:00 EST (-05:00) -> 17:00 UTC
    assert start_utc == datetime(2026, 3, 7, 17, 0, tzinfo=timezone.utc)
    # 2026-03-09 12:00 EDT (-04:00) -> 16:00 UTC
    assert end_utc == datetime(2026, 3, 9, 16, 0, tzinfo=timezone.utc)
    # Returned datetimes are timezone-aware UTC.
    assert start_utc.tzinfo == timezone.utc
    assert end_utc.tzinfo == timezone.utc


def test_window_invalid_tz_falls_back_to_utc():
    """An unknown IANA name is treated as UTC (no conversion applied)."""
    start_utc, end_utc = local_window_to_utc(
        date(2026, 3, 7),
        date(2026, 3, 9),
        time(12, 0),
        time(9, 30),
        "Not/AZone",
    )
    assert start_utc == datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc)
    assert end_utc == datetime(2026, 3, 9, 9, 30, tzinfo=timezone.utc)


def test_window_none_tz_falls_back_to_utc():
    """A missing timezone (None) is treated as UTC."""
    start_utc, end_utc = local_window_to_utc(
        date(2026, 7, 1),
        date(2026, 7, 1),
        time(8, 0),
        time(17, 0),
        None,
    )
    assert start_utc == datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
    assert end_utc == datetime(2026, 7, 1, 17, 0, tzinfo=timezone.utc)


# ─── local_today: midnight shifts ────────────────────────────────────────────

def test_local_today_shifts_date_backwards_across_midnight():
    """2026-07-17T02:00Z is still 2026-07-16 in America/Los_Angeles (PDT -7)."""
    ref = datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc)
    assert local_today(ref, "America/Los_Angeles") == date(2026, 7, 16)


def test_local_today_shifts_date_forwards_across_midnight():
    """2026-07-16T20:00Z is already 2026-07-17 in Asia/Tokyo (JST +9)."""
    ref = datetime(2026, 7, 16, 20, 0, tzinfo=timezone.utc)
    assert local_today(ref, "Asia/Tokyo") == date(2026, 7, 17)


def test_local_today_naive_reference_assumed_utc():
    """A naive reference instant is interpreted as UTC."""
    ref = datetime(2026, 7, 17, 2, 0)  # naive
    assert local_today(ref, "America/Los_Angeles") == date(2026, 7, 16)


def test_local_today_invalid_tz_uses_utc_date():
    """Invalid tz -> UTC, so the UTC date is returned unchanged."""
    ref = datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc)
    assert local_today(ref, "bogus/zone") == date(2026, 7, 17)


# ─── format_utc_in_tz: rendering ─────────────────────────────────────────────

def test_format_utc_in_tz_renders_local_wall_clock():
    """16:30 UTC renders as 12:30 in America/New_York (EDT -4) in July."""
    dt = datetime(2026, 7, 17, 16, 30, tzinfo=timezone.utc)
    assert format_utc_in_tz(dt, "America/New_York") == "2026-07-17 12:30"


def test_format_utc_in_tz_invalid_tz_renders_utc():
    """Invalid tz -> rendered as UTC wall-clock."""
    dt = datetime(2026, 7, 17, 16, 30, tzinfo=timezone.utc)
    assert format_utc_in_tz(dt, "nope") == "2026-07-17 16:30"


def test_format_utc_in_tz_naive_assumed_utc():
    """A naive UTC instant renders correctly in the target zone."""
    dt = datetime(2026, 7, 17, 16, 30)  # naive, assumed UTC
    assert format_utc_in_tz(dt, "America/New_York") == "2026-07-17 12:30"


# ─── is_valid_timezone: IANA name validation ─────────────────────────────────

def test_is_valid_timezone_accepts_known_iana_zones():
    assert is_valid_timezone("America/New_York")
    assert is_valid_timezone("Asia/Jerusalem")
    assert is_valid_timezone("UTC")


def test_is_valid_timezone_rejects_unknown_or_empty():
    assert not is_valid_timezone("Not/AZone")
    assert not is_valid_timezone("EST5EDT-nonsense")
    assert not is_valid_timezone("")
