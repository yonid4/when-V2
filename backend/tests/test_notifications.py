"""Sprint 3 — Notification tests.

Tests the notifications router and service with mocked Supabase clients.
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


def _make_notification_row(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    defaults = {
        "id": "notif-uuid-1",
        "user_id": "user-uuid-1",
        "event_id": "event-db-id-1",
        "notification_type": "event_invitation",
        "title": "You have been invited",
        "message": "You have been invited to Team Lunch.",
        "is_read": False,
        "action_taken": False,
        "action_type": None,
        "metadata": {"invitation_id": "invite-uuid-1"},
        "created_at": now,
        "read_at": None,
        "action_at": None,
    }
    return {**defaults, **overrides}


def _current_user_profile() -> dict:
    return {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}


# ─── 1. test_get_notifications_success ───────────────────────────────────────

@patch("app.services.notification_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_get_notifications_success(mock_dep_svc, mock_get_authed):
    """GET /api/notifications → 200 with list of notifications."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    db = MagicMock()
    mock_get_authed.return_value = db

    notif = _make_notification_row()
    db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[notif])

    response = client.get("/api/notifications", headers=_auth_headers())

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["id"] == "notif-uuid-1"
    assert data[0]["notification_type"] == "event_invitation"


# ─── 2. test_get_notifications_empty ─────────────────────────────────────────

@patch("app.services.notification_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_get_notifications_empty(mock_dep_svc, mock_get_authed):
    """GET /api/notifications → 200 with empty list when user has no notifications."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    db = MagicMock()
    mock_get_authed.return_value = db
    db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])

    response = client.get("/api/notifications", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == []


# ─── 3. test_mark_read_success ───────────────────────────────────────────────

@patch("app.services.notification_service.service_client")
@patch("app.services.notification_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_mark_read_success(mock_dep_svc, mock_get_authed, mock_notif_svc):
    """POST /api/notifications/{id}/read → 200 with updated notification."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    db = MagicMock()
    mock_get_authed.return_value = db

    notif = _make_notification_row()
    db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[notif])

    updated_notif = {**notif, "is_read": True}
    mock_notif_svc.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[updated_notif])

    response = client.post("/api/notifications/notif-uuid-1/read", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["is_read"] is True


# ─── 4. test_mark_read_other_user ────────────────────────────────────────────

@patch("app.services.notification_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_mark_read_other_user(mock_dep_svc, mock_get_authed):
    """POST /api/notifications/{id}/read → 403 when notification belongs to another user."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    db = MagicMock()
    mock_get_authed.return_value = db

    # Notification belongs to someone else
    notif = _make_notification_row(user_id="some-other-user")
    db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[notif])

    response = client.post("/api/notifications/notif-uuid-1/read", headers=_auth_headers())

    assert response.status_code == 403


# ─── 5. test_take_action_accept ──────────────────────────────────────────────

@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.services.notification_service.service_client")
@patch("app.services.notification_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_take_action_accept(mock_dep_svc, mock_notif_authed, mock_notif_svc, mock_inv_authed, mock_inv_svc):
    """POST /api/notifications/{id}/action with accept → 200, calls respond_to_invitation."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    notif = _make_notification_row(notification_type="event_invitation", metadata={"invitation_id": "invite-uuid-1"})

    # Invitation for respond_to_invitation
    now = datetime.now(timezone.utc).isoformat()
    invite_row = {
        "id": "invite-uuid-1",
        "event_id": "event-db-id-1",
        "inviter_id": "other-user",
        "invitee_id": "user-uuid-1",
        "invitee_email": "alice@example.com",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }

    updated_notif = {**notif, "action_taken": True, "action_type": "accept"}

    # Route db calls by table name to avoid chain collision
    notif_call_count = {"n": 0}
    def make_db_table(table_name):
        tbl = MagicMock()
        if table_name == "notifications":
            # First call: fetch to verify ownership; second call: re-fetch after update
            notif_call_count["n"] += 1
            row = notif if notif_call_count["n"] == 1 else updated_notif
            tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[row])
        elif table_name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={"coordinator_id": "other-user", "name": "Team Lunch"})
        elif table_name == "event_participants":
            tbl.insert.return_value.execute.return_value = MagicMock(data=[{}])
        return tbl

    db = MagicMock()
    db.table.side_effect = make_db_table
    mock_notif_authed.return_value = db
    mock_inv_authed.return_value = db

    mock_inv_svc.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=invite_row)
    mock_inv_svc.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])
    mock_inv_svc.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    mock_notif_svc.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[updated_notif])

    response = client.post(
        "/api/notifications/notif-uuid-1/action",
        json={"action": "accept"},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] is True
    assert data["action_type"] == "accept"


# ─── 5b. test_take_action_already_responded_syncs_notification ───────────────

@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.services.notification_service.service_client")
@patch("app.services.notification_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_take_action_already_responded_syncs_notification(
    mock_dep_svc, mock_notif_authed, mock_notif_svc, mock_inv_authed, mock_inv_svc
):
    """An invitation already responded to (e.g. via an older flow) does not 409
    the client; the notification is stamped using the invitation's real status."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    notif = _make_notification_row(notification_type="event_invitation", metadata={"invitation_id": "invite-uuid-1"})
    # Invitation was already accepted, but the stale notification still offered buttons.
    updated_notif = {**notif, "action_taken": True, "action_type": "accept"}

    now = datetime.now(timezone.utc).isoformat()
    invite_row = {
        "id": "invite-uuid-1",
        "event_id": "event-db-id-1",
        "inviter_id": "other-user",
        "invitee_id": "user-uuid-1",
        "invitee_email": "alice@example.com",
        "status": "accepted",  # no longer pending → respond_to_invitation raises 409
        "created_at": now,
        "updated_at": now,
    }

    # notif get_authed_client db: ownership fetch (call 1) then refresh (call 2)
    notif_call_count = {"n": 0}
    def make_db_table(table_name):
        tbl = MagicMock()
        if table_name == "notifications":
            notif_call_count["n"] += 1
            row = notif if notif_call_count["n"] == 1 else updated_notif
            tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[row])
        return tbl
    db = MagicMock()
    db.table.side_effect = make_db_table
    mock_notif_authed.return_value = db
    mock_inv_authed.return_value = db

    # invitation_service.service_client: invitation is already accepted → 409 inside respond
    mock_inv_svc.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=invite_row)

    # notification_service.service_client: route by table name
    def make_notif_svc_table(table_name):
        tbl = MagicMock()
        if table_name == "event_invitations":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={"status": "accepted"})
        elif table_name == "notifications":
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[updated_notif])
        return tbl
    mock_notif_svc.table.side_effect = make_notif_svc_table

    # User clicks Decline on the stale invite, but it was already accepted.
    response = client.post(
        "/api/notifications/notif-uuid-1/action",
        json={"action": "decline"},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] is True
    # Reflects the invitation's real status, not the (stale) click.
    assert data["action_type"] == "accept"


# ─── 6. test_notifications_require_auth ──────────────────────────────────────

def test_notifications_require_auth():
    """GET /api/notifications without token → 403 (HTTPBearer)."""
    response = client.get("/api/notifications")
    assert response.status_code == 403
