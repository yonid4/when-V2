"""Scheduling algorithm service — generates ranked time proposals for an event."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from app.services.event_service import fetch_event_by_uid
from app.utils.supabase import service_client

logger = logging.getLogger(__name__)


def get_event_and_check_access(uid: str, user_id: str, coordinator_only: bool = False) -> dict:
    """Look up event by uid and verify access.
    Returns the event row (includes proposals_needs_regeneration).
    Raises 404 if not found, 403 if unauthorized.
    """
    event = fetch_event_by_uid(uid, db=service_client)

    if event["coordinator_id"] == user_id:
        return event

    if coordinator_only:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Coordinator only")

    participant_result = (
        service_client.table("event_participants")
        .select("user_id")
        .eq("event_id", event["id"])
        .eq("user_id", user_id)
        .eq("status", "accepted")
        .maybe_single()
        .execute()
    )
    if not participant_result or not participant_result.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an accepted participant")

    return event


def get_cached_proposals(event_id: str) -> list[dict]:
    result = (
        service_client.table("proposed_times")
        .select("id, event_id, start_time_utc, end_time_utc, conflicts, preferred_count, reasoning, rank")
        .eq("event_id", event_id)
        .order("rank")
        .execute()
    )
    rows = result.data or []
    return [
        {
            "id": row["id"],
            "event_id": row["event_id"],
            "start_time_utc": row["start_time_utc"],
            "end_time_utc": row["end_time_utc"],
            "conflict_count": row.get("conflicts", 0),
            "preferred_count": row.get("preferred_count", 0),
            "reasoning": row["reasoning"],
            "rank": row["rank"],
        }
        for row in rows
    ]


def _parse_dt(s: str) -> datetime:
    """Parse an ISO datetime string (with or without Z) to a UTC-aware datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _snap_forward(t: datetime, duration: timedelta, seg_end: datetime) -> list[datetime]:
    """Snap t to the next 30-min boundary and collect all stride slots until seg_end."""
    minute_mod = t.minute % 30
    if minute_mod != 0:
        t += timedelta(minutes=(30 - minute_mod))
    t = t.replace(second=0, microsecond=0)

    slots: list[datetime] = []
    stride = timedelta(minutes=30)
    while t + duration <= seg_end:
        slots.append(t)
        t += stride
    return slots


def _build_day_candidates(
    start_date: datetime.date,
    end_date: datetime.date,
    start_hour: int,
    end_hour: int,
    duration: timedelta,
    earliest_dt: datetime,
    reference_time_utc: datetime,
) -> list[datetime]:
    """Build candidate start times for each day in [start_date, end_date].

    Handles both normal (start_hour < end_hour) and wrap-around
    (start_hour >= end_hour, e.g. 20:00–03:00) UTC windows.

    - Normal: each day has one segment [start_hour, end_hour).
    - Wrap: each day has two segments [start_hour, midnight) and [midnight, end_hour).
      The wrap segment that trails into the next calendar day is attached to the
      *previous* day's iteration so scoring/conflict logic stays per-event-day.
    - Every segment is clamped to reference_time_utc so past slots are never
      generated. This reference is an explicit input, never the wall clock, to
      keep proposal generation deterministic.
    - First day: also clamped to earliest_dt.
    - Last day: only segments that fall within the event window are included.
    """
    now = reference_time_utc
    candidates: list[datetime] = []

    # end_hour == 0 with a wrap means end at midnight (full wrap to end of day)
    wraps = (end_hour != 0 and end_hour <= start_hour) or (end_hour == 0 and start_hour > 0)

    day = start_date
    while day <= end_date:
        is_first = day == start_date
        is_last = day == end_date

        midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        next_midnight = midnight + timedelta(days=1)

        if wraps:
            # Segment 1: start_hour → midnight of this day
            seg1_start = datetime(day.year, day.month, day.day, start_hour, 0, tzinfo=timezone.utc)
            seg1_end = next_midnight

            # Segment 2: midnight → end_hour (overnight tail into next calendar day)
            if end_hour == 0:
                seg2_start = seg2_end = next_midnight  # no tail segment
            else:
                seg2_start = next_midnight
                seg2_end = next_midnight.replace(hour=end_hour, minute=0, second=0, microsecond=0)

            # Clamp both segment starts to now (and earliest_dt for seg1 on first day)
            t1 = seg1_start
            if is_first:
                t1 = max(t1, earliest_dt)
            t1 = max(t1, now)
            candidates.extend(_snap_forward(t1, duration, seg1_end))

            # Tail segment: only add if next day is still within the event window
            if not is_last and end_hour != 0:
                candidates.extend(_snap_forward(max(seg2_start, now), duration, seg2_end))

        else:
            # Normal window: start_hour → end_hour (or midnight if end_hour == 0)
            seg_start = datetime(day.year, day.month, day.day, start_hour, 0, tzinfo=timezone.utc)
            if end_hour == 0:
                seg_end = next_midnight
            else:
                seg_end = datetime(day.year, day.month, day.day, end_hour, 0, tzinfo=timezone.utc)

            t = seg_start
            if is_first:
                t = max(t, earliest_dt)
            t = max(t, now)
            candidates.extend(_snap_forward(t, duration, seg_end))

        day += timedelta(days=1)

    return candidates


