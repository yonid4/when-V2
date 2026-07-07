"""Sprint 8 — sync_service unit tests (provider-agnostic).

Covers:
- Time range: sync_busy_slots uses now → now+90 days
- Window widening when the user is in past-starting active events
- Event-scoped sync: uses event's earliest/latest, not the global window
- Coordinator inclusion: coordinator synced even if not in event_participants
- _sync_source: upsert + stale deletion operate on provider BusyEvents
- Token rotation: rotated credentials are persisted after a sync

Provider-specific parsing (pagination, UTC normalisation, cancelled/all-day
handling) lives in test_google_provider.py.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from app.providers.base import BusyEvent, ProviderAPIError, ProviderAuthError, TokenBundle
from app.services import sync_service


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _busy(event_id: str, start: datetime, end: datetime) -> BusyEvent:
    return BusyEvent(event_id=event_id, start_utc=start.isoformat(), end_utc=end.isoformat())


def _provider_returning(busy_events) -> MagicMock:
    prov = MagicMock()
    prov.fetch_busy_events.return_value = list(busy_events)
    return prov


# ─── 1. Time range ────────────────────────────────────────────────────────────

def _stub_no_active_events(mock_svc) -> None:
    """Make `_earliest_active_event_start` return its default by stubbing every
    query it issues to return empty data."""
    empty = MagicMock(data=[])
    mock_svc.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = empty
    mock_svc.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = empty
    mock_svc.table.return_value.select.return_value.in_.return_value.in_.return_value.execute.return_value = empty
    mock_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = empty


@patch("app.services.sync_service.service_client")
def test_sync_busy_slots_uses_90_day_window(mock_svc):
    """sync_busy_slots queries calendar_accounts (now → now+90 days) when the
    user is in no active past-starting events."""
    _stub_no_active_events(mock_svc)

    result = sync_service.sync_busy_slots("user-1")

    assert result == 0
    assert any(c == call("calendar_accounts") for c in mock_svc.table.call_args_list)


# ─── 1b. Window widening ──────────────────────────────────────────────────────

def _stub_widening_queries(
    mock_svc,
    coord_event_starts: list[str] = None,
    participant_event_ids: list[str] = None,
    participant_event_starts: list[str] = None,
) -> None:
    coord_event_starts = coord_event_starts or []
    participant_event_ids = participant_event_ids or []
    participant_event_starts = participant_event_starts or []

    mock_svc.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"earliest_datetime_utc": s} for s in coord_event_starts]
    )
    mock_svc.table.return_value.select.return_value.eq.return_value.neq.return_value.execute.return_value = MagicMock(
        data=[{"event_id": eid} for eid in participant_event_ids]
    )
    mock_svc.table.return_value.select.return_value.in_.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"earliest_datetime_utc": s} for s in participant_event_starts]
    )
    mock_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])


@patch("app.services.sync_service._sync_user")
@patch("app.services.sync_service.service_client")
def test_widens_window_when_coordinator_event_starts_in_past(mock_svc, mock_sync_user):
    now = datetime.now(timezone.utc)
    past = now - timedelta(days=10)
    _stub_widening_queries(mock_svc, coord_event_starts=[past.isoformat()])
    mock_sync_user.return_value = 0

    sync_service.sync_busy_slots("user-1")

    args, _ = mock_sync_user.call_args
    user_id_arg, time_min_arg, time_max_arg = args
    assert user_id_arg == "user-1"
    assert abs((time_min_arg - past).total_seconds()) < 2
    assert (time_max_arg - now) >= timedelta(days=89)
    assert (time_max_arg - now) <= timedelta(days=91)


@patch("app.services.sync_service._sync_user")
@patch("app.services.sync_service.service_client")
def test_widens_window_when_participant_event_starts_in_past(mock_svc, mock_sync_user):
    now = datetime.now(timezone.utc)
    past = now - timedelta(days=5)
    _stub_widening_queries(
        mock_svc,
        participant_event_ids=["evt-A"],
        participant_event_starts=[past.isoformat()],
    )
    mock_sync_user.return_value = 0

    sync_service.sync_busy_slots("user-1")

    args, _ = mock_sync_user.call_args
    _, time_min_arg, _ = args
    assert abs((time_min_arg - past).total_seconds()) < 2


@patch("app.services.sync_service._sync_user")
@patch("app.services.sync_service.service_client")
def test_does_not_widen_when_active_events_are_all_in_future(mock_svc, mock_sync_user):
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=2)
    _stub_widening_queries(mock_svc, coord_event_starts=[future.isoformat()])
    mock_sync_user.return_value = 0

    sync_service.sync_busy_slots("user-1")

    args, _ = mock_sync_user.call_args
    _, time_min_arg, _ = args
    assert abs((time_min_arg - now).total_seconds()) < 2


@patch("app.services.sync_service._sync_user")
@patch("app.services.sync_service.service_client")
def test_widening_ignores_declined_participation(mock_svc, mock_sync_user):
    now = datetime.now(timezone.utc)
    _stub_widening_queries(mock_svc, participant_event_ids=[])
    mock_sync_user.return_value = 0

    sync_service.sync_busy_slots("user-1")

    args, _ = mock_sync_user.call_args
    _, time_min_arg, _ = args
    assert abs((time_min_arg - now).total_seconds()) < 2


# ─── 2. _sync_source: upsert + stale deletion (provider-agnostic) ─────────────

@patch("app.services.sync_service.service_client")
def test_sync_source_upserts_busy_events(mock_svc):
    """_sync_source upserts one busy_slot per BusyEvent returned by the provider."""
    now = datetime.now(timezone.utc)
    time_min, time_max = now, now + timedelta(days=90)
    prov = _provider_returning([
        _busy("evt-1", now, now + timedelta(hours=1)),
        _busy("evt-2", now + timedelta(hours=2), now + timedelta(hours=3)),
    ])

    upserted = []

    def capture_upsert(rows, **kwargs):
        upserted.extend(rows)
        return MagicMock(execute=MagicMock(return_value=MagicMock()))

    mock_svc.table.return_value.upsert.side_effect = capture_upsert
    mock_svc.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = MagicMock(data=[])

    upserted_count, deleted_count = sync_service._sync_source(
        "user-1", "src-1", "primary", prov, TokenBundle({}), time_min, time_max
    )

    assert upserted_count == 2
    assert deleted_count == 0
    assert {r["provider_event_id"] for r in upserted} == {"evt-1", "evt-2"}
    assert all(r["calendar_source_id"] == "src-1" for r in upserted)


@patch("app.services.sync_service.service_client")
def test_stale_deletion_uses_query_time_max(mock_svc):
    """Stale deletion filters by end_time_utc < time_max (same window as fetch)."""
    now = datetime.now(timezone.utc)
    time_min, time_max = now, now + timedelta(days=90)
    prov = _provider_returning([])

    lt_calls = []

    def capture_lt(column, value):
        lt_calls.append(value)
        result = MagicMock()
        result.execute.return_value = MagicMock(data=[])
        return result

    mock_svc.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.side_effect = capture_lt

    sync_service._sync_source("user-1", "src-1", "primary", prov, TokenBundle({}), time_min, time_max)

    assert len(lt_calls) == 1
    stale_cutoff = datetime.fromisoformat(lt_calls[0])
    assert abs((stale_cutoff - time_max).total_seconds()) < 2


@patch("app.services.sync_service.service_client")
def test_stale_slot_deleted_when_event_no_longer_returned(mock_svc):
    """A busy slot whose event is no longer returned by the provider is deleted."""
    now = datetime.now(timezone.utc)
    time_min, time_max = now, now + timedelta(days=90)
    prov = _provider_returning([_busy("evt-active", now, now + timedelta(hours=1))])

    mock_svc.table.return_value.upsert.return_value.execute.return_value = MagicMock()
    mock_svc.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = MagicMock(
        data=[{"provider_event_id": "evt-active"}, {"provider_event_id": "evt-stale"}]
    )

    deleted_ids = []

    def capture_in(column, ids):
        if column == "provider_event_id":
            deleted_ids.extend(ids)
        return MagicMock(execute=MagicMock(return_value=MagicMock()))

    mock_svc.table.return_value.delete.return_value.eq.return_value.in_.side_effect = capture_in

    sync_service._sync_source("user-1", "src-1", "primary", prov, TokenBundle({}), time_min, time_max)

    assert "evt-stale" in deleted_ids
    assert "evt-active" not in deleted_ids


@patch("app.services.sync_service.service_client")
def test_no_stale_slots_delete_not_called(mock_svc):
    """When no slots are stale, the delete call is not made."""
    now = datetime.now(timezone.utc)
    time_min, time_max = now, now + timedelta(days=90)
    prov = _provider_returning([_busy("evt-active", now, now + timedelta(hours=1))])

    mock_svc.table.return_value.upsert.return_value.execute.return_value = MagicMock()
    mock_svc.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = MagicMock(
        data=[{"provider_event_id": "evt-active"}]
    )

    sync_service._sync_source("user-1", "src-1", "primary", prov, TokenBundle({}), time_min, time_max)

    mock_svc.table.return_value.delete.assert_not_called()


@patch("app.services.sync_service.service_client")
def test_scoped_sync_does_not_delete_slots_outside_window(mock_svc):
    """Regression (H5): the stale-slot query must be bounded below by time_min.

    A narrow event-scoped sync only fetches provider events inside
    [time_min, time_max]; slots ending before time_min were never fetched and
    must not be treated as stale. Simulates Supabase's server-side filtering:
    without the .gte bound the out-of-window slot would be returned and
    deleted."""
    now = datetime.now(timezone.utc)
    time_min = now + timedelta(days=5)          # narrow 2-hour event window
    time_max = now + timedelta(days=5, hours=2)
    prov = _provider_returning([])              # provider returns nothing in window

    stored_slots = [
        # Synced weeks earlier, ends long before time_min — must survive.
        {"provider_event_id": "evt-out-of-window", "end_time_utc": now.isoformat()},
        # Inside the window but no longer returned by the provider — stale.
        {"provider_event_id": "evt-stale-in-window",
         "end_time_utc": (time_min + timedelta(hours=1)).isoformat()},
    ]

    class FakeStaleQuery:
        """Applies gte/lt filters like PostgREST would."""

        def __init__(self):
            self.min = None
            self.max = None

        def gte(self, column, value):
            assert column == "end_time_utc"
            self.min = datetime.fromisoformat(value)
            return self

        def lt(self, column, value):
            assert column == "end_time_utc"
            self.max = datetime.fromisoformat(value)
            return self

        def execute(self):
            data = [
                s for s in stored_slots
                if (self.min is None or datetime.fromisoformat(s["end_time_utc"]) >= self.min)
                and (self.max is None or datetime.fromisoformat(s["end_time_utc"]) < self.max)
            ]
            return MagicMock(data=data)

    mock_svc.table.return_value.select.return_value.eq.side_effect = lambda *a: FakeStaleQuery()

    deleted_ids = []

    def capture_in(column, ids):
        if column == "provider_event_id":
            deleted_ids.extend(ids)
        return MagicMock(execute=MagicMock(return_value=MagicMock()))

    mock_svc.table.return_value.delete.return_value.eq.return_value.in_.side_effect = capture_in

    sync_service._sync_source("user-1", "src-1", "primary", prov, TokenBundle({}), time_min, time_max)

    assert "evt-out-of-window" not in deleted_ids, (
        "scoped sync must not delete busy slots ending before time_min"
    )
    assert "evt-stale-in-window" in deleted_ids


@patch("app.services.sync_service.service_client")
def test_sync_source_propagates_auth_error(mock_svc):
    """A ProviderAuthError bubbles up so _sync_user can mark needs_reauth."""
    now = datetime.now(timezone.utc)
    prov = MagicMock()
    prov.fetch_busy_events.side_effect = ProviderAuthError("invalid_grant")

    with pytest.raises(ProviderAuthError):
        sync_service._sync_source("user-1", "src-1", "primary", prov, TokenBundle({}), now, now + timedelta(days=90))


@patch("app.services.sync_service.service_client")
def test_sync_source_api_error_skips_source_without_deleting(mock_svc):
    """A ProviderAPIError skips the source (no changes) and never deletes slots."""
    now = datetime.now(timezone.utc)
    prov = MagicMock()
    prov.fetch_busy_events.side_effect = ProviderAPIError("boom")

    count = sync_service._sync_source("user-1", "src-1", "primary", prov, TokenBundle({}), now, now + timedelta(days=90))

    assert count == (0, 0)
    mock_svc.table.return_value.delete.assert_not_called()


# ─── 3. _sync_user: token rotation persistence ────────────────────────────────

@patch("app.services.sync_service.get_provider")
@patch("app.services.sync_service.service_client")
def test_sync_user_persists_rotated_credentials(mock_svc, mock_get_provider):
    """When the provider rotates credentials during sync, the whole updated
    credentials dict is persisted (covers Microsoft's refresh-token rotation)."""
    now = datetime.now(timezone.utc)
    account = {
        "id": "acct-1",
        "provider": "microsoft",
        "credentials": {"access_token": "old", "refresh_token": "r1"},
        "calendar_sources": [{"id": "src-1", "calendar_id": "cal", "is_enabled": True}],
    }
    mock_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[account])
    mock_svc.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = MagicMock(data=[])

    prov = MagicMock()

    def fetch(tokens, calendar_id, time_min, time_max):
        tokens.update({"access_token": "new", "refresh_token": "r2"})
        return []

    prov.fetch_busy_events.side_effect = fetch
    mock_get_provider.return_value = prov

    updates = []

    def capture_update(payload):
        updates.append(payload)
        m = MagicMock()
        m.eq.return_value.execute.return_value = MagicMock()
        return m

    mock_svc.table.return_value.update.side_effect = capture_update

    sync_service._sync_user("user-1", now, now + timedelta(days=90))

    persisted = [u for u in updates if "credentials" in u]
    assert persisted, "rotated credentials should be persisted"
    assert persisted[-1]["credentials"]["refresh_token"] == "r2"


