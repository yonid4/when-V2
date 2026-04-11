"""Sprint 3 — Participant tests.

Tests the participants router and service with mocked Supabase clients.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User

client = TestClient(app)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-uuid-1",
        "email_address": "alice@example.com",
        "full_name": "Alice",
        "avatar_url": None,
        "token": "valid-token",
    }
    return User(**{**defaults, **overrides})


def _auth_headers(user_id: str = "user-uuid-1", email: str = "alice@example.com") -> dict:
    from datetime import timedelta
    from jose import jwt
    from app.config import settings
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = jwt.encode(
        {"sub": user_id, "email": email, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def _make_participant_row(user_id: str = "user-uuid-1", **overrides) -> dict:
    defaults = {
        "event_id": "event-db-id-1",
        "user_id": user_id,
        "status": "accepted",
        "rsvp_status": "going",
        "can_invite": False,
        "joined_at": "2026-04-01T00:00:00+00:00",
        "full_name": "Alice",
        "avatar_url": None,
        "email_address": "alice@example.com",
    }
    return {**defaults, **overrides}


def _make_event_row(**overrides) -> dict:
    defaults = {"id": "event-db-id-1", "coordinator_id": "user-uuid-1"}
    return {**defaults, **overrides}


# ─── 1. test_get_participants_success ─────────────────────────────────────────

@patch("app.services.event_service.service_client")
@patch("app.services.participant_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_get_participants_success(mock_dep_svc, mock_get_authed, mock_svc):
    """GET /api/events/{uid}/participants → 200 with participant list."""
    profile = {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)
    mock_svc.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"id": "user-uuid-1", "full_name": "Alice", "avatar_url": None, "email_address": "alice@example.com"}]
    )

    db = MagicMock()
    mock_get_authed.return_value = db

    event_row = _make_event_row()
    participant_raw = {
        "event_id": "event-db-id-1",
        "user_id": "user-uuid-1",
        "status": "accepted",
        "rsvp_status": "going",
        "can_invite": False,
        "joined_at": "2026-04-01T00:00:00+00:00",
    }

    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[participant_raw])

    headers = _auth_headers()
    response = client.get("/api/events/event-uid-1/participants", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["user_id"] == "user-uuid-1"


# ─── 2. test_get_participants_not_member ──────────────────────────────────────

@patch("app.services.event_service.service_client")
@patch("app.services.participant_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_get_participants_not_member(mock_dep_svc, mock_get_authed, mock_svc):
    """GET /api/events/{uid}/participants → 403 when current user is not a participant."""
    profile = {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)
    mock_svc.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"id": "other-user", "full_name": "Bob", "avatar_url": None, "email_address": "bob@example.com"}]
    )

    db = MagicMock()
    mock_get_authed.return_value = db

    event_row = _make_event_row()
    # Participant list has no entry for user-uuid-1
    other_participant = {
        "event_id": "event-db-id-1",
        "user_id": "other-user",
        "status": "accepted",
        "rsvp_status": "going",
        "can_invite": False,
        "joined_at": "2026-04-01T00:00:00+00:00",
    }

    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[other_participant])

    response = client.get("/api/events/event-uid-1/participants", headers=_auth_headers())
    assert response.status_code == 403


# ─── 3. test_update_rsvp_own_status ──────────────────────────────────────────

@patch("app.services.event_service.service_client")
@patch("app.services.participant_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_update_rsvp_own_status(mock_dep_svc, mock_get_authed, mock_svc):
    """PUT /api/events/{uid}/participants/{user_id}/rsvp → 200 when updating own RSVP."""
    profile = {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)
    mock_svc.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"id": "user-uuid-1", "full_name": "Alice", "avatar_url": None, "email_address": "alice@example.com"}]
    )

    db = MagicMock()
    mock_get_authed.return_value = db

    event_row = _make_event_row()
    updated_participant = {
        "event_id": "event-db-id-1",
        "user_id": "user-uuid-1",
        "status": "accepted",
        "rsvp_status": "maybe",
        "can_invite": False,
        "joined_at": "2026-04-01T00:00:00+00:00",
    }

    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[updated_participant])

    response = client.put(
        "/api/events/event-uid-1/participants/user-uuid-1/rsvp",
        json={"rsvp_status": "maybe"},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    assert response.json()["rsvp_status"] == "maybe"


# ─── 4. test_update_rsvp_other_user_forbidden ────────────────────────────────

@patch("app.services.participant_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_update_rsvp_other_user_forbidden(mock_dep_svc, mock_get_authed):
    """PUT .../rsvp for another user_id → 403."""
    profile = {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

    db = MagicMock()
    mock_get_authed.return_value = db

    response = client.put(
        "/api/events/event-uid-1/participants/other-user-id/rsvp",
        json={"rsvp_status": "going"},
        headers=_auth_headers(),
    )
    assert response.status_code == 403


# ─── 5. test_update_permissions_coordinator_only ─────────────────────────────

@patch("app.services.participant_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_update_permissions_coordinator_only(mock_dep_svc, mock_get_authed):
    """PUT .../permissions → 403 when non-coordinator attempts it."""
    profile = {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

    db = MagicMock()
    mock_get_authed.return_value = db

    # Event has a different coordinator
    event_row = {"id": "event-db-id-1", "coordinator_id": "other-coordinator"}
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)

    response = client.put(
        "/api/events/event-uid-1/participants/some-user/permissions",
        json={"can_invite": True},
        headers=_auth_headers(),
    )
    assert response.status_code == 403


# ─── 6. test_remove_participant_self ─────────────────────────────────────────

@patch("app.services.participant_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_remove_participant_self(mock_dep_svc, mock_get_authed):
    """DELETE .../participants/{user_id} → 204 when user removes themselves."""
    profile = {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

    db = MagicMock()
    mock_get_authed.return_value = db

    # Not coordinator, but is_self is True
    event_row = {"id": "event-db-id-1", "coordinator_id": "other-coordinator"}
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    db.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    response = client.delete(
        "/api/events/event-uid-1/participants/user-uuid-1",
        headers=_auth_headers(),
    )
    assert response.status_code == 204


# ─── 7. test_remove_participant_not_allowed ───────────────────────────────────

@patch("app.services.participant_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_remove_participant_not_allowed(mock_dep_svc, mock_get_authed):
    """DELETE .../participants/{user_id} → 403 when non-coordinator targets another user."""
    profile = {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

    db = MagicMock()
    mock_get_authed.return_value = db

    event_row = {"id": "event-db-id-1", "coordinator_id": "other-coordinator"}
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)

    response = client.delete(
        "/api/events/event-uid-1/participants/some-other-user",
        headers=_auth_headers(),
    )
    assert response.status_code == 403


# ─── 8. test_get_participants_event_not_found ─────────────────────────────────

@patch("app.services.participant_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_get_participants_event_not_found(mock_dep_svc, mock_get_authed):
    """GET /api/events/{uid}/participants → 404 when event doesn't exist."""
    profile = {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

    db = MagicMock()
    mock_get_authed.return_value = db
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)

    response = client.get("/api/events/nonexistent-uid/participants", headers=_auth_headers())
    assert response.status_code == 404


# ─── 9. test_update_permissions_success ──────────────────────────────────────

@patch("app.services.event_service.service_client")
@patch("app.services.participant_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_update_permissions_success(mock_dep_svc, mock_get_authed, mock_svc):
    """PUT .../permissions → 200 when coordinator grants can_invite."""
    profile = {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)
    mock_svc.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"id": "target-user-id", "full_name": "Bob", "avatar_url": None, "email_address": "bob@example.com"}]
    )

    db = MagicMock()
    mock_get_authed.return_value = db

    # user-uuid-1 is coordinator
    event_row = {"id": "event-db-id-1", "coordinator_id": "user-uuid-1"}
    updated_participant = {
        "event_id": "event-db-id-1",
        "user_id": "target-user-id",
        "status": "accepted",
        "rsvp_status": "going",
        "can_invite": True,
        "joined_at": "2026-04-01T00:00:00+00:00",
    }

    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[updated_participant])

    response = client.put(
        "/api/events/event-uid-1/participants/target-user-id/permissions",
        json={"can_invite": True},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    assert response.json()["can_invite"] is True