def generate_proposals(event_id: str, *, reference_time_utc: datetime, db=None) -> list[dict]:
    """Generate ranked time proposals for an event and persist them.

    ``reference_time_utc`` is the request instant, supplied by the caller (the
    router). It is used to clamp out past slots and to stamp
    ``proposals_last_generated_at``. It is a required, explicit input — the
    service never reads the wall clock — so generation is a pure function of
    (event data, reference_time_utc) and stays deterministic.

    Steps:
    1. Fetch event metadata (duration, window).
    2. Fetch accepted participants.
    3. Fetch busy and preferred slots within the window.
    4. Generate candidate 30-min-stride windows of duration_minutes length.
    5. Score each candidate (conflict_count, preferred_count).
    6. Rank: conflict_count ASC, preferred_count DESC, start_time ASC — take top 5.
    7. If no candidates, log a warning and return [] without touching existing proposals or flags.
    8. Delete old proposed_times rows, insert new ones.
    9. Update event: proposals_last_generated_at, proposals_needs_regeneration=false.
    10. Return inserted rows.
    """
    client = db if db is not None else service_client

    # 1. Fetch event
    event_result = (
        client.table("events")
        .select("id, duration_minutes, earliest_datetime_utc, latest_datetime_utc")
        .eq("id", event_id)
        .maybe_single()
        .execute()
    )
    event = event_result.data if event_result else None
    if not event:
        return []

    duration_min = int(event["duration_minutes"])
    earliest_dt = _parse_dt(event["earliest_datetime_utc"])
    latest_dt = _parse_dt(event["latest_datetime_utc"])

    start_date = earliest_dt.date()
    end_date = latest_dt.date()
    start_hour = earliest_dt.hour
    end_hour = latest_dt.hour

    # 2. Fetch accepted participants
    participants_result = (
        client.table("event_participants")
        .select("user_id")
        .eq("event_id", event_id)
        .eq("status", "accepted")
        .execute()
    )
    accepted_participant_ids = [r["user_id"] for r in (participants_result.data or [])]
    total = len(accepted_participant_ids)

    # 3. Fetch busy slots for accepted participants within the window
    busy_slots: list[dict] = []
    if accepted_participant_ids:
        busy_result = (
            client.table("busy_slots")
            .select("user_id, start_time_utc, end_time_utc")
            .in_("user_id", accepted_participant_ids)
            .lt("start_time_utc", event["latest_datetime_utc"])
            .gt("end_time_utc", event["earliest_datetime_utc"])
            .execute()
        )
        busy_slots = busy_result.data or []

    # 4. Fetch preferred slots for accepted participants within the window
    preferred_slots: list[dict] = []
    if accepted_participant_ids:
        pref_result = (
            client.table("preferred_slots")
            .select("user_id, start_time_utc, end_time_utc")
            .eq("event_id", event_id)
            .in_("user_id", accepted_participant_ids)
            .execute()
        )
        preferred_slots = pref_result.data or []

    # 5. Generate candidate windows day-by-day within the configured hour window
    duration = timedelta(minutes=duration_min)
    candidates = _build_day_candidates(
        start_date=start_date,
        end_date=end_date,
        start_hour=start_hour,
        end_hour=end_hour,
        duration=duration,
        earliest_dt=earliest_dt,
        reference_time_utc=reference_time_utc,
    )

    # Clamp to the window's upper bound: a meeting must END within the event
    # window. This drops spurious wrap-around candidates on the last day whose
    # evening segment lies entirely after latest_dt (M8). No-op for normal
    # windows, where segment ends are already bounded by end_hour <= latest_dt.
    candidates = [c for c in candidates if c + duration <= latest_dt]

    # 6. Score each candidate
    scored = []
    for cand_start in candidates:
        cand_end = cand_start + duration

        # conflict_count: unique participants with at least one overlapping busy slot
        conflicting = set()
        for bs in busy_slots:
            bs_start = _parse_dt(bs["start_time_utc"])
            bs_end = _parse_dt(bs["end_time_utc"])
            if bs_start < cand_end and bs_end > cand_start:
                conflicting.add(bs["user_id"])
        conflict_count = len(conflicting)

        # preferred_count: unique participants with at least one overlapping preferred slot
        preferring = set()
        for ps in preferred_slots:
            ps_start = _parse_dt(ps["start_time_utc"])
            ps_end = _parse_dt(ps["end_time_utc"])
            if ps_start < cand_end and ps_end > cand_start:
                preferring.add(ps["user_id"])
        preferred_count = len(preferring)

        free_count = total - conflict_count
        reasoning = f"{free_count}/{total} participants free"
        if preferred_count > 0:
            reasoning += f", {preferred_count} marked as preferred"

        scored.append({
            "start": cand_start,
            "end": cand_end,
            "conflict_count": conflict_count,
            "preferred_count": preferred_count,
            "reasoning": reasoning,
        })

    # 7. Rank: conflict_count ASC, preferred_count DESC, start_time ASC — take top 5
    scored.sort(key=lambda x: (x["conflict_count"], -x["preferred_count"], x["start"]))
    top5 = scored[:5]

    if not top5:
        logger.warning("generate_proposals: no candidates found for event %s — keeping existing proposals", event_id)
        return []

    # 8. Delete old proposed_times rows and insert new ones
    client.table("proposed_times").delete().eq("event_id", event_id).execute()

    now_iso = reference_time_utc.isoformat()
    rows_to_insert = []
    for rank, item in enumerate(top5, start=1):
        rows_to_insert.append({
            "event_id": event_id,
            "start_time_utc": item["start"].isoformat(),
            "end_time_utc": item["end"].isoformat(),
            "conflicts": item["conflict_count"],
            "preferred_count": item["preferred_count"],
            "reasoning": item["reasoning"],
            "rank": rank,
        })

    insert_result = (
        client.table("proposed_times")
        .insert(rows_to_insert)
        .execute()
    )
    inserted = insert_result.data or []

    # 9. Update event metadata only on success
    client.table("events").update({
        "proposals_last_generated_at": now_iso,
        "proposals_needs_regeneration": False,
    }).eq("id", event_id).execute()

    # Return rows with the expected field names for the API response
    result = []
    for row in inserted:
        result.append({
            "id": row["id"],
            "event_id": row["event_id"],
            "start_time_utc": row["start_time_utc"],
            "end_time_utc": row["end_time_utc"],
            "conflict_count": row.get("conflicts", 0),
            "preferred_count": row.get("preferred_count", 0),
            "reasoning": row["reasoning"],
            "rank": row["rank"],
        })
    return result
