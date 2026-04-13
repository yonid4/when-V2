"""Service layer for pre-computing availability segments for the grid.

Fetches raw busy and preferred slots, then segments the timeline at every
boundary where the participant count changes. Returns a flat list of
non-overlapping typed segments ready for the frontend to render directly.
"""

from datetime import datetime, timezone

from app.services import busy_slots_service, preferred_slots_service


def _parse_dt(s: str) -> datetime:
    """Parse an ISO datetime string to a UTC-aware datetime."""
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _intensity_tier(count: int) -> int:
    if count >= 7:
        return 4
    if count >= 5:
        return 3
    if count >= 3:
        return 2
    return 1


def compute_availability_segments(event_uid: str, current_user_id: str) -> list[dict]:
    """Return pre-computed, non-overlapping time segments for the availability grid.

    Each segment has:
      start_time_utc, end_time_utc — ISO strings
      type                         — "busy" | "preferred" | "conflict"
      busy_count                   — number of participants busy in this segment
      preferred_count              — number of participants preferring this segment

    Adjacent segments of the same type and intensity tier are merged.
    """
    busy_slots = busy_slots_service.get_event_busy_slots(event_uid, current_user_id) or []
    preferred_slots = preferred_slots_service.get_preferred_slots(event_uid, current_user_id) or []

    busy_ivs = [
        (_parse_dt(s["start_time_utc"]), _parse_dt(s["end_time_utc"]))
        for s in busy_slots
    ]
    pref_ivs = [
        (_parse_dt(s["start_time_utc"]), _parse_dt(s["end_time_utc"]))
        for s in preferred_slots
    ]

    # Collect all unique boundary points
    all_points: set[datetime] = set()
    for start, end in busy_ivs + pref_ivs:
        all_points.add(start)
        all_points.add(end)

    if not all_points:
        return []

    sorted_points = sorted(all_points)

    # Score each segment between consecutive boundary points
    raw: list[dict] = []
    for t_start, t_end in zip(sorted_points, sorted_points[1:]):
        bc = sum(1 for s, e in busy_ivs if s <= t_start and e >= t_end)
        pc = sum(1 for s, e in pref_ivs if s <= t_start and e >= t_end)

        if bc == 0 and pc == 0:
            continue

        if bc > 0 and pc > 0:
            seg_type = "conflict"
        elif bc > 0:
            seg_type = "busy"
        else:
            seg_type = "preferred"

        raw.append({"start": t_start, "end": t_end, "type": seg_type, "bc": bc, "pc": pc})

    if not raw:
        return []

    # Merge adjacent segments of same type and same intensity tier
    merged = [raw[0].copy()]
    for seg in raw[1:]:
        last = merged[-1]
        if (
            seg["type"] == last["type"]
            and _intensity_tier(seg["bc"]) == _intensity_tier(last["bc"])
            and _intensity_tier(seg["pc"]) == _intensity_tier(last["pc"])
            and seg["start"] == last["end"]
        ):
            last["end"] = seg["end"]
            last["bc"] = max(last["bc"], seg["bc"])
            last["pc"] = max(last["pc"], seg["pc"])
        else:
            merged.append(seg.copy())

    return [
        {
            "start_time_utc": s["start"].isoformat(),
            "end_time_utc": s["end"].isoformat(),
            "type": s["type"],
            "busy_count": s["bc"],
            "preferred_count": s["pc"],
        }
        for s in merged
    ]
