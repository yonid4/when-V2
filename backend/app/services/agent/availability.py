"""Deterministic availability ranking for the chat agent (plan §5).

``rank_candidate_slots`` reuses the proposal service's candidate grid
(``_build_day_candidates``) and datetime parsing (``_parse_dt``) byte-for-byte,
then scores each candidate by the number of unique participants with a
conflicting busy slot — exactly like ``generate_proposals`` step 6. It is a pure
function: same input → same output, stable ordering, no LLM/randomness.

``ensure_fresh_busy_slots`` is a best-effort freshness gate: for users whose
``calendar_accounts.last_synced_at`` is older than ``max_age_minutes`` (relative
to an explicit ``reference_time_utc``), it triggers a window-scoped sync via
``sync_service.sync_users_scoped``. Failures are logged and ignored so ranking
proceeds on whatever data exists.
"""

import logging
from datetime import datetime, timedelta

from app.services import sync_service
from app.services.proposal_service import _build_day_candidates, _parse_dt
from app.utils.supabase import service_client

logger = logging.getLogger(__name__)


def _as_dt(value) -> datetime:
    """Accept either a datetime or an ISO string; return a UTC-aware datetime.

    Reuses ``proposal_service._parse_dt`` for strings so parsing stays identical
    to the proposal pipeline (jsonb thread state stores ISO strings).
    """
    if isinstance(value, datetime):
        return value
    return _parse_dt(value)


def rank_candidate_slots(
    user_ids: list[str],
    earliest_utc,
    latest_utc,
    duration_minutes: int,
    *,
    reference_time_utc,
    limit: int = 3,
    db=None,
) -> list[dict]:
    """Rank the top candidate slots for ``user_ids`` within the window.

    Candidates are the proposal service's deterministic 30-min-stride grid over
    ``[earliest_utc, latest_utc]`` (past-clamped to ``reference_time_utc``), each
    scored by the number of unique participants with an overlapping busy slot.
    Sorted by ``(conflict_count ASC, start ASC)``, top ``limit`` returned.

    Datetime args accept datetimes or ISO strings. Returns a list of dicts with
    ISO-string times for jsonb persistence::

        {start_time_utc, end_time_utc, conflict_count, free_count, total, reasoning}
    """
    client = db if db is not None else service_client

    earliest_dt = _as_dt(earliest_utc)
    latest_dt = _as_dt(latest_utc)
    reference_dt = _as_dt(reference_time_utc)
    duration = timedelta(minutes=int(duration_minutes))

    user_ids = list(user_ids)
    total = len(user_ids)

    # Candidate grid — reused byte-for-byte from proposal_service.
    candidates = _build_day_candidates(
        start_date=earliest_dt.date(),
        end_date=latest_dt.date(),
        start_hour=earliest_dt.hour,
        end_hour=latest_dt.hour,
        duration=duration,
        earliest_dt=earliest_dt,
        reference_time_utc=reference_dt,
    )
    # A meeting must END within the window (matches generate_proposals).
    candidates = [c for c in candidates if c + duration <= latest_dt]

    # Busy slots overlapping the window (precedent: proposal_service busy query).
    busy_slots: list[dict] = []
    if user_ids:
        busy_result = (
            client.table("busy_slots")
            .select("user_id, start_time_utc, end_time_utc")
            .in_("user_id", user_ids)
            .lt("start_time_utc", latest_dt.isoformat())
            .gt("end_time_utc", earliest_dt.isoformat())
            .execute()
        )
        busy_slots = busy_result.data or []

    scored: list[dict] = []
    for cand_start in candidates:
        cand_end = cand_start + duration

        # conflict_count: unique participants with ≥1 overlapping busy slot.
        conflicting: set[str] = set()
        for bs in busy_slots:
            bs_start = _parse_dt(bs["start_time_utc"])
            bs_end = _parse_dt(bs["end_time_utc"])
            if bs_start < cand_end and bs_end > cand_start:
                conflicting.add(bs["user_id"])
        conflict_count = len(conflicting)
        free_count = total - conflict_count

        scored.append({
            "start": cand_start,
            "end": cand_end,
            "conflict_count": conflict_count,
            "free_count": free_count,
        })

    scored.sort(key=lambda s: (s["conflict_count"], s["start"]))

    return [
        {
            "start_time_utc": s["start"].isoformat(),
            "end_time_utc": s["end"].isoformat(),
            "conflict_count": s["conflict_count"],
            "free_count": s["free_count"],
            "total": total,
            "reasoning": f"{s['free_count']}/{total} participants free",
        }
        for s in scored[:limit]
    ]


def ensure_fresh_busy_slots(
    user_ids: list[str],
    window_start,
    window_end,
    *,
    reference_time_utc,
    max_age_minutes: int = 15,
    db=None,
) -> list[str]:
    """Best-effort: sync stale users' busy slots before ranking.

    Reads ``calendar_accounts.last_synced_at`` for ``user_ids``. A user is stale
    when their most recent sync is older than ``reference_time_utc -
    max_age_minutes`` (or never synced). Stale users are synced, window-scoped,
    via ``sync_service.sync_users_scoped``. Users with no calendar account are
    skipped (nothing to sync). Sync failures are logged and swallowed.

    Returns the list of user_ids deemed stale (in input order) for observability.
    """
    user_ids = list(user_ids)
    if not user_ids:
        return []

    client = db if db is not None else service_client
    threshold = _as_dt(reference_time_utc) - timedelta(minutes=max_age_minutes)

    accounts_result = (
        client.table("calendar_accounts")
        .select("user_id, last_synced_at")
        .in_("user_id", user_ids)
        .execute()
    )

    # Most-recent last_synced_at per user (a user may have several accounts).
    latest: dict[str, datetime | None] = {}
    for row in accounts_result.data or []:
        uid = row["user_id"]
        raw = row.get("last_synced_at")
        synced_at = _as_dt(raw) if raw else None
        if uid not in latest:
            latest[uid] = synced_at
        elif synced_at is not None and (latest[uid] is None or synced_at > latest[uid]):
            latest[uid] = synced_at

    stale = [
        uid for uid in user_ids
        if uid in latest and (latest[uid] is None or latest[uid] < threshold)
    ]
    if not stale:
        return []

    try:
        sync_service.sync_users_scoped(stale, window_start, window_end)
    except Exception as exc:  # pragma: no cover - defensive; wrapper already isolates
        logger.warning(
            "ensure_fresh_busy_slots: scoped sync failed, proceeding on existing data: %s",
            exc,
        )
    return stale
