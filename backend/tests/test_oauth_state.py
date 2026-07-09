"""Signed OAuth ``state`` tests — the C1 fix (cross-user calendar linking).

Covers the HMAC state helper (app.utils.oauth_state) and the calendar-connect
endpoints: the connect-URL must issue a signed state embedding the current
user, and BOTH callbacks (Google + Microsoft) must reject forged/expired/raw
states before any token exchange or DB work. Providers and Supabase are mocked;
no network calls are made.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.main import app
from app.providers.base import ConnectedIdentity
from app.utils.oauth_state import (
    DEFAULT_MAX_AGE_SECONDS,
    OAuthStateError,
    create_oauth_state,
    verify_oauth_state,
)

client = TestClient(app, follow_redirects=False)

GOOGLE_CALLBACK = "/api/calendar-accounts/callback"
MICROSOFT_CALLBACK = "/api/calendar-accounts/callback/microsoft"
CALLBACKS = [GOOGLE_CALLBACK, MICROSOFT_CALLBACK]


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


def _identity() -> ConnectedIdentity:
    return ConnectedIdentity(
        credentials={"access_token": "at", "refresh_token": "rt"},
        provider_email="alice@gmail.com",
        provider_account_id="prov-id-1",
    )


def _tamper_signature(token: str) -> str:
    """Flip the last character of the signature segment."""
    head, sig = token.rsplit(".", 1)
    flipped = "A" if sig[-1] != "A" else "B"
    return f"{head}.{sig[:-1]}{flipped}"


def _expired_state(user_id: str = "user-uuid-1") -> str:
    """A correctly signed state issued beyond the TTL."""
    past = time.time() - (DEFAULT_MAX_AGE_SECONDS + 60)
    with patch("app.utils.oauth_state.time.time", return_value=past):
        return create_oauth_state(user_id)


def _assert_error_redirect(response, error_code: str = "calendar_auth_failed"):
    assert response.status_code in (302, 307)
    assert response.headers["location"] == f"{settings.frontend_url}/settings?error={error_code}"


# ─── State helper unit tests ─────────────────────────────────────────────────

def test_state_roundtrip_returns_user_id():
    token = create_oauth_state("user-uuid-1")
    assert verify_oauth_state(token) == "user-uuid-1"


def test_state_tokens_are_unique_per_issue():
    # Random nonce (and timestamp) → two states for the same user never collide.
    assert create_oauth_state("user-uuid-1") != create_oauth_state("user-uuid-1")


def test_state_tampered_signature_rejected():
    token = _tamper_signature(create_oauth_state("user-uuid-1"))
    with pytest.raises(OAuthStateError):
        verify_oauth_state(token)


def test_state_swapped_payload_rejected():
    """Splicing the attacker's valid signature onto a victim's user_id fails."""
    victim_token = create_oauth_state("victim-uuid")
    attacker_token = create_oauth_state("attacker-uuid")
    victim_payload = victim_token.rsplit(".", 1)[0]
    attacker_sig = attacker_token.rsplit(".", 1)[1]
    with pytest.raises(OAuthStateError):
        verify_oauth_state(f"{victim_payload}.{attacker_sig}")


def test_state_expired_rejected():
    with pytest.raises(OAuthStateError):
        verify_oauth_state(_expired_state())


def test_state_just_inside_ttl_accepted():
    recent = time.time() - (DEFAULT_MAX_AGE_SECONDS - 60)
    with patch("app.utils.oauth_state.time.time", return_value=recent):
        token = create_oauth_state("user-uuid-1")
    assert verify_oauth_state(token) == "user-uuid-1"


def test_state_issued_far_in_future_rejected():
    future = time.time() + 3600
    with patch("app.utils.oauth_state.time.time", return_value=future):
        token = create_oauth_state("user-uuid-1")
    with pytest.raises(OAuthStateError):
        verify_oauth_state(token)


def test_state_raw_uuid_rejected():
    """The old format — a bare user id — must never verify."""
    with pytest.raises(OAuthStateError):
        verify_oauth_state("2c6e10f2-6c3f-4a1e-9d7b-0a8f5b8b4a11")


@pytest.mark.parametrize("bad", ["", None, "v1", "v1.a.b.c", "v9.a.1.b.c", "a.b.c.d.e.f"])
def test_state_malformed_rejected(bad):
    with pytest.raises(OAuthStateError):
        verify_oauth_state(bad)


# ─── connect-url issues a signed state ───────────────────────────────────────

@patch("app.routers.calendar_accounts.get_provider")
@patch("app.dependencies.service_client")
def test_connect_url_state_verifies_and_embeds_user(mock_dep_svc, mock_get_provider):
    """GET /connect-url → provider receives a signed state that verifies back to
    the authenticated user's id (never the raw id)."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    prov = MagicMock()
    prov.get_authorization_url.return_value = "https://accounts.google.com/o/oauth2/auth?..."
    mock_get_provider.return_value = prov

    response = client.get("/api/calendar-accounts/connect-url", headers=_auth_headers())

    assert response.status_code == 200
    state = prov.get_authorization_url.call_args.kwargs["state"]
    assert state != "user-uuid-1"  # raw id must not be used
    assert verify_oauth_state(state) == "user-uuid-1"


