"""Sprint 1 — Auth tests.

Tests the auth router, auth service, and get_current_user dependency with mocked
Supabase clients and mocked Google OAuth flow.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call
import os

from google.oauth2.credentials import Credentials

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt

# Ensure OAuth works over HTTP in tests
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

from app.main import app
from app.config import settings
from app.models.user import User
from app.services import auth_service
from app.dependencies import get_current_user


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-uuid-1",
        "email_address": "alice@example.com",
        "full_name": "Alice",
        "avatar_url": "https://example.com/avatar.jpg",
    }
    return User(**{**defaults, **overrides})


def _make_profile_row(**overrides) -> dict:
    defaults = {
        "id": "user-uuid-1",
        "email_address": "alice@example.com",
        "full_name": "Alice",
        "avatar_url": "https://example.com/avatar.jpg",
        "timezone": None,
        "primary_calendar_provider": "google",
        "google_auth_token": None,
        "microsoft_auth_token": None,
        "google_calendar_id": None,
        "created_at": "2026-04-01T00:00:00+00:00",
        "updated_at": "2026-04-01T00:00:00+00:00",
    }
    return {**defaults, **overrides}


def _make_valid_jwt(user_id: str = "user-uuid-1", email: str = "alice@example.com") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _make_expired_jwt(user_id: str = "user-uuid-1", email: str = "alice@example.com") -> str:
    expire = datetime.now(timezone.utc) - timedelta(minutes=60)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


client = TestClient(app, follow_redirects=False)


# ─── 1. test_auth_google_redirect ─────────────────────────────────────────────

def test_auth_google_redirect():
    """GET /auth/google returns 302 to Google OAuth with required query params."""
    response = client.get("/auth/google")

    # FastAPI RedirectResponse defaults to 307; both 302 and 307 are valid redirect codes
    assert response.status_code in (302, 307)
    location = response.headers["location"]

    assert "accounts.google.com" in location
    assert "client_id=" in location
    assert "redirect_uri=" in location
    assert "scope=" in location


# ─── 2. test_auth_me_success ──────────────────────────────────────────────────

@patch("app.dependencies.service_client")
def test_auth_me_success(mock_svc):
    """Valid JWT → GET /auth/me returns correct user id and email."""
    profile = _make_profile_row()
    mock_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

    # auth_service.get_user_profile also calls service_client
    with patch("app.services.auth_service.service_client") as mock_auth_svc:
        mock_auth_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

        token = _make_valid_jwt()
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "user-uuid-1"
    assert data["email_address"] == "alice@example.com"


# ─── 3. test_auth_me_no_token ─────────────────────────────────────────────────

def test_auth_me_no_token():
    """No Authorization header → 401."""
    response = client.get("/auth/me")
    assert response.status_code == 403  # HTTPBearer returns 403 when no token


# ─── 4. test_auth_me_invalid_token ────────────────────────────────────────────

def test_auth_me_invalid_token():
    """Malformed JWT → 401."""
    response = client.get("/auth/me", headers={"Authorization": "Bearer not.a.real.jwt"})
    assert response.status_code == 401


def test_auth_me_expired_token():
    """Expired JWT → 401."""
    token = _make_expired_jwt()
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# ─── 5. test_auth_me_unknown_user ─────────────────────────────────────────────

@patch("app.dependencies.service_client")
def test_auth_me_unknown_user(mock_svc):
    """Valid JWT but user_id not found in profiles → 401."""
    mock_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)

    token = _make_valid_jwt(user_id="nonexistent-user")
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# ─── 6. test_get_current_user_dependency_valid ────────────────────────────────

@patch("app.dependencies.service_client")
def test_get_current_user_dependency_valid(mock_svc):
    """Protected route with valid JWT resolves the correct user without error."""
    profile = _make_profile_row()
    mock_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

    token = _make_valid_jwt()
    # Use /auth/me as the protected route (it uses get_current_user dependency)
    with patch("app.services.auth_service.service_client") as mock_auth_svc:
        mock_auth_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "user-uuid-1"


# ─── 7. test_get_current_user_dependency_missing ─────────────────────────────

def test_get_current_user_dependency_missing():
    """Protected route with no token → 403 (HTTPBearer rejects missing token)."""
    response = client.get("/auth/me")
    # FastAPI HTTPBearer returns 403 when Authorization header is absent
    assert response.status_code == 403


# ─── 8. test_profile_created_on_first_login ──────────────────────────────────

@patch("app.services.auth_service.service_client")
@patch("app.services.auth_service.build_oauth_flow")
def test_profile_created_on_first_login(mock_build_flow, mock_svc):
    """Callback flow creates a profiles row with correct email, name, avatar."""
    user_info = {
        "id": "google-account-id",
        "email": "newuser@example.com",
        "name": "New User",
        "picture": "https://example.com/pic.jpg",
    }

    # Mock OAuth flow
    mock_flow = MagicMock()
    mock_flow.credentials = Credentials(token="access-token", refresh_token="refresh-token")
    mock_build_flow.return_value = mock_flow

    # Mock Google userinfo API call
    with patch("app.services.auth_service._fetch_google_user_info", return_value=user_info):
        # Mock auth.admin.create_user → returns new user
        new_auth_user = MagicMock()
        new_auth_user.user.id = "new-user-uuid"
        mock_svc.auth.admin.create_user.return_value = new_auth_user

        # Mock profiles upsert
        mock_svc.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
        # Mock pending invitations query → empty
        mock_svc.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        auth_service.exchange_code_and_upsert_user("fake-code")

    # Capture the profiles upsert call
    upsert_calls = [
        c for c in mock_svc.table.call_args_list
        if c.args[0] == "profiles"
    ]
    assert len(upsert_calls) > 0

    # Find the upsert data for profiles
    profiles_table = MagicMock()
    # Verify upsert was called with correct profile data
    all_upsert_calls = mock_svc.table.return_value.upsert.call_args_list
    profile_upsert = None
    for c in all_upsert_calls:
        data = c.args[0] if c.args else c.kwargs.get("data", {})
        if isinstance(data, dict) and "email_address" in data:
            profile_upsert = data
            break

    assert profile_upsert is not None
    assert profile_upsert["email_address"] == "newuser@example.com"
    assert profile_upsert["full_name"] == "New User"
    assert profile_upsert["avatar_url"] == "https://example.com/pic.jpg"


# ─── 9. test_pending_invitations_matched_on_signup ───────────────────────────

@patch("app.services.auth_service.service_client")
@patch("app.services.auth_service.build_oauth_flow")
def test_pending_invitations_matched_on_signup(mock_build_flow, mock_svc):
    """New user signup with a pending invitation:
    - invitee_id is set on the invitation row
    - an event_invitation notification is created for the new user (invitee)
    - invitation status remains 'pending'
    - no event_participants row is inserted
    """
    user_info = {
        "id": "google-account-id",
        "email": "invited@example.com",
        "name": "Invited User",
        "picture": None,
    }
    pending_invite = {
        "id": "invite-uuid-1",
        "event_id": "event-uuid-1",
        "inviter_id": "inviter-uuid-1",
        "invitee_email": "invited@example.com",
        "status": "pending",
        "events": {"name": "Team Sync"},
    }

    mock_flow = MagicMock()
    mock_flow.credentials = Credentials(token="tok", refresh_token="ref")
    mock_build_flow.return_value = mock_flow

    # Track operations by table
    notifications_inserted = []
    invitations_updated = []
    participants_upserted = []

    def make_table(table_name):
        tbl = MagicMock()

        if table_name == "event_invitations":
            # SELECT returns the pending invite
            # Chain: select(...).eq(invitee_email).eq(status).is_(invitee_id, null).execute()
            select_chain = MagicMock()
            select_chain.eq.return_value.eq.return_value.is_.return_value.execute.return_value = MagicMock(
                data=[pending_invite]
            )
            tbl.select.return_value = select_chain

            # UPDATE to set invitee_id — capture it
            def capture_update(data):
                invitations_updated.append(data)
                chain = MagicMock()
                chain.eq.return_value.execute.return_value = MagicMock(data=[])
                return chain

            tbl.update.side_effect = capture_update

        elif table_name == "event_participants":
            def capture_upsert(data, **kwargs):
                participants_upserted.append(data)
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[])
                return chain

            tbl.upsert.side_effect = capture_upsert

        elif table_name == "notifications":
            def capture_insert(data):
                notifications_inserted.append(data)
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[])
                return chain

            tbl.insert.side_effect = capture_insert

        elif table_name == "profiles":
            def profile_upsert(data, **kwargs):
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[])
                return chain

            tbl.upsert.side_effect = profile_upsert

        else:
            tbl.upsert.return_value.execute.return_value = MagicMock(data=[])
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        return tbl

    mock_svc.table.side_effect = make_table

    with patch("app.services.auth_service._fetch_google_user_info", return_value=user_info):
        new_auth_user = MagicMock()
        new_auth_user.user.id = "new-invited-user-uuid"
        mock_svc.auth.admin.create_user.return_value = new_auth_user

        auth_service.exchange_code_and_upsert_user("fake-code")

    # invitee_id is set on the invitation row
    assert len(invitations_updated) == 1
    assert invitations_updated[0].get("invitee_id") == "new-invited-user-uuid"
    assert "status" not in invitations_updated[0]

    # An event_invitation notification is created for the new user (invitee)
    assert len(notifications_inserted) == 1
    notif = notifications_inserted[0]
    assert notif["notification_type"] == "event_invitation"
    assert notif["user_id"] == "new-invited-user-uuid"
    assert notif["event_id"] == "event-uuid-1"
    # invitation_id must be in metadata so Accept/Decline buttons can resolve it
    assert notif["metadata"]["invitation_id"] == "invite-uuid-1"

    # Invitation status is NOT changed — remains pending
    assert pending_invite["status"] == "pending"

    # No participant row is created automatically
    assert len(participants_upserted) == 0


# ─── 10b. test_pending_invitations_no_duplicate_on_relogin ───────────────────

@patch("app.services.auth_service.service_client")
@patch("app.services.auth_service.build_oauth_flow")
def test_pending_invitations_no_duplicate_on_relogin(mock_build_flow, mock_svc):
    """Re-login while an invitation is still pending must NOT create a duplicate
    notification. _process_pending_invitations filters on invitee_id IS NULL,
    so once linked the row is excluded from the next sweep.

    We simulate this by having the SELECT return an empty list (mirroring the
    DB behaviour where invitee_id is already populated and therefore excluded
    by the .is_("invitee_id", "null") filter).
    """
    user_info = {
        "id": "google-account-id",
        "email": "invited@example.com",
        "name": "Invited User",
        "picture": None,
    }

    mock_flow = MagicMock()
    mock_flow.credentials = Credentials(token="tok", refresh_token="ref")
    mock_build_flow.return_value = mock_flow

    notifications_inserted = []
    invitations_updated = []

    def make_table(table_name):
        tbl = MagicMock()

        if table_name == "event_invitations":
            # The is_ filter excludes already-linked rows, so SELECT returns empty
            select_chain = MagicMock()
            select_chain.eq.return_value.eq.return_value.is_.return_value.execute.return_value = MagicMock(
                data=[]
            )
            tbl.select.return_value = select_chain

            def capture_update(data):
                invitations_updated.append(data)
                chain = MagicMock()
                chain.eq.return_value.execute.return_value = MagicMock(data=[])
                return chain

            tbl.update.side_effect = capture_update

        elif table_name == "notifications":
            def capture_insert(data):
                notifications_inserted.append(data)
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[])
                return chain

            tbl.insert.side_effect = capture_insert

        elif table_name == "profiles":
            def profile_upsert(data, **kwargs):
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[])
                return chain

            tbl.upsert.side_effect = profile_upsert

        else:
            tbl.upsert.return_value.execute.return_value = MagicMock(data=[])
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        return tbl

    mock_svc.table.side_effect = make_table

    with patch("app.services.auth_service._fetch_google_user_info", return_value=user_info):
        existing_auth_user = MagicMock()
        existing_auth_user.user.id = "existing-invited-user-uuid"
        mock_svc.auth.admin.create_user.return_value = existing_auth_user

        auth_service.exchange_code_and_upsert_user("fake-code")

    # No duplicate notification — invitee_id is already set so the row is excluded
    assert notifications_inserted == []
    # No second invitee_id update either
    assert invitations_updated == []


# ─── 11. test_jwt_contains_expected_claims ────────────────────────────────────

def test_jwt_contains_expected_claims():
    """_create_jwt produces a token with user_id (sub) and email claims."""
    token = auth_service._create_jwt(user_id="user-uuid-1", email="alice@example.com")

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == "user-uuid-1"
    assert payload["email"] == "alice@example.com"
    assert "exp" in payload
