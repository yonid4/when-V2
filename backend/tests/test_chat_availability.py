"""Chat agent — deterministic availability tests (agent/availability.py).

Covers exact ordered slot output from fixed fixtures (run twice → identical),
window clamping against reference_time, unique-user conflict counting, the
freshness threshold gating sync_users_scoped, and sync_users_scoped's per-user
failure isolation. Supabase is mocked; no network is touched.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.services import sync_service
from app.services.agent import availability

UTC = timezone.utc


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _busy(user_id, start_iso, end_iso):
    return {"user_id": user_id, "start_time_utc": start_iso, "end_time_utc": end_iso}


def _db_busy(busy_rows):
    """A db whose busy_slots query chain returns ``busy_rows``."""
    db = MagicMock()
    (db.table.return_value.select.return_value.in_.return_value
     .lt.return_value.gt.return_value.execute.return_value) = MagicMock(data=list(busy_rows))
    return db


def _iso(y=2026, mo=7, d=20, h=9, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=UTC).isoformat()


# ─── 1. Exact ordered output + determinism ────────────────────────────────────

def test_rank_slots_exact_ordered_output_and_deterministic():
    earliest = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)
    latest = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    reference = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)  # before window: no clamp
    busy = [
        _busy("u1", _iso(h=9, mi=0), _iso(h=11, mi=0)),   # blocks 09:00–11:00
        _busy("u2", _iso(h=9, mi=0), _iso(h=9, mi=30)),   # blocks 09:00–09:30
    ]

    result1 = availability.rank_candidate_slots(
        ["u1", "u2"], earliest, latest, 60,
        reference_time_utc=reference, limit=3, db=_db_busy(busy),
    )
    result2 = availability.rank_candidate_slots(
        ["u1", "u2"], earliest, latest, 60,
        reference_time_utc=reference, limit=3, db=_db_busy(busy),
    )

    assert result1 == result2  # determinism: same input → identical output

    assert result1 == [
        {
            "start_time_utc": "2026-07-20T11:00:00+00:00",
            "end_time_utc": "2026-07-20T12:00:00+00:00",
            "conflict_count": 0,
            "free_count": 2,
            "total": 2,
            "reasoning": "2/2 participants free",
        },
        {
            "start_time_utc": "2026-07-20T09:30:00+00:00",
            "end_time_utc": "2026-07-20T10:30:00+00:00",
            "conflict_count": 1,
            "free_count": 1,
            "total": 2,
            "reasoning": "1/2 participants free",
        },
        {
            "start_time_utc": "2026-07-20T10:00:00+00:00",
            "end_time_utc": "2026-07-20T11:00:00+00:00",
            "conflict_count": 1,
            "free_count": 1,
            "total": 2,
            "reasoning": "1/2 participants free",
        },
    ]


def test_rank_slots_accepts_iso_string_inputs():
    """Datetime args may arrive as ISO strings (jsonb thread state)."""
    busy = [_busy("u1", _iso(h=9), _iso(h=11))]
    result = availability.rank_candidate_slots(
        ["u1"],
        "2026-07-20T09:00:00+00:00",
        "2026-07-20T12:00:00+00:00",
        60,
        reference_time_utc="2026-07-20T08:00:00+00:00",
        limit=3,
        db=_db_busy(busy),
    )
    assert result[0]["start_time_utc"] == "2026-07-20T11:00:00+00:00"


# ─── 2. Window clamping vs reference_time ─────────────────────────────────────

def test_rank_slots_clamps_past_slots_to_reference_time():
    earliest = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)
    latest = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    reference = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)  # mid-window
    busy = [
        _busy("u1", _iso(h=9, mi=0), _iso(h=11, mi=0)),
        _busy("u2", _iso(h=9, mi=0), _iso(h=9, mi=30)),
    ]

    result = availability.rank_candidate_slots(
        ["u1", "u2"], earliest, latest, 60,
        reference_time_utc=reference, limit=5, db=_db_busy(busy),
    )

    starts = [r["start_time_utc"] for r in result]
    # No candidate may start before 10:00 (reference_time clamp).
    assert all(s >= "2026-07-20T10:00:00+00:00" for s in starts)
    # Best remaining slot is 11:00 (fully free).
    assert result[0]["start_time_utc"] == "2026-07-20T11:00:00+00:00"


# ─── 3. Unique-user conflict counting ─────────────────────────────────────────

def test_rank_slots_counts_unique_conflicting_users():
    """A user with two overlapping busy slots counts as one conflict."""
    earliest = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)
    latest = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    reference = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    busy = [
        _busy("u1", _iso(h=9, mi=0), _iso(h=9, mi=30)),
        _busy("u1", _iso(h=9, mi=15), _iso(h=9, mi=45)),  # same user, 2nd slot
    ]

    result = availability.rank_candidate_slots(
        ["u1", "u2"], earliest, latest, 60,
        reference_time_utc=reference, limit=3, db=_db_busy(busy),
    )

    # Single 09:00–10:00 candidate; u1 conflicts once, u2 free.
    assert len(result) == 1
    assert result[0]["conflict_count"] == 1
    assert result[0]["free_count"] == 1
    assert result[0]["total"] == 2


# ─── 4. Freshness threshold → sync only stale users ───────────────────────────

def _db_accounts(rows):
    db = MagicMock()
    (db.table.return_value.select.return_value.in_.return_value
     .execute.return_value) = MagicMock(data=list(rows))
    return db


@patch("app.services.agent.availability.sync_service")
def test_ensure_fresh_syncs_only_stale_users(mock_sync):
    now = datetime.now(UTC)
    rows = [
        {"user_id": "u1", "last_synced_at": (now - timedelta(minutes=5)).isoformat()},   # fresh
        {"user_id": "u2", "last_synced_at": (now - timedelta(minutes=30)).isoformat()},  # stale
        {"user_id": "u3", "last_synced_at": None},                                       # never synced
        # u4 has no calendar_accounts row → skipped (nothing to sync)
    ]
    window_start = now
    window_end = now + timedelta(hours=2)

    stale = availability.ensure_fresh_busy_slots(
        ["u1", "u2", "u3", "u4"], window_start, window_end,
        reference_time_utc=now, max_age_minutes=15, db=_db_accounts(rows),
    )

    assert stale == ["u2", "u3"]
    mock_sync.sync_users_scoped.assert_called_once_with(["u2", "u3"], window_start, window_end)


@patch("app.services.agent.availability.sync_service")
def test_ensure_fresh_no_sync_when_all_fresh(mock_sync):
    now = datetime.now(UTC)
    rows = [{"user_id": "u1", "last_synced_at": (now - timedelta(minutes=1)).isoformat()}]

    stale = availability.ensure_fresh_busy_slots(
        ["u1"], now, now + timedelta(hours=1),
        reference_time_utc=now, max_age_minutes=15, db=_db_accounts(rows),
    )

    assert stale == []
    mock_sync.sync_users_scoped.assert_not_called()


@patch("app.services.agent.availability.sync_service")
def test_ensure_fresh_empty_user_ids_is_noop(mock_sync):
    assert availability.ensure_fresh_busy_slots(
        [], datetime.now(UTC), datetime.now(UTC), reference_time_utc=datetime.now(UTC)
    ) == []
    mock_sync.sync_users_scoped.assert_not_called()


# ─── 5. sync_users_scoped: per-user failure isolation ─────────────────────────

@patch("app.services.sync_service._sync_user")
def test_sync_users_scoped_isolates_per_user_failure(mock_sync_user):
    def side_effect(uid, time_min, time_max):
        if uid == "u2":
            raise RuntimeError("boom")
        return 3

    mock_sync_user.side_effect = side_effect
    now = datetime.now(UTC)

    result = sync_service.sync_users_scoped(["u1", "u2", "u3"], now, now + timedelta(hours=1))

    assert result == {"u1": 3, "u2": 0, "u3": 3}
    assert mock_sync_user.call_count == 3


@patch("app.services.sync_service._sync_user")
def test_sync_users_scoped_passes_window_through(mock_sync_user):
    mock_sync_user.return_value = 1
    now = datetime.now(UTC)
    time_max = now + timedelta(days=3)

    sync_service.sync_users_scoped(["u1"], now, time_max)

    args, _ = mock_sync_user.call_args
    assert args == ("u1", now, time_max)
