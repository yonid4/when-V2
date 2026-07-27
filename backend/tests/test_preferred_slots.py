"""Sprint 5B — Preferred slots tests.

Tests the preferred_slots router with mocked Supabase service_client.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.config import settings

client = TestClient(app)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _auth_headers(user_id: str = "user-uuid-1", email: str = "alice@example.com") -> dict:
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = jwt.encode(
        {"sub": user_id, "email": email, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def _current_user_profile(user_id: str = "user-uuid-1") -> dict:
    return {"id": user_id, "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}


def _make_event_row(**overrides) -> dict:
    defaults = {
        "id": "event-db-id-1",
        "coordinator_id": "coordinator-uuid-1",
    }
    return {**defaults, **overrides}


def _make_slot_row(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    defaults = {
        "id": "slot-uuid-1",
        "event_id": "event-db-id-1",
        "user_id": "user-uuid-1",
        "start_time_utc": "2026-04-10T10:00:00+00:00",
        "end_time_utc": "2026-04-10T10:30:00+00:00",
        "created_at": now,
    }
    return {**defaults, **overrides}


# ─── POST tests ───────────────────────────────────────────────────────────────

@patch("app.services.preferred_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_create_preferred_slot_success(mock_dep_svc, mock_router_svc):
    """POST /api/events/{uid}/preferred-slots → 201, returns created slot."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1")
    slot_row = _make_slot_row()

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            # _get_event_and_check_participant lookup
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
            # update proposals_needs_regeneration
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.in_.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"user_id": "user-uuid-1"}
            )
        elif name == "preferred_slots":
            tbl.insert.return_value.execute.return_value = MagicMock(data=[slot_row])
        return tbl

    mock_router_svc.table.side_effect = make_table

    # user-uuid-1 is NOT the coordinator — they are a participant
    response = client.post(
        "/api/events/event-uid-1/preferred-slots",
        json={"start_time_utc": "2026-04-10T10:00:00+00:00", "end_time_utc": "2026-04-10T10:30:00+00:00"},
        headers=_auth_headers("user-uuid-1"),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "slot-uuid-1"
    assert data["user_id"] == "user-uuid-1"
    assert data["start_time_utc"] == "2026-04-10T10:00:00+00:00"


@patch("app.services.preferred_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_create_preferred_slot_sets_regeneration_flag(mock_dep_svc, mock_router_svc):
    """POST should set proposals_needs_regeneration=true on the event."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("coordinator-uuid-1")
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1")
    slot_row = _make_slot_row(user_id="coordinator-uuid-1")

    events_mock = MagicMock()
    events_mock.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    update_chain = MagicMock()
    events_mock.update.return_value = update_chain

    slots_mock = MagicMock()
    slots_mock.insert.return_value.execute.return_value = MagicMock(data=[slot_row])

    def make_table(name):
        if name == "events":
            return events_mock
        elif name == "preferred_slots":
            return slots_mock
        return MagicMock()

    mock_router_svc.table.side_effect = make_table

    response = client.post(
        "/api/events/event-uid-1/preferred-slots",
        json={"start_time_utc": "2026-04-10T10:00:00+00:00", "end_time_utc": "2026-04-10T10:30:00+00:00"},
        headers=_auth_headers("coordinator-uuid-1"),
    )
    assert response.status_code == 201
    # Verify update was called with regeneration flag
    events_mock.update.assert_called_once_with({"proposals_needs_regeneration": True})


@patch("app.services.preferred_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_create_preferred_slot_403_not_participant(mock_dep_svc, mock_router_svc):
    """POST → 403 when user is neither coordinator nor participant."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("outsider-uuid")
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1")

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
        elif name == "event_participants":
            # Not a participant
            tbl.select.return_value.eq.return_value.eq.return_value.in_.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=None
            )
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.post(
        "/api/events/event-uid-1/preferred-slots",
        json={"start_time_utc": "2026-04-10T10:00:00+00:00", "end_time_utc": "2026-04-10T10:30:00+00:00"},
        headers=_auth_headers("outsider-uuid"),
    )
    assert response.status_code == 403


# ─── GET tests ────────────────────────────────────────────────────────────────

@patch("app.services.preferred_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_get_preferred_slots_success(mock_dep_svc, mock_router_svc):
    """GET /api/events/{uid}/preferred-slots → 200, returns all participants' slots."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("coordinator-uuid-1")
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1")
    slot_row = _make_slot_row(user_id="coordinator-uuid-1")

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
        elif name == "preferred_slots":
            # Only one .eq() now (event_id), no user_id filter
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[slot_row])
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.get(
        "/api/events/event-uid-1/preferred-slots",
        headers=_auth_headers("coordinator-uuid-1"),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "slot-uuid-1"


@patch("app.services.preferred_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_get_preferred_slots_returns_all_participants(mock_dep_svc, mock_router_svc):
    """GET returns slots from multiple participants, not just the requesting user."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("coordinator-uuid-1")
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1")
    slot_alice = _make_slot_row(id="slot-alice", user_id="alice-uuid")
    slot_bob = _make_slot_row(id="slot-bob", user_id="bob-uuid",
                              start_time_utc="2026-04-10T11:00:00+00:00",
                              end_time_utc="2026-04-10T11:30:00+00:00")

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
        elif name == "preferred_slots":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[slot_alice, slot_bob])
        return tbl

    mock_router_svc.table.side_effect = make_table

    # coordinator calls GET — should receive slots from both alice and bob
    response = client.get(
        "/api/events/event-uid-1/preferred-slots",
        headers=_auth_headers("coordinator-uuid-1"),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    user_ids = {s["user_id"] for s in data}
    assert "alice-uuid" in user_ids
    assert "bob-uuid" in user_ids


@patch("app.services.preferred_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_get_preferred_slots_403_not_participant(mock_dep_svc, mock_router_svc):
    """GET → 403 when user is not a participant or coordinator."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("outsider-uuid")
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1")

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.in_.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=None
            )
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.get(
        "/api/events/event-uid-1/preferred-slots",
        headers=_auth_headers("outsider-uuid"),
    )
    assert response.status_code == 403


# ─── DELETE tests ─────────────────────────────────────────────────────────────

@patch("app.services.preferred_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_delete_preferred_slot_success(mock_dep_svc, mock_router_svc):
    """DELETE /api/events/{uid}/preferred-slots/{slot_id} → 204."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("user-uuid-1")
    )

    slot_row = _make_slot_row(user_id="user-uuid-1")

    def make_table(name):
        tbl = MagicMock()
        if name == "preferred_slots":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=slot_row)
            tbl.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.delete(
        "/api/events/event-uid-1/preferred-slots/slot-uuid-1",
        headers=_auth_headers("user-uuid-1"),
    )
    assert response.status_code == 204


@patch("app.services.preferred_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_delete_preferred_slot_sets_regeneration_flag(mock_dep_svc, mock_router_svc):
    """DELETE should set proposals_needs_regeneration=true on the event,
    symmetric with create (M10)."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("user-uuid-1")
    )

    slot_row = _make_slot_row(user_id="user-uuid-1")  # event_id = event-db-id-1

    events_mock = MagicMock()

    slots_mock = MagicMock()
    slots_mock.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=slot_row)
    slots_mock.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    def make_table(name):
        if name == "events":
            return events_mock
        elif name == "preferred_slots":
            return slots_mock
        return MagicMock()

    mock_router_svc.table.side_effect = make_table

    response = client.delete(
        "/api/events/event-uid-1/preferred-slots/slot-uuid-1",
        headers=_auth_headers("user-uuid-1"),
    )
    assert response.status_code == 204
    # Verify update was called with regeneration flag on the slot's event
    events_mock.update.assert_called_once_with({"proposals_needs_regeneration": True})
    events_mock.update.return_value.eq.assert_called_once_with("id", "event-db-id-1")


@patch("app.services.preferred_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_delete_preferred_slot_403_not_owner(mock_dep_svc, mock_router_svc):
    """DELETE → 403 when slot belongs to a different user."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("other-user-uuid")
    )

    # Slot belongs to user-uuid-1, not other-user-uuid
    slot_row = _make_slot_row(user_id="user-uuid-1")

    def make_table(name):
        tbl = MagicMock()
        if name == "preferred_slots":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=slot_row)
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.delete(
        "/api/events/event-uid-1/preferred-slots/slot-uuid-1",
        headers=_auth_headers("other-user-uuid"),
    )
    assert response.status_code == 403