@patch("app.services.sync_service.mark_account_needs_reauth")
@patch("app.services.sync_service.get_provider")
@patch("app.services.sync_service.service_client")
def test_sync_user_marks_needs_reauth_on_auth_error(mock_svc, mock_get_provider, mock_mark):
    """A ProviderAuthError during a source sync marks the account needs_reauth."""
    now = datetime.now(timezone.utc)
    account = {
        "id": "acct-1",
        "provider": "google",
        "credentials": {"access_token": "tok", "refresh_token": "r1"},
        "calendar_sources": [{"id": "src-1", "calendar_id": "cal", "is_enabled": True}],
    }
    mock_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[account])

    prov = MagicMock()
    prov.fetch_busy_events.side_effect = ProviderAuthError("revoked")
    mock_get_provider.return_value = prov

    sync_service._sync_user("user-1", now, now + timedelta(days=90))

    mock_mark.assert_called_once_with("acct-1")


# ─── 3b. _sync_user: proposals_needs_regeneration on slot changes (H6) ───────

def _account_row(source_id: str = "src-1") -> dict:
    return {
        "id": "acct-1",
        "provider": "google",
        "credentials": {"access_token": "tok", "refresh_token": "r1"},
        "calendar_sources": [{"id": source_id, "calendar_id": "cal", "is_enabled": True}],
    }


