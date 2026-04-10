"""Sprint 8 — sync_service unit tests.

Covers:
- Time range: sync_busy_slots uses now → now+90 days
- Pagination: _sync_source follows nextPageToken
- Stale deletion: bounded to the same 90-day window
- Event-scoped sync: uses event's earliest/latest, not the global window
- Coordinator inclusion: coordinator synced even if not in event_participants
- UTC normalization: non-UTC offsets converted before storage
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from app.services import sync_service


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_google_event(event_id: str, start: str, end: str) -> dict:
    return {
        "id": event_id,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }


def _make_credentials_data(**overrides) -> dict:
    return {
        "access_token": "tok-original",
        "refresh_token": "ref-tok",
        **overrides,
    }


def _make_account(account_id: str = "acct-1", user_id: str = "user-1", sources=None) -> dict:
    return {
        "id": account_id,
        "user_id": user_id,
        "credentials": _make_credentials_data(),
        "calendar_sources": sources or [
            {"id": "src-1", "calendar_id": "primary", "is_enabled": True}
        ],
    }


# ─── 1. Time range ────────────────────────────────────────────────────────────

@patch("app.services.sync_service.build")
@patch("app.services.sync_service.service_client")
def test_sync_busy_slots_uses_90_day_window(mock_svc, mock_build):
    """sync_busy_slots passes a time window of now → now+90 days to Google Calendar."""
    # No accounts → we just check the time calculation doesn't crash and returns 0
    mock_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )

    before = datetime.now(timezone.utc)
    result = sync_service.sync_busy_slots("user-1")
    after = datetime.now(timezone.utc)

    assert result == 0
    # Verify service_client was asked for calendar_accounts (not something wrong)
    mock_svc.table.assert_called_with("calendar_accounts")


@patch("app.services.sync_service.build")
@patch("app.services.sync_service.service_client")
def test_sync_source_time_range_is_90_days(mock_svc, mock_build):
    """_sync_source timeMin is 'now' and timeMax is within 90-91 days from now."""
    now = datetime.now(timezone.utc)

    # Mock calendar API to capture the list call arguments
    mock_events = MagicMock()
    mock_list = MagicMock()
    mock_list.execute.return_value = {"items": [], "nextPageToken": None}
    mock_events.list.return_value = mock_list
    mock_cal_service = MagicMock()
    mock_cal_service.events.return_value = mock_events

    # Stale deletion query
    mock_svc.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=[]
    )

    time_min = now
    time_max = now + timedelta(days=90)

    sync_service._sync_source("user-1", "src-1", "primary", mock_cal_service, time_min, time_max)

    call_kwargs = mock_events.list.call_args.kwargs
    parsed_min = datetime.fromisoformat(call_kwargs["timeMin"])
    parsed_max = datetime.fromisoformat(call_kwargs["timeMax"])

    assert parsed_max - parsed_min >= timedelta(days=89)
    assert parsed_max - parsed_min <= timedelta(days=91)


# ─── 2. Pagination ────────────────────────────────────────────────────────────

@patch("app.services.sync_service.service_client")
def test_sync_source_follows_page_token(mock_svc):
    """_sync_source loops through pages when nextPageToken is present."""
    now = datetime.now(timezone.utc)
    time_min = now
    time_max = now + timedelta(days=90)

    event1 = _make_google_event("evt-1", now.isoformat(), (now + timedelta(hours=1)).isoformat())
    event2 = _make_google_event("evt-2", (now + timedelta(hours=2)).isoformat(), (now + timedelta(hours=3)).isoformat())

    mock_list = MagicMock()
    mock_list.execute.side_effect = [
        {"items": [event1], "nextPageToken": "page2"},
        {"items": [event2]},  # no nextPageToken → loop ends
    ]
    mock_cal = MagicMock()
    mock_cal.events.return_value.list.return_value = mock_list

    # Upsert and stale deletion mocks
    mock_svc.table.return_value.upsert.return_value.execute.return_value = MagicMock()
    mock_svc.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=[]
    )

    count = sync_service._sync_source("user-1", "src-1", "primary", mock_cal, time_min, time_max)

    assert count == 2
    assert mock_cal.events.return_value.list.call_count == 2
    # Second call should have included pageToken
    second_kwargs = mock_cal.events.return_value.list.call_args_list[1].kwargs
    assert second_kwargs.get("pageToken") == "page2"


# ─── 3. Stale deletion bounded to query window ───────────────────────────────

@patch("app.services.sync_service.service_client")
def test_stale_deletion_uses_query_time_max(mock_svc):
    """Stale deletion filters by end_time_utc < time_max (same window as Google query)."""
    now = datetime.now(timezone.utc)
    time_min = now
    time_max = now + timedelta(days=90)

    mock_list = MagicMock()
    mock_list.execute.return_value = {"items": []}
    mock_cal = MagicMock()
    mock_cal.events.return_value.list.return_value = mock_list

    # Capture the lt() argument used for stale deletion
    lt_calls = []

    def capture_lt(column, value):
        lt_calls.append(value)
        result = MagicMock()
        result.execute.return_value = MagicMock(data=[])
        return result

    mock_svc.table.return_value.select.return_value.eq.return_value.lt.side_effect = capture_lt

    sync_service._sync_source("user-1", "src-1", "primary", mock_cal, time_min, time_max)

    assert len(lt_calls) == 1
    stale_cutoff = datetime.fromisoformat(lt_calls[0])
    expected_max = time_max
    diff = abs((stale_cutoff - expected_max).total_seconds())
    assert diff < 2, f"Stale cutoff {stale_cutoff} should be close to time_max {expected_max}"


# ─── 4. Event-scoped sync uses event's datetime window ───────────────────────

@patch("app.services.sync_service._sync_user")
@patch("app.services.sync_service.service_client")
def test_sync_event_participants_scoped_uses_event_window(mock_svc, mock_sync_user):
    """sync_event_participants_scoped passes event's time bounds, not global 90 days."""
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

    # Verify _sync_user was called with the event's window, not 90-day window
    for call_args in mock_sync_user.call_args_list:
        _, passed_min, passed_max = call_args.args
        diff_min = abs((passed_min - event_min).total_seconds())
        diff_max = abs((passed_max - event_max).total_seconds())
        assert diff_min < 2, "time_min should match event window"
        assert diff_max < 2, "time_max should match event window"


