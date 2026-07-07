"""Sprint 1 — Auth tests.

Tests the auth router, auth service, and get_current_user dependency with mocked
Supabase clients and mocked Google OAuth flow.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call
from urllib.parse import parse_qs, urlparse
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
from app.utils.login_code import (
    DEFAULT_MAX_AGE_SECONDS as LOGIN_CODE_MAX_AGE,
    create_login_code,
)


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

    # Login must NOT request the incremental-auth scope union: with
    # include_granted_scopes=false Google echoes exactly the requested scopes,
    # which is what lets the exchange keep oauthlib's scope validation enabled.
    query = parse_qs(urlparse(location).query)
    assert query["include_granted_scopes"] == ["false"]


def test_auth_google_redirect_binds_state_to_cookie():
    """Login-start sets an HttpOnly state cookie whose value matches the ``state``
    carried in the Google consent URL — the browser-session binding that defeats
    login CSRF."""
    response = client.get("/auth/google")

    # State from the Google URL
    query = parse_qs(urlparse(response.headers["location"]).query)
    url_state = query["state"][0]
    assert url_state and url_state != "stateless"

    # State pinned to the browser via cookie
    set_cookie = response.headers["set-cookie"]
    assert "oauth_login_state=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()
    assert "path=/auth/google/callback" in set_cookie.lower()
    assert response.cookies["oauth_login_state"] == url_state


# ─── 1b. Login callback CSRF / state-binding ──────────────────────────────────

# Fresh clients per test so the module-level cookie jar (populated by the
# login-start tests) can't leak an oauth_login_state cookie into these.

@patch("app.services.auth_service.exchange_code_and_upsert_user", return_value="fake-login-code")
def test_login_callback_valid_state_proceeds(mock_exchange):
    """Matching cookie + query state → code is exchanged and the browser is
    redirected to the frontend with a short-lived login code — NEVER the session
    JWT (?token= would leak a 7-day credential into history/Referer/logs);
    the state cookie is cleared."""
    c = TestClient(app, follow_redirects=False, cookies={"oauth_login_state": "match-123"})
    response = c.get("/auth/google/callback?code=auth-code&state=match-123")

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "/auth/callback?code=fake-login-code" in location
    assert "token=" not in location
    mock_exchange.assert_called_once_with("auth-code", "match-123")

    # Cookie is single-use — cleared on success
    set_cookie = response.headers["set-cookie"]
    assert "oauth_login_state=" in set_cookie
    assert "max-age=0" in set_cookie.lower()


@patch("app.services.auth_service.exchange_code_and_upsert_user")
def test_login_callback_missing_cookie_rejected(mock_exchange):
    """State query param present but no cookie (attacker's own flow in victim's
    browser) → rejected, code never exchanged."""
    c = TestClient(app, follow_redirects=False)
    response = c.get("/auth/google/callback?code=auth-code&state=whatever")

    assert response.status_code in (302, 307)
    assert "error=auth_failed" in response.headers["location"]
    mock_exchange.assert_not_called()


@patch("app.services.auth_service.exchange_code_and_upsert_user")
def test_login_callback_missing_param_rejected(mock_exchange):
    """Cookie present but no state query param → rejected, code never exchanged."""
    c = TestClient(app, follow_redirects=False, cookies={"oauth_login_state": "cookie-value"})
    response = c.get("/auth/google/callback?code=auth-code")

    assert response.status_code in (302, 307)
    assert "error=auth_failed" in response.headers["location"]
    mock_exchange.assert_not_called()


@patch("app.services.auth_service.exchange_code_and_upsert_user")
def test_login_callback_state_mismatch_rejected(mock_exchange):
    """Cookie and query state differ → rejected, code never exchanged."""
    c = TestClient(app, follow_redirects=False, cookies={"oauth_login_state": "victim-state"})
    response = c.get("/auth/google/callback?code=auth-code&state=attacker-state")

    assert response.status_code in (302, 307)
    assert "error=auth_failed" in response.headers["location"]
    mock_exchange.assert_not_called()


# ─── 1c. Exchange keeps oauthlib scope validation ─────────────────────────────

@patch("app.services.auth_service.service_client")
@patch("app.services.auth_service.build_oauth_flow")
def test_exchange_keeps_scope_validation(mock_build_flow, mock_svc):
    """The exchange must NOT disable oauthlib's scope check (the old
    ``flow.oauth2session.scope = None``) and must thread ``state`` through the
    flow builder rather than a private attribute. Genuine scope validation is
    safe because the login URL requests include_granted_scopes=false, so Google
    echoes exactly the requested scopes."""
    mock_flow = MagicMock()
    mock_flow.credentials = Credentials(token="tok", refresh_token="ref")
    mock_build_flow.return_value = mock_flow

    user_info = {
        "id": "google-account-id",
        "email": "scope@example.com",
        "name": "Scope User",
        "picture": None,
    }
    with patch("app.services.auth_service._fetch_google_user_info", return_value=user_info):
        auth_user = MagicMock()
        auth_user.user.id = "scope-user-uuid"
        mock_svc.auth.admin.create_user.return_value = auth_user

        auth_service.exchange_code_and_upsert_user("fake-code", "csrf-state")

    # State goes through the builder (oauthlib's own API), not flow._state
    mock_build_flow.assert_called_once_with(state="csrf-state")
    # Scope checking stays enabled — the session scope is never nulled out
    assert mock_flow.oauth2session.scope is not None


# ─── 1d. Session exchange / realtime token / logout (M4+M5) ───────────────────

@patch("app.services.auth_service.service_client")
def test_session_exchange_sets_cookie_and_returns_user(mock_svc):
    """Valid login code → HttpOnly `session` cookie carrying the JWT is set and
    the body carries the User payload only (no token field)."""
    profile = _make_profile_row()
    mock_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

    code = create_login_code("user-uuid-1")
    c = TestClient(app)
    response = c.post("/auth/session/exchange", json={"code": code})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "user-uuid-1"
    assert data["email_address"] == "alice@example.com"
    # The JWT travels ONLY in the cookie — never the response body
    assert "token" not in data

    set_cookie = response.headers["set-cookie"]
    assert "session=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()
    assert "path=/" in set_cookie.lower()

    # The cookie really is the session JWT for the right user
    payload = jwt.decode(
        response.cookies["session"],
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert payload["sub"] == "user-uuid-1"
    assert payload["email"] == "alice@example.com"


@patch("app.services.auth_service.service_client")
def test_session_exchange_tampered_code_rejected(mock_svc):
    """A signature-tampered login code → 401, no cookie, no DB work."""
    code = create_login_code("user-uuid-1")
    tampered = code[:-1] + ("A" if code[-1] != "A" else "B")

    c = TestClient(app)
    response = c.post("/auth/session/exchange", json={"code": tampered})

    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    mock_svc.table.assert_not_called()


@patch("app.services.auth_service.service_client")
def test_session_exchange_garbage_code_rejected(mock_svc):
    """A malformed code → 401, no cookie, no DB work."""
    c = TestClient(app)
    response = c.post("/auth/session/exchange", json={"code": "not-a-real-code"})

    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    mock_svc.table.assert_not_called()


@patch("app.services.auth_service.service_client")
def test_session_exchange_expired_code_rejected(mock_svc):
    """A login code past its 60s TTL → 401, no cookie, no DB work."""
    code = create_login_code("user-uuid-1")

    c = TestClient(app)
    with patch(
        "app.utils.login_code.time.time",
        return_value=time.time() + LOGIN_CODE_MAX_AGE + 5,
    ):
        response = c.post("/auth/session/exchange", json={"code": code})

    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    mock_svc.table.assert_not_called()


@patch("app.dependencies.service_client")
def test_realtime_token_is_short_lived(mock_svc):
    """A session-cookie-authenticated request gets a ~1h JWT for supabase
    realtime, with its lifetime in the body so the client can cache it."""
    profile = _make_profile_row()
    mock_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

    c = TestClient(app, cookies={"session": _make_valid_jwt()})
    response = c.get("/auth/realtime-token")

    assert response.status_code == 200
    data = response.json()
    assert data["expires_in"] == 3600

    payload = jwt.decode(
        data["token"], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    assert payload["sub"] == "user-uuid-1"
    assert payload["email"] == "alice@example.com"
    remaining = payload["exp"] - datetime.now(timezone.utc).timestamp()
    # ~1 hour, definitely not the 7-day session lifetime
    assert 3300 < remaining <= 3660


def test_realtime_token_requires_auth():
    """No header and no session cookie → rejected (403, matching the repo's
    missing-credentials convention), no token minted."""
    c = TestClient(app)
    response = c.get("/auth/realtime-token")
    assert response.status_code == 403


def test_logout_clears_session_cookie():
    """POST /auth/logout expires the session cookie."""
    c = TestClient(app, cookies={"session": _make_valid_jwt()})
    response = c.post("/auth/logout")

    assert response.status_code == 204
    set_cookie = response.headers["set-cookie"]
    assert "session=" in set_cookie
    assert "max-age=0" in set_cookie.lower()


@patch("app.dependencies.service_client")
def test_get_current_user_accepts_session_cookie(mock_svc):
    """get_current_user resolves the user from the HttpOnly session cookie
    (the browser path — no Authorization header)."""
    profile = _make_profile_row()
    mock_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

    with patch("app.services.auth_service.service_client") as mock_auth_svc:
        mock_auth_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)
        c = TestClient(app, cookies={"session": _make_valid_jwt()})
        response = c.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["id"] == "user-uuid-1"


@patch("app.dependencies.service_client")
def test_get_current_user_header_takes_precedence_over_cookie(mock_svc):
    """When both are present the Authorization header wins: a valid header with
    a garbage cookie must still authenticate."""
    profile = _make_profile_row()
    mock_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)

    with patch("app.services.auth_service.service_client") as mock_auth_svc:
        mock_auth_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)
        c = TestClient(app, cookies={"session": "garbage-not-a-jwt"})
        response = c.get(
            "/auth/me", headers={"Authorization": f"Bearer {_make_valid_jwt()}"}
        )

    assert response.status_code == 200
    assert response.json()["id"] == "user-uuid-1"


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
    # The internal per-request JWT field must never be serialized
    assert "token" not in data


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

        auth_service.exchange_code_and_upsert_user("fake-code", "test-state")

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


# ─── 8b. Returning-user resolution via profiles lookup (H7) ──────────────────
#
# When auth.admin.create_user raises (user already exists), the auth user id
# must be resolved with a single profiles-table query — NEVER by paging
# auth.admin.list_users, whose old first-page-then-page-2 scan skipped users
# at indices ~51–1000 and broke returning logins at scale.

def _profiles_lookup_client(rows: list[dict]) -> MagicMock:
    """Mock service_client: create_user raises 'already exists'; the profiles
    email lookup returns ``rows``; the profiles upsert is a no-op."""
    mock_svc = MagicMock()
    mock_svc.auth.admin.create_user.side_effect = Exception("User already registered")

    profiles_tbl = MagicMock()
    profiles_tbl.select.return_value.in_.return_value.execute.return_value = MagicMock(data=rows)
    profiles_tbl.upsert.return_value.execute.return_value = MagicMock(data=[])
    mock_svc.table.return_value = profiles_tbl
    return mock_svc


def test_returning_user_resolved_via_profiles_lookup():
    """Returning login: id comes from the profiles email lookup; list_users is
    never called (there is no page for a user to be lost on)."""
    existing_row = {"id": "existing-user-uuid", "email_address": "alice@example.com"}
    mock_svc = _profiles_lookup_client([existing_row])

    user_info = {"email": "alice@example.com", "name": "Alice", "picture": None}
    with patch("app.services.auth_service.service_client", mock_svc):
        profile = auth_service._upsert_profile(user_info, MagicMock())

    assert profile["id"] == "existing-user-uuid"
    mock_svc.auth.admin.list_users.assert_not_called()

    # The upsert is keyed to the resolved auth user id
    upsert_data = mock_svc.table.return_value.upsert.call_args.args[0]
    assert upsert_data["id"] == "existing-user-uuid"
    assert upsert_data["email_address"] == "alice@example.com"


def test_returning_user_gmail_dots_resolved_via_normalized_email():
    """Gmail dot-variant: the profile row stores the normalized form
    (johndoe@) while Google sends the raw form (john.doe@). The lookup must
    query both forms and match the normalized row."""
    existing_row = {"id": "gmail-user-uuid", "email_address": "johndoe@gmail.com"}
    mock_svc = _profiles_lookup_client([existing_row])

    user_info = {"email": "john.doe@gmail.com", "name": "John", "picture": None}
    with patch("app.services.auth_service.service_client", mock_svc):
        profile = auth_service._upsert_profile(user_info, MagicMock())

    assert profile["id"] == "gmail-user-uuid"

    # Both email forms were included in the candidates filter
    in_args = mock_svc.table.return_value.select.return_value.in_.call_args
    assert in_args.args[0] == "email_address"
    assert set(in_args.args[1]) == {"johndoe@gmail.com", "john.doe@gmail.com"}


def test_returning_user_raw_trigger_email_still_resolves():
    """Crash-window case: the on_auth_user_created trigger wrote the raw email
    and no completed login normalized it yet — the raw-form row must still
    resolve."""
    existing_row = {"id": "raw-email-uuid", "email_address": "john.doe@gmail.com"}
    mock_svc = _profiles_lookup_client([existing_row])

    user_info = {"email": "john.doe@gmail.com", "name": "John", "picture": None}
    with patch("app.services.auth_service.service_client", mock_svc):
        profile = auth_service._upsert_profile(user_info, MagicMock())

    assert profile["id"] == "raw-email-uuid"


def test_returning_user_unresolvable_raises_500():
    """create_user raises and no profile row matches either email form → 500."""
    mock_svc = _profiles_lookup_client([])

    user_info = {"email": "ghost@example.com", "name": "Ghost", "picture": None}
    with patch("app.services.auth_service.service_client", mock_svc):
        with pytest.raises(HTTPException) as exc_info:
            auth_service._upsert_profile(user_info, MagicMock())

    assert exc_info.value.status_code == 500


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

        auth_service.exchange_code_and_upsert_user("fake-code", "test-state")

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

        auth_service.exchange_code_and_upsert_user("fake-code", "test-state")

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