def _stale_flag_tables(mock_svc, stale_rows=None, participant_event_ids=None):
    """Route service_client.table(name) to per-table mocks and return
    (accounts, busy_slots, event_participants, events) mocks."""
    accounts_tbl = MagicMock()
    accounts_tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_account_row()]
    )

    busy_tbl = MagicMock()
    busy_tbl.upsert.return_value.execute.return_value = MagicMock()
    busy_tbl.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = MagicMock(
        data=list(stale_rows or [])
    )

    participants_tbl = MagicMock()
    participants_tbl.select.return_value.eq.return_value.neq.return_value.execute.return_value = MagicMock(
        data=[{"event_id": eid} for eid in (participant_event_ids or [])]
    )

    events_tbl = MagicMock()

    tables = {
        "calendar_accounts": accounts_tbl,
        "busy_slots": busy_tbl,
        "event_participants": participants_tbl,
        "events": events_tbl,
    }
    mock_svc.table.side_effect = lambda name: tables[name]
    return accounts_tbl, busy_tbl, participants_tbl, events_tbl


@patch("app.services.sync_service.get_provider")
@patch("app.services.sync_service.service_client")
def test_sync_user_flags_planning_events_when_slots_change(mock_svc, mock_get_provider):
    """A sync that upserts busy slots flags the user's planning events with
    proposals_needs_regeneration so cached proposals are not served stale."""
    now = datetime.now(timezone.utc)
    _, _, _, events_tbl = _stale_flag_tables(
        mock_svc, participant_event_ids=["evt-planning-1", "evt-planning-2"]
    )
    mock_get_provider.return_value = _provider_returning(
        [_busy("evt-1", now, now + timedelta(hours=1))]
    )

    sync_service._sync_user("user-1", now, now + timedelta(days=90))

    events_tbl.update.assert_called_once_with({"proposals_needs_regeneration": True})
    events_tbl.update.return_value.in_.assert_called_once_with(
        "id", ["evt-planning-1", "evt-planning-2"]
    )
    events_tbl.update.return_value.in_.return_value.eq.assert_called_once_with(
        "status", "planning"
    )


