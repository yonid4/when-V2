"""Sprint 8 — Busy slot router + service tests.

Covers:
- Endpoint 1 (GET /api/busy-slots): my slots, auth required
- Endpoint 2 (GET /api/busy-slots/event/{uid}): 403 for non-participant,
  declined participant exclusion, missing event → 404, happy path
- Endpoint 3 (POST /api/busy-slots/sync): 200 with synced count
- Endpoint 4 (POST /api/busy-slots/sync/event/{uid}): missing event → 404,
  403 for non-coordinator, happy path
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
    return {
        "id": user_id,
        "email_address": "alice@example.com",
        "full_name": "Alice",
        "avatar_url": None,
    }


def _make_busy_slot(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "id": "slot-uuid-1",
        "user_id": "user-uuid-1",
        "calendar_source_id": "source-uuid-1",
        "start_time_utc": now.isoformat(),
        "end_time_utc": (now + timedelta(hours=1)).isoformat(),
    }
    return {**defaults, **overrides}


def _event_row(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "id": "event-db-id-1",
        "coordinator_id": "coordinator-uuid-1",
        "earliest_datetime_utc": now.isoformat(),
        "latest_datetime_utc": (now + timedelta(hours=4)).isoformat(),
    }
    return {**defaults, **overrides}


# ─── Endpoint 1: GET /api/busy-slots ─────────────────────────────────────────

@patch("app.services.busy_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_get_my_busy_slots_returns_list(mock_dep_svc, mock_service_svc):
    """GET /api/busy-slots → 200 with the current user's busy slots."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    slot = _make_busy_slot()
    mock_service_svc.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
        data=[slot]
    )

    response = client.get("/api/busy-slots", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["id"] == "slot-uuid-1"


def test_get_my_busy_slots_requires_auth():
    """GET /api/busy-slots without token → 403."""
    response = client.get("/api/busy-slots")
    assert response.status_code == 403


# ─── Endpoint 2: GET /api/busy-slots/event/{uid} ─────────────────────────────

def _make_event_busy_slots_table(
    event_data,
    participant_data,
    auth_participant_data=None,
    busy_slot_data=None,
):
    """Build a per-table side_effect for busy-slots-service mock.

    The service issues two distinct queries against event_participants:
      1. Auth check: .eq(event_id).eq(user_id).in_(...).maybe_single().execute()
      2. Non-declined list: .eq(event_id).neq("status","declined").execute()

    We model this by counting how many times .eq() has been called and
    returning different mock chains for each call depth.

    auth_participant_data — value for the authorization participant lookup.
                            Pass None to simulate "not a participant" (403).
    """

    def make_table(table_name):
        tbl = MagicMock()
        if table_name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_data
            )
        elif table_name == "event_participants":
            # Auth check chain: .eq(event_id).eq(user_id).in_(...).maybe_single().execute()
            auth_execute = MagicMock(data=auth_participant_data)
            auth_chain = MagicMock()
            auth_chain.execute.return_value = auth_execute

            # The second .eq() leads into the auth chain (.in_.maybe_single.execute)
            second_eq = MagicMock()
            second_eq.in_.return_value.maybe_single.return_value = auth_chain

            # Non-declined list chain: .eq(event_id).neq("status","declined").execute()
            list_execute = MagicMock(data=participant_data)
            list_chain = MagicMock()
            list_chain.execute.return_value = list_execute

            # First .eq() returns an object that handles both possible next calls:
            # - .eq(user_id, ...) → second_eq (auth path)
            # - .neq("status", ...) → list_chain (list path)
            first_eq = MagicMock()
            first_eq.eq.return_value = second_eq
            first_eq.neq.return_value = list_chain

            tbl.select.return_value.eq.return_value = first_eq

        elif table_name == "busy_slots":
            slot_data = busy_slot_data if busy_slot_data is not None else []
            tbl.select.return_value.in_.return_value.lt.return_value.gt.return_value.order.return_value.execute.return_value = MagicMock(
                data=slot_data
            )
        return tbl

    return make_table


@patch("app.services.busy_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_get_event_busy_slots_coordinator_sees_slots(mock_dep_svc, mock_service_svc):
    """GET /api/busy-slots/event/{uid} → 200 for the coordinator."""
    # Coordinator is calling → user_id == coordinator_id
    coordinator_id = "user-uuid-1"
    event = _event_row(coordinator_id=coordinator_id)

    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile(coordinator_id)
    )

    slot = _make_busy_slot(user_id="participant-uuid-2")

    mock_service_svc.table.side_effect = _make_event_busy_slots_table(
        event_data=event,
        participant_data=[{"user_id": "participant-uuid-2"}],
        auth_participant_data={"user_id": coordinator_id},  # not reached for coordinator
        busy_slot_data=[slot],
    )

    response = client.get("/api/busy-slots/event/test-uid-1", headers=_auth_headers(coordinator_id))
    assert response.status_code == 200
    assert len(response.json()) == 1


@patch("app.services.busy_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_get_event_busy_slots_non_participant_gets_403(mock_dep_svc, mock_service_svc):
    """GET /api/busy-slots/event/{uid} → 403 for a user who is not a participant."""
    outsider_id = "outsider-uuid-99"
    event = _event_row(coordinator_id="coordinator-uuid-1")

    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile(outsider_id)
    )

    # Authorization lookup returns None → not a participant
    mock_service_svc.table.side_effect = _make_event_busy_slots_table(
        event_data=event,
        participant_data=[],
        auth_participant_data=None,
    )

    response = client.get("/api/busy-slots/event/test-uid-1", headers=_auth_headers(outsider_id))
    assert response.status_code == 403


