"""Sprint 3 — Invitation tests.

Tests the invitations router and service with mocked Supabase clients.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
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


def _make_invitation_row(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    defaults = {
        "id": "invite-uuid-1",
        "event_id": "event-db-id-1",
        "inviter_id": "inviter-uuid-1",
        "invitee_id": "user-uuid-1",  # matches current user for respond tests
        "invitee_email": "alice@example.com",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    return {**defaults, **overrides}


def _current_user_profile() -> dict:
    return {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}


# ─── 1. test_invite_existing_user_success ────────────────────────────────────

@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_invite_existing_user_success(mock_dep_svc, mock_get_authed, mock_inv_svc):
    """POST /api/events/{uid}/invite → 201, creates invitation and notification for existing user."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    invite_row = _make_invitation_row(invitee_email="bob@example.com", invitee_id="invitee-uuid-1")
    invitee_profile = {"id": "invitee-uuid-1"}

    # Route db calls by table name
    def make_db_table(table_name):
        tbl = MagicMock()
        if table_name == "events":
            event_row = {"id": "event-db-id-1", "coordinator_id": "user-uuid-1", "name": "Team Lunch"}
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
        elif table_name == "event_participants":
            # can_invite check: user-uuid-1 IS coordinator, so can_invite check returns participant row
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
        return tbl

    db = MagicMock()
    db.table.side_effect = make_db_table
    mock_get_authed.return_value = db

    # Route service_client calls by table name
    def make_svc_table(table_name):
        tbl = MagicMock()
        if table_name == "profiles":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=invitee_profile)
        elif table_name == "event_invitations":
            tbl.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            tbl.insert.return_value.execute.return_value = MagicMock(data=[invite_row])
        elif table_name == "notifications":
            tbl.insert.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    mock_inv_svc.table.side_effect = make_svc_table

    response = client.post(
        "/api/events/event-uid-1/invite",
        json={"email": "bob@example.com"},
        headers=_auth_headers(),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["invitee_email"] == "bob@example.com"


# ─── 2. test_invite_no_account_success ───────────────────────────────────────

@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_invite_no_account_success(mock_dep_svc, mock_get_authed, mock_inv_svc):
    """POST .../invite with email that has no account → 201 with invitee_id=None."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    db = MagicMock()
    mock_get_authed.return_value = db

    event_row = {"id": "event-db-id-1", "coordinator_id": "user-uuid-1", "name": "Team Lunch"}
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={"can_invite": True})

    # No profile found
    mock_inv_svc.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
    mock_inv_svc.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)

    invite_row = _make_invitation_row(invitee_id=None)
    mock_inv_svc.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[invite_row])

    response = client.post(
        "/api/events/event-uid-1/invite",
        json={"email": "newperson@example.com"},
        headers=_auth_headers(),
    )
    assert response.status_code == 201
    assert response.json()["invitee_id"] is None


# ─── 3. test_invite_already_participant ──────────────────────────────────────

@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_invite_already_participant(mock_dep_svc, mock_get_authed, mock_inv_svc):
    """POST .../invite with email of existing participant → 409."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    db = MagicMock()
    mock_get_authed.return_value = db

    event_row = {"id": "event-db-id-1", "coordinator_id": "user-uuid-1", "name": "Team Lunch"}
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={"can_invite": True})

    # Profile found
    mock_inv_svc.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={"id": "invitee-uuid-1"})
    # Already a participant
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={"user_id": "invitee-uuid-1"})

    response = client.post(
        "/api/events/event-uid-1/invite",
        json={"email": "bob@example.com"},
        headers=_auth_headers(),
    )
    assert response.status_code == 409


# ─── 4. test_invite_not_participant ──────────────────────────────────────────

@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_invite_not_participant(mock_dep_svc, mock_get_authed, mock_inv_svc):
    """POST .../invite when requester is not a participant → 403."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    db = MagicMock()
    mock_get_authed.return_value = db

    event_row = {"id": "event-db-id-1", "coordinator_id": "other-coordinator", "name": "Team Lunch"}
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    # Not a participant
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)

    response = client.post(
        "/api/events/event-uid-1/invite",
        json={"email": "bob@example.com"},
        headers=_auth_headers(),
    )
    assert response.status_code == 403


# ─── 5. test_respond_accept ──────────────────────────────────────────────────

@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_respond_accept(mock_dep_svc, mock_get_authed, mock_inv_svc):
    """PUT /api/invitations/{id}/respond with accept → 204, joins event."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    db = MagicMock()
    mock_get_authed.return_value = db

    invite_row = _make_invitation_row(status="pending")
    mock_inv_svc.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=invite_row)
    mock_inv_svc.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])
    mock_inv_svc.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    event_data = {"coordinator_id": "other-coord", "name": "Team Lunch"}
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_data)

    response = client.put(
        "/api/invitations/invite-uuid-1/respond",
        json={"action": "accept"},
        headers=_auth_headers(),
    )
    assert response.status_code == 204


# ─── 6. test_respond_decline ─────────────────────────────────────────────────

@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_respond_decline(mock_dep_svc, mock_get_authed, mock_inv_svc):
    """PUT /api/invitations/{id}/respond with decline → 204."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    db = MagicMock()
    mock_get_authed.return_value = db

    invite_row = _make_invitation_row(status="pending")
    mock_inv_svc.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=invite_row)
    mock_inv_svc.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    response = client.put(
        "/api/invitations/invite-uuid-1/respond",
        json={"action": "decline"},
        headers=_auth_headers(),
    )
    assert response.status_code == 204


# ─── 7. test_respond_wrong_user ──────────────────────────────────────────────

@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_respond_wrong_user(mock_dep_svc, mock_get_authed, mock_inv_svc):
    """PUT /api/invitations/{id}/respond when invitation belongs to different user → 403."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    db = MagicMock()
    mock_get_authed.return_value = db

    # Invitation belongs to someone else
    invite_row = _make_invitation_row(invitee_id="some-other-user")
    mock_inv_svc.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=invite_row)

    response = client.put(
        "/api/invitations/invite-uuid-1/respond",
        json={"action": "accept"},
        headers=_auth_headers(),
    )
    assert response.status_code == 403


# ─── 8. test_respond_accept_no_calendar_raises_422 ───────────────────────────

@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_respond_accept_no_calendar_raises_422(mock_dep_svc, mock_get_authed, mock_inv_svc):
    """PUT /api/invitations/{id}/respond with action='accept' when user has no
    calendar_sources rows → 422 calendar_required."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    db = MagicMock()
    mock_get_authed.return_value = db

    invite_row = _make_invitation_row(status="pending")

    def make_svc_table(table_name):
        tbl = MagicMock()
        if table_name == "event_invitations":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=invite_row)
        elif table_name == "calendar_sources":
            # No connected calendar for this user
            tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    mock_inv_svc.table.side_effect = make_svc_table

    response = client.put(
        "/api/invitations/invite-uuid-1/respond",
        json={"action": "accept"},
        headers=_auth_headers(),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "calendar_required"