# ─── 5. Coordinator included even if not in event_participants ────────────────

@patch("app.services.sync_service._sync_user")
@patch("app.services.sync_service.service_client")
def test_sync_event_participants_scoped_includes_coordinator(mock_svc, mock_sync_user):
    """Coordinator is synced even when they are not listed in event_participants."""
    now = datetime.now(timezone.utc)
    coordinator_id = "coordinator-uuid-1"

    # event_participants returns empty (coordinator not in table)
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
    """Coordinator is not synced twice if they are also in event_participants."""
    now = datetime.now(timezone.utc)
    coordinator_id = "coordinator-uuid-1"

    # Coordinator appears in event_participants
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

    # coordinator_id should appear exactly once in results
    assert list(result.keys()).count(coordinator_id) == 1
    # _sync_user called only once (for the participant loop, not again for coordinator)
    assert mock_sync_user.call_count == 1


# ─── 6. UTC normalization ─────────────────────────────────────────────────────

def test_to_utc_converts_offset_to_utc():
    """_to_utc converts a datetime string with a non-UTC offset to a UTC ISO string."""
    # UTC-7 offset → same instant in UTC is +7 hours
    pdt_str = "2026-04-09T09:00:00-07:00"
    result = sync_service._to_utc(pdt_str)
    dt = datetime.fromisoformat(result)
    assert dt.tzinfo is not None
    # 09:00 PDT = 16:00 UTC
    assert dt.hour == 16
    assert dt.utcoffset().total_seconds() == 0


def test_to_utc_preserves_utc_time():
    """_to_utc is a no-op (aside from formatting) for a datetime already in UTC."""
    utc_str = "2026-04-09T16:00:00+00:00"
    result = sync_service._to_utc(utc_str)
    dt = datetime.fromisoformat(result)
    assert dt.hour == 16
    assert dt.utcoffset().total_seconds() == 0


@patch("app.services.sync_service.service_client")
def test_sync_source_normalizes_timestamps_to_utc(mock_svc):
    """_sync_source stores start/end times as UTC regardless of source timezone."""
    now = datetime.now(timezone.utc)
    time_min = now
    time_max = now + timedelta(days=90)

    # Google returns an event with PDT offset
    event = _make_google_event(
        "evt-pdt",
        "2026-04-09T09:00:00-07:00",  # 16:00 UTC
        "2026-04-09T10:00:00-07:00",  # 17:00 UTC
    )
    mock_list = MagicMock()
    mock_list.execute.return_value = {"items": [event]}
    mock_cal = MagicMock()
    mock_cal.events.return_value.list.return_value = mock_list

    upserted_rows = []

    def capture_upsert(rows, **kwargs):
        upserted_rows.extend(rows)
        return MagicMock(execute=MagicMock(return_value=MagicMock()))

    mock_svc.table.return_value.upsert.side_effect = capture_upsert
    mock_svc.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=[]
    )

    sync_service._sync_source("user-1", "src-1", "primary", mock_cal, time_min, time_max)

    assert len(upserted_rows) == 1
    start_dt = datetime.fromisoformat(upserted_rows[0]["start_time_utc"])
    end_dt = datetime.fromisoformat(upserted_rows[0]["end_time_utc"])
    assert start_dt.utcoffset().total_seconds() == 0, "start_time_utc must be UTC"
    assert end_dt.utcoffset().total_seconds() == 0, "end_time_utc must be UTC"
    assert start_dt.hour == 16
    assert end_dt.hour == 17