# ─── Callbacks: valid state links the account ────────────────────────────────

@pytest.mark.parametrize(
    "path,provider_name", [(GOOGLE_CALLBACK, "google"), (MICROSOFT_CALLBACK, "microsoft")]
)
@patch("app.routers.calendar_accounts.sync_service")
@patch("app.routers.calendar_accounts.calendar_service")
@patch("app.routers.calendar_accounts.get_provider")
def test_callback_valid_state_links_account(
    mock_get_provider, mock_cal_service, mock_sync_service, path, provider_name
):
    prov = MagicMock()
    prov.exchange_code.return_value = _identity()
    mock_get_provider.return_value = prov

    state = create_oauth_state("user-uuid-1")
    response = client.get(path, params={"code": "auth-code", "state": state})

    assert response.status_code in (302, 307)
    assert response.headers["location"] == f"{settings.frontend_url}/settings?connected=true"
    mock_get_provider.assert_called_once_with(provider_name)
    prov.exchange_code.assert_called_once_with("auth-code", state)
    mock_cal_service.connect_account.assert_called_once_with(
        user_id="user-uuid-1", provider_name=provider_name, identity=prov.exchange_code.return_value
    )
    mock_sync_service.sync_busy_slots.assert_called_once_with("user-uuid-1")


# ─── Callbacks: tampered signature rejected before any work ──────────────────

@pytest.mark.parametrize("path", CALLBACKS)
@patch("app.routers.calendar_accounts.calendar_service")
@patch("app.routers.calendar_accounts.get_provider")
def test_callback_tampered_state_rejected(mock_get_provider, mock_cal_service, path):
    state = _tamper_signature(create_oauth_state("victim-uuid"))
    response = client.get(path, params={"code": "auth-code", "state": state})

    _assert_error_redirect(response)
    # Rejected BEFORE any token exchange or DB write.
    mock_get_provider.assert_not_called()
    mock_cal_service.connect_account.assert_not_called()


# ─── Callbacks: expired state rejected ───────────────────────────────────────

@pytest.mark.parametrize("path", CALLBACKS)
@patch("app.routers.calendar_accounts.calendar_service")
@patch("app.routers.calendar_accounts.get_provider")
def test_callback_expired_state_rejected(mock_get_provider, mock_cal_service, path):
    response = client.get(path, params={"code": "auth-code", "state": _expired_state()})

    _assert_error_redirect(response)
    mock_get_provider.assert_not_called()
    mock_cal_service.connect_account.assert_not_called()


# ─── Callbacks: raw-UUID state (old format) rejected ─────────────────────────

@pytest.mark.parametrize("path", CALLBACKS)
@patch("app.routers.calendar_accounts.calendar_service")
@patch("app.routers.calendar_accounts.get_provider")
def test_callback_raw_uuid_state_rejected(mock_get_provider, mock_cal_service, path):
    response = client.get(
        path, params={"code": "auth-code", "state": "2c6e10f2-6c3f-4a1e-9d7b-0a8f5b8b4a11"}
    )

    _assert_error_redirect(response)
    mock_get_provider.assert_not_called()
    mock_cal_service.connect_account.assert_not_called()


# ─── Callbacks: missing state / provider error rejected ─────────────────────

@pytest.mark.parametrize("path", CALLBACKS)
@patch("app.routers.calendar_accounts.calendar_service")
@patch("app.routers.calendar_accounts.get_provider")
def test_callback_missing_state_rejected(mock_get_provider, mock_cal_service, path):
    response = client.get(path, params={"code": "auth-code"})

    _assert_error_redirect(response)
    mock_get_provider.assert_not_called()
    mock_cal_service.connect_account.assert_not_called()


@pytest.mark.parametrize("path", CALLBACKS)
@patch("app.routers.calendar_accounts.calendar_service")
@patch("app.routers.calendar_accounts.get_provider")
def test_callback_provider_error_param_rejected(mock_get_provider, mock_cal_service, path):
    """Provider-side denial (?error=access_denied) short-circuits to the error
    redirect without touching the provider or DB."""
    response = client.get(
        path,
        params={"error": "access_denied", "state": create_oauth_state("user-uuid-1")},
    )

    _assert_error_redirect(response)
    mock_get_provider.assert_not_called()
    mock_cal_service.connect_account.assert_not_called()