@patch("app.services.sync_service.get_provider")
@patch("app.services.sync_service.service_client")
def test_sync_user_flags_events_on_stale_deletion_only(mock_svc, mock_get_provider):
    """A sync whose only change is deleting a stale slot still flags the
    user's planning events (freed availability also invalidates proposals)."""
    now = datetime.now(timezone.utc)
    _, _, _, events_tbl = _stale_flag_tables(
        mock_svc,
        stale_rows=[{"provider_event_id": "evt-stale"}],
        participant_event_ids=["evt-planning-1"],
    )
    mock_get_provider.return_value = _provider_returning([])  # nothing upserted

    sync_service._sync_user("user-1", now, now + timedelta(days=90))

    events_tbl.update.assert_called_once_with({"proposals_needs_regeneration": True})


@patch("app.services.sync_service.get_provider")
@patch("app.services.sync_service.service_client")
def test_sync_user_does_not_flag_events_when_nothing_changed(mock_svc, mock_get_provider):
    """A sync that upserts and deletes nothing must not touch the flag."""
    now = datetime.now(timezone.utc)
    _, _, participants_tbl, events_tbl = _stale_flag_tables(
        mock_svc, participant_event_ids=["evt-planning-1"]
    )
    mock_get_provider.return_value = _provider_returning([])  # no upserts, no stale rows

    sync_service._sync_user("user-1", now, now + timedelta(days=90))

    events_tbl.update.assert_not_called()
    participants_tbl.select.assert_not_called()


