"""Sprint 2 — Event CRUD tests.

Tests the event service layer with mocked Supabase clients.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest
from fastapi import HTTPException

from app.models.event import EventCreate, EventUpdate, EventResponse
from app.models.participant import ParticipantResponse
from app.models.user import User
from app.services import event_service


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-1",
        "email_address": "alice@example.com",
        "full_name": "Alice",
        "avatar_url": None,
        "token": "fake-jwt-token",
    }
    return User(**{**defaults, **overrides})


def _make_event_row(**overrides) -> dict:
    defaults = {
        "id": "evt-uuid-1",
        "uid": "abc123def456",
        "name": "Team Standup",
        "description": "Daily sync",
        "event_type": "meeting",
        "coordinator_id": "user-1",
        "earliest_datetime_utc": "2026-04-10T09:00:00+00:00",
        "latest_datetime_utc": "2026-04-10T17:00:00+00:00",
        "duration_minutes": 30,
        "status": "planning",
        "location": None,
        "video_call_link": None,
        "finalized_start_time_utc": None,
        "finalized_end_time_utc": None,
        "google_calendar_event_id": None,
        "proposals_needs_regeneration": False,
        "proposals_last_generated_at": None,
        "created_at": "2026-04-01T00:00:00+00:00",
        "updated_at": "2026-04-01T00:00:00+00:00",
        "finalized_at": None,
    }
    return {**defaults, **overrides}


def _make_participant_row(**overrides) -> dict:
    defaults = {
        "event_id": "evt-uuid-1",
        "user_id": "user-1",
        "status": "accepted",
        "rsvp_status": "going",
        "can_invite": True,
        "joined_at": "2026-04-01T00:00:00+00:00",
        "full_name": "Alice",
        "avatar_url": None,
        "email_address": "alice@example.com",
    }
    return {**defaults, **overrides}


def _make_chain():
    """Create a fresh chainable mock (every builder method returns itself)."""
    chain = MagicMock()
    for m in ("eq", "neq", "in_", "single", "maybe_single"):
        getattr(chain, m).return_value = chain
    return chain


def _mock_db():
    """Return a mock Supabase client.

    Same table name → same table mock (cached).
    Each operation (select/insert/update/delete) returns its OWN chain
    so select().eq().execute() and update().eq().execute() don't collide.
    """
    db = MagicMock()
    tables = {}

    def _get_table(table_name):
        if table_name not in tables:
            table = MagicMock()
            # Each operation gets its own chain
            for op in ("select", "insert", "update", "delete"):
                chain = _make_chain()
                getattr(table, op).return_value = chain
            tables[table_name] = table
        return tables[table_name]

    db.table = MagicMock(side_effect=_get_table)
    return db


def _make_ep_row(**overrides):
    """Flat event_participant row (no profile data — fetched separately via service_client)."""
    base = _make_participant_row(**overrides)
    return {
        "event_id": base["event_id"],
        "user_id": base["user_id"],
        "status": base["status"],
        "rsvp_status": base["rsvp_status"],
        "can_invite": base["can_invite"],
        "joined_at": base["joined_at"],
    }


def _make_profile_row(**overrides):
    """Profile row as returned by service_client profiles lookup."""
    base = _make_participant_row(**overrides)
    return {
        "id": base["user_id"],
        "full_name": base["full_name"],
        "avatar_url": base["avatar_url"],
        "email_address": base["email_address"],
    }


def _mock_service_client_profiles(profile_rows: list[dict]):
    """Return a mock service_client that returns the given profile rows."""
    mock_sc = MagicMock()
    profiles_chain = _make_chain()
    profiles_chain.execute.return_value = MagicMock(data=profile_rows)
    mock_sc.table.return_value.select.return_value = profiles_chain
    return mock_sc


# ─── 1. create_event — happy path ────────────────────────────────────────────

@patch("app.services.event_service.service_client")
@patch("app.services.event_service.get_authed_client")
@patch("app.services.event_service.generate_uid", return_value="abc123def456")
def test_create_event_happy_path(mock_uid, mock_get_client, mock_sc):
    user = _make_user()
    db = _mock_db()
    mock_get_client.return_value = db
    mock_sc.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[_make_profile_row()]
    )

    event_row = _make_event_row()

    events_table = db.table("events")
    events_table.insert.return_value.execute.return_value = MagicMock(data=[event_row])

    ep_table = db.table("event_participants")
    ep_table.insert.return_value.execute.return_value = MagicMock(data=[])
    ep_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_make_ep_row()]
    )

    data = EventCreate(
        name="Team Standup",
        event_type="meeting",
        earliest_datetime_utc=datetime(2026, 4, 10, 9, tzinfo=timezone.utc),
        latest_datetime_utc=datetime(2026, 4, 10, 17, tzinfo=timezone.utc),
        duration_minutes=30,
    )

    result = event_service.create_event(data, user)

    assert result.uid == "abc123def456"
    assert result.name == "Team Standup"
    assert result.coordinator_id == "user-1"
    assert len(result.participants) == 1


# ─── 2. create_event — coordinator inserted as participant with rsvp going ──

@patch("app.services.event_service.get_authed_client")
@patch("app.services.event_service.generate_uid", return_value="xyz789aaa111")
def test_create_event_adds_coordinator_as_going_participant(mock_uid, mock_get_client):
    user = _make_user()
    db = _mock_db()
    mock_get_client.return_value = db

    event_row = _make_event_row(uid="xyz789aaa111")

    events_table = db.table("events")
    events_table.insert.return_value.execute.return_value = MagicMock(data=[event_row])

    ep_table = db.table("event_participants")
    ep_table.insert.return_value.execute.return_value = MagicMock(data=[])
    ep_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    data = EventCreate(
        name="Test",
        event_type="social",
        earliest_datetime_utc=datetime(2026, 4, 10, 9, tzinfo=timezone.utc),
        latest_datetime_utc=datetime(2026, 4, 10, 17, tzinfo=timezone.utc),
        duration_minutes=60,
    )

    event_service.create_event(data, user)

    # Verify the participant insert was called with rsvp_status='going'
    ep_insert_call = ep_table.insert.call_args[0][0]
    assert ep_insert_call["rsvp_status"] == "going"
    assert ep_insert_call["user_id"] == "user-1"
    assert ep_insert_call["status"] == "accepted"


# ─── 3. get_events_for_user — returns events ────────────────────────────────

@patch("app.services.event_service.get_authed_client")
def test_get_events_for_user(mock_get_client):
    user = _make_user()
    db = _mock_db()
    mock_get_client.return_value = db

    event_rows = [_make_event_row(), _make_event_row(id="evt-2", uid="second_event")]

    events_table = db.table("events")
    events_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=event_rows)

    ep_table = db.table("event_participants")
    ep_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    results = event_service.get_events_for_user(user)

    assert len(results) == 2
    assert results[0].uid == "abc123def456"
    assert results[1].uid == "second_event"


# ─── 4. get_event_by_uid — happy path ────────────────────────────────────────

@patch("app.services.event_service.service_client")
@patch("app.services.event_service.get_authed_client")
def test_get_event_by_uid_happy_path(mock_get_client, mock_sc):
    user = _make_user()
    db = _mock_db()
    mock_get_client.return_value = db
    mock_sc.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[_make_profile_row()]
    )

    event_row = _make_event_row()

    events_table = db.table("events")
    events_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)

    ep_table = db.table("event_participants")
    ep_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_make_ep_row()]
    )

    result = event_service.get_event_by_uid("abc123def456", user)

    assert result.name == "Team Standup"
    assert len(result.participants) == 1
    assert result.participants[0].full_name == "Alice"


# ─── 5. get_event_by_uid — 404 when not found ────────────────────────────────

@patch("app.services.event_service.get_authed_client")
def test_get_event_by_uid_not_found(mock_get_client):
    user = _make_user()
    db = _mock_db()
    mock_get_client.return_value = db

    events_table = db.table("events")
    events_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)

    with pytest.raises(HTTPException) as exc_info:
        event_service.get_event_by_uid("nonexistent", user)

    assert exc_info.value.status_code == 404


# ─── 6. get_event_by_uid — 403 when not coordinator or participant ───────────

@patch("app.services.event_service.service_client")
@patch("app.services.event_service.get_authed_client")
def test_get_event_by_uid_access_denied(mock_get_client, mock_sc):
    other_user = _make_user(id="user-other")
    db = _mock_db()
    mock_get_client.return_value = db
    mock_sc.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[_make_profile_row()]
    )

    event_row = _make_event_row(coordinator_id="user-1")

    events_table = db.table("events")
    events_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)

    ep_table = db.table("event_participants")
    ep_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_make_ep_row()]  # only user-1 is participant
    )

    with pytest.raises(HTTPException) as exc_info:
        event_service.get_event_by_uid("abc123def456", other_user)

    assert exc_info.value.status_code == 403


# ─── 7. update_event — happy path ────────────────────────────────────────────

@patch("app.services.event_service.get_authed_client")
def test_update_event_happy_path(mock_get_client):
    user = _make_user()
    db = _mock_db()
    mock_get_client.return_value = db

    event_row = _make_event_row()
    updated_row = _make_event_row(name="Updated Name")

    events_table = db.table("events")
    events_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    events_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[updated_row])

    ep_table = db.table("event_participants")
    ep_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    data = EventUpdate(name="Updated Name")
    result = event_service.update_event("abc123def456", data, user)

    assert result.name == "Updated Name"


# ─── 8. update_event — proposals_needs_regeneration on window change ─────────

@patch("app.services.event_service.get_authed_client")
def test_update_event_marks_proposals_regen_on_window_change(mock_get_client):
    user = _make_user()
    db = _mock_db()
    mock_get_client.return_value = db

    event_row = _make_event_row()
    updated_row = _make_event_row(proposals_needs_regeneration=True)

    events_table = db.table("events")
    events_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    events_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[updated_row])

    ep_table = db.table("event_participants")
    ep_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    new_earliest = datetime(2026, 5, 1, 9, tzinfo=timezone.utc)
    data = EventUpdate(earliest_datetime_utc=new_earliest)
    result = event_service.update_event("abc123def456", data, user)

    # Verify the update payload includes proposals_needs_regeneration = True
    update_call_data = events_table.update.call_args[0][0]
    assert update_call_data["proposals_needs_regeneration"] is True


# ─── 9. update_event — 403 when not coordinator ──────────────────────────────

@patch("app.services.event_service.get_authed_client")
def test_update_event_non_coordinator_forbidden(mock_get_client):
    other_user = _make_user(id="user-other")
    db = _mock_db()
    mock_get_client.return_value = db

    event_row = _make_event_row(coordinator_id="user-1")

    events_table = db.table("events")
    events_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)

    data = EventUpdate(name="Hacked")

    with pytest.raises(HTTPException) as exc_info:
        event_service.update_event("abc123def456", data, other_user)

    assert exc_info.value.status_code == 403


# ─── 10. delete_event — sends notifications and deletes ──────────────────────

@patch("app.services.event_service.service_client")
@patch("app.services.event_service.get_authed_client")
def test_delete_event_notifies_participants(mock_get_client, mock_svc):
    user = _make_user()
    db = _mock_db()
    mock_get_client.return_value = db

    event_row = {"id": "evt-uuid-1", "coordinator_id": "user-1", "name": "Team Standup"}

    events_table = db.table("events")
    events_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    events_table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    ep_table = db.table("event_participants")
    ep_table.select.return_value.eq.return_value.neq.return_value.execute.return_value = MagicMock(
        data=[{"user_id": "user-2"}, {"user_id": "user-3"}]
    )

    notif_table = MagicMock()
    notif_table.insert.return_value.execute.return_value = MagicMock(data=[])
    mock_svc.table.return_value = notif_table

    event_service.delete_event("abc123def456", user)

    # Verify notifications were inserted for 2 other participants
    notif_insert_data = notif_table.insert.call_args[0][0]
    assert len(notif_insert_data) == 2
    assert all(n["notification_type"] == "event_deleted" for n in notif_insert_data)
    assert {n["user_id"] for n in notif_insert_data} == {"user-2", "user-3"}