@patch("app.services.busy_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_get_event_busy_slots_accepted_participant_allowed(mock_dep_svc, mock_service_svc):
    """GET /api/busy-slots/event/{uid} → 200 for an accepted participant."""
    participant_id = "user-uuid-1"
    event = _event_row(coordinator_id="coordinator-uuid-1")

    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile(participant_id)
    )

    slot = _make_busy_slot(user_id=participant_id)
    mock_service_svc.table.side_effect = _make_event_busy_slots_table(
        event_data=event,
        participant_data=[{"user_id": participant_id}],
        auth_participant_data={"user_id": participant_id},
        busy_slot_data=[slot],
    )

    response = client.get("/api/busy-slots/event/test-uid-1", headers=_auth_headers(participant_id))
    assert response.status_code == 200
    assert response.json()[0]["user_id"] == participant_id


@patch("app.services.busy_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_get_event_busy_slots_declined_participant_excluded(mock_dep_svc, mock_service_svc):
    """GET /api/busy-slots/event/{uid}: the participant query uses neq('status','declined'),
    so declined users' slots are not fetched.  Simulated by returning an empty participant list."""
    participant_id = "user-uuid-1"
    event = _event_row(coordinator_id="coordinator-uuid-1")

    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile(participant_id)
    )

    # Participant passes auth check but the full list returns empty (declined excluded by DB filter)
    mock_service_svc.table.side_effect = _make_event_busy_slots_table(
        event_data=event,
        participant_data=[],          # declined users filtered server-side → empty list
        auth_participant_data={"user_id": participant_id},
        busy_slot_data=[],
    )

    response = client.get("/api/busy-slots/event/test-uid-1", headers=_auth_headers(participant_id))
    assert response.status_code == 200
    assert response.json() == []


@patch("app.services.busy_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_get_event_busy_slots_missing_event_returns_404(mock_dep_svc, mock_service_svc):
    """GET /api/busy-slots/event/{uid} → 404 when the event does not exist (maybe_single path)."""
    user_id = "user-uuid-1"
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile(user_id)
    )

    # maybe_single returns None → event not found
    mock_service_svc.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=None
    )

    response = client.get("/api/busy-slots/event/nonexistent-uid", headers=_auth_headers(user_id))
    assert response.status_code == 404


# ─── Endpoint 3: POST /api/busy-slots/sync ───────────────────────────────────

@patch("app.services.sync_service.service_client")
@patch("app.dependencies.service_client")
def test_sync_my_slots_returns_synced_count(mock_dep_svc, mock_sync_svc):
    """POST /api/busy-slots/sync → 200 with synced=0 when no calendar accounts."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    mock_sync_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )

    response = client.post("/api/busy-slots/sync", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["synced"] == 0


# ─── Endpoint 4: POST /api/busy-slots/sync/event/{uid} ───────────────────────

@patch("app.services.busy_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_sync_event_slots_missing_event_returns_404(mock_dep_svc, mock_service_svc):
    """POST /api/busy-slots/sync/event/{uid} → 404 when event does not exist."""
    coordinator_id = "user-uuid-1"
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile(coordinator_id)
    )

    # maybe_single returns None
    mock_service_svc.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=None
    )

    response = client.post(
        "/api/busy-slots/sync/event/nonexistent-uid", headers=_auth_headers(coordinator_id)
    )
    assert response.status_code == 404


@patch("app.services.busy_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_sync_event_slots_non_coordinator_gets_403(mock_dep_svc, mock_service_svc):
    """POST /api/busy-slots/sync/event/{uid} → 403 for non-coordinator."""
    user_id = "user-uuid-1"
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile(user_id)
    )

    mock_service_svc.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=_event_row(coordinator_id="other-user-uuid")
    )

    response = client.post(
        "/api/busy-slots/sync/event/test-uid-1", headers=_auth_headers(user_id)
    )
    assert response.status_code == 403


@patch("app.services.sync_service.sync_event_participants_scoped")
@patch("app.services.busy_slots_service.service_client")
@patch("app.dependencies.service_client")
def test_sync_event_slots_coordinator_triggers_scoped_sync(
    mock_dep_svc, mock_service_svc, mock_scoped_sync
):
    """POST /api/busy-slots/sync/event/{uid} → 200 for coordinator, scoped sync called."""
    coordinator_id = "user-uuid-1"
    now = datetime.now(timezone.utc)
    event = _event_row(
        coordinator_id=coordinator_id,
        earliest_datetime_utc=now.isoformat(),
        latest_datetime_utc=(now + timedelta(hours=4)).isoformat(),
    )

    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile(coordinator_id)
    )
    mock_service_svc.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=event
    )
    mock_scoped_sync.return_value = {coordinator_id: 3, "participant-uuid-2": 2}

    response = client.post(
        "/api/busy-slots/sync/event/test-uid-1", headers=_auth_headers(coordinator_id)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["synced"] == 5
    mock_scoped_sync.assert_called_once()
