"""Timezone conversion utilities.

Per the backend rules, ALL timezone conversion in the service layer lives here.
Times are stored and computed in UTC; these helpers translate between a user's
local (IANA) timezone and UTC. An unknown or missing timezone name falls back
to UTC so callers never crash on bad or absent profile data.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc


def _resolve_tz(tz_name: str | None):
    """Return a tzinfo for ``tz_name``, falling back to UTC when it is missing
    or not a known IANA zone."""
    if not tz_name:
        return UTC
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def local_today(reference_time_utc: datetime, tz_name: str | None) -> date:
    """The calendar date it currently is in ``tz_name``.

    ``reference_time_utc`` is a UTC instant (a naive value is assumed to be
    UTC). The returned local date can differ from the UTC date near midnight.
    """
    tz = _resolve_tz(tz_name)
    ref = reference_time_utc
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    return ref.astimezone(tz).date()


def local_window_to_utc(
    start_date: date,
    end_date: date,
    start_time: time,
    end_time: time,
    tz_name: str | None,
) -> tuple[datetime, datetime]:
    """Convert a local date/time window to an aware UTC ``(start, end)`` pair.

    The window opens at ``start_time`` on ``start_date`` and closes at
    ``end_time`` on ``end_date``, all interpreted in ``tz_name``. Both returned
    datetimes are timezone-aware UTC. A window that straddles a DST transition
    yields the correct (differing) UTC offset on each side.
    """
    tz = _resolve_tz(tz_name)
    local_start = datetime.combine(start_date, start_time, tzinfo=tz)
    local_end = datetime.combine(end_date, end_time, tzinfo=tz)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def format_utc_in_tz(
    dt_utc: datetime, tz_name: str | None, fmt: str = "%Y-%m-%d %H:%M"
) -> str:
    """Render a UTC instant as local wall-clock time in ``tz_name``.

    A naive ``dt_utc`` is assumed to already be UTC.
    """
    tz = _resolve_tz(tz_name)
    dt = dt_utc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(tz).strftime(fmt)