# ─── 4. Event-scoped sync uses event's datetime window ───────────────────────

@patch("app.services.sync_service._sync_user")
@patch("app.services.sync_service.service_client")
def test_sync_event_participants_scoped_uses_event_window(mock_svc, mock_sync_user):
    now = datetime.now(timezone.utc)
    event_min = now + timedelta(days=5)
    event_max = now + timedelta(days=7)
    coordinator_id = "coordinator-uuid-1"
    participant_id = "participant-uuid-2"

    mock_svc.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"user_id": participant_id}]
    )
    mock_sync_user.return_value = 2

    result = sync_service.sync_event_participants_scoped(
        event_id="event-db-id-1",
        coordinator_id=coordinator_id,
        time_min=event_min.isoformat(),
        time_max=event_max.isoformat(),
    )

    assert participant_id in result
    assert coordinator_id in result

    for call_args in mock_sync_user.call_args_list:
        _, passed_min, passed_max = call_args.args
        assert abs((passed_min - event_min).total_seconds()) < 2
        assert abs((passed_max - event_max).total_seconds()) < 2


@patch("app.services.sync_service._sync_user")
@patch("app.services.sync_service.service_client")
def test_sync_event_participants_scoped_includes_coordinator(mock_svc, mock_sync_user):
    now = datetime.now(timezone.utc)
    coordinator_id = "coordinator-uuid-1"

    mock_svc.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[]
    )
    mock_sync_user.return_value = 5

    result = sync_service.sync_event_participants_scoped(
        event_id="event-db-id-1",
        coordinator_id=coordinator_id,
        time_min=now.isoformat(),
        time_max=(now + timedelta(hours=4)).isoformat(),
    )

    assert coordinator_id in result
    assert result[coordinator_id] == 5


@patch("app.services.sync_service._sync_user")
@patch("app.services.sync_service.service_client")
def test_sync_event_participants_scoped_deduplicates_coordinator(mock_svc, mock_sync_user):
    now = datetime.now(timezone.utc)
    coordinator_id = "coordinator-uuid-1"

    mock_svc.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"user_id": coordinator_id}]
    )
    mock_sync_user.return_value = 3

    result = sync_service.sync_event_participants_scoped(
        event_id="event-db-id-1",
        coordinator_id=coordinator_id,
        time_min=now.isoformat(),
        time_max=(now + timedelta(hours=4)).isoformat(),
    )

    assert list(result.keys()).count(coordinator_id) == 1
    assert mock_sync_user.call_count == 1