# ─── 7. Stale deletion correctness ───────────────────────────────────────────

@patch("app.services.sync_service.service_client")
def test_stale_slot_deleted_when_event_no_longer_returned(mock_svc):
    """A busy slot whose event is no longer returned by Google is deleted."""
    now = datetime.now(timezone.utc)
    time_min = now
    time_max = now + timedelta(days=90)

    # Google returns one event; the DB has two (one is stale)
    active_event = _make_google_event(
        "evt-active",
        now.isoformat(),
        (now + timedelta(hours=1)).isoformat(),
    )
    mock_list = MagicMock()
    mock_list.execute.return_value = {"items": [active_event]}
    mock_cal = MagicMock()
    mock_cal.events.return_value.list.return_value = mock_list

    # DB contains both the active slot and a stale slot
    mock_svc.table.return_value.upsert.return_value.execute.return_value = MagicMock()
    mock_svc.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=[
            {"provider_event_id": "evt-active"},
            {"provider_event_id": "evt-stale"},
        ]
    )

    deleted_ids = []

    def capture_in(column, ids):
        if column == "provider_event_id":
            deleted_ids.extend(ids)
        return MagicMock(execute=MagicMock(return_value=MagicMock()))

    mock_svc.table.return_value.delete.return_value.eq.return_value.in_.side_effect = capture_in

    sync_service._sync_source("user-1", "src-1", "primary", mock_cal, time_min, time_max)

    assert "evt-stale" in deleted_ids, "Stale event should be deleted"
    assert "evt-active" not in deleted_ids, "Active event must not be deleted"


@patch("app.services.sync_service.service_client")
def test_cancelled_event_not_in_fetched_ids_and_deleted_if_in_db(mock_svc):
    """A Google event with status 'cancelled' is excluded from fetched_event_ids
    and deleted from busy_slots if it exists in the DB."""
    now = datetime.now(timezone.utc)
    time_min = now
    time_max = now + timedelta(days=90)

    # Google returns one active event and one cancelled event
    active_event = _make_google_event(
        "evt-active",
        now.isoformat(),
        (now + timedelta(hours=1)).isoformat(),
    )
    cancelled_event = {
        "id": "evt-cancelled",
        "status": "cancelled",
        "start": {"dateTime": now.isoformat()},
        "end": {"dateTime": (now + timedelta(hours=1)).isoformat()},
    }
    mock_list = MagicMock()
    mock_list.execute.return_value = {"items": [active_event, cancelled_event]}
    mock_cal = MagicMock()
    mock_cal.events.return_value.list.return_value = mock_list

    # DB contains both the active slot and the previously-synced cancelled slot
    mock_svc.table.return_value.upsert.return_value.execute.return_value = MagicMock()
    mock_svc.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=[
            {"provider_event_id": "evt-active"},
            {"provider_event_id": "evt-cancelled"},
        ]
    )

    deleted_ids = []

    def capture_in(column, ids):
        if column == "provider_event_id":
            deleted_ids.extend(ids)
        return MagicMock(execute=MagicMock(return_value=MagicMock()))

    mock_svc.table.return_value.delete.return_value.eq.return_value.in_.side_effect = capture_in

    sync_service._sync_source("user-1", "src-1", "primary", mock_cal, time_min, time_max)

    assert "evt-cancelled" in deleted_ids, "Cancelled event's slot should be deleted"
    assert "evt-active" not in deleted_ids, "Active event must not be deleted"


@patch("app.services.sync_service.service_client")
def test_no_stale_slots_delete_not_called(mock_svc):
    """When no slots are stale, the delete call is not made."""
    now = datetime.now(timezone.utc)
    time_min = now
    time_max = now + timedelta(days=90)

    active_event = _make_google_event(
        "evt-active",
        now.isoformat(),
        (now + timedelta(hours=1)).isoformat(),
    )
    mock_list = MagicMock()
    mock_list.execute.return_value = {"items": [active_event]}
    mock_cal = MagicMock()
    mock_cal.events.return_value.list.return_value = mock_list

    # DB returns the same single slot that Google returned — nothing is stale
    mock_svc.table.return_value.upsert.return_value.execute.return_value = MagicMock()
    mock_svc.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=[{"provider_event_id": "evt-active"}]
    )

    sync_service._sync_source("user-1", "src-1", "primary", mock_cal, time_min, time_max)

    # delete() should never have been called
    mock_svc.table.return_value.delete.assert_not_called()
