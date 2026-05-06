"""Sprint 4 — Calendar account + source tests.

Tests the calendar_accounts and calendar_sources routers with mocked Supabase/Google.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
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


def _current_user_profile(user_id: str = "user-uuid-1") -> dict:
    return {"id": user_id, "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}


def _make_account_row(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    defaults = {
        "id": "account-uuid-1",
        "user_id": "user-uuid-1",
        "provider": "google",
        "provider_email": "alice@gmail.com",
        "provider_account_id": "google-id-1",
        "connected_at": now,
        "last_synced_at": None,
    }
    return {**defaults, **overrides}


def _make_source_row(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    defaults = {
        "id": "source-uuid-1",
        "account_id": "account-uuid-1",
        "calendar_id": "alice@gmail.com",
        "calendar_name": "Primary",
        "is_enabled": True,
        "is_write_calendar": True,
        "color": "#9b4428",
        "created_at": now,
        "updated_at": now,
    }
    return {**defaults, **overrides}


# ─── 1. test_list_accounts_success ───────────────────────────────────────────

@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_list_accounts_success(mock_dep_svc, mock_cal_svc):
    """GET /api/calendar-accounts → 200 with list of accounts."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    account = _make_account_row()
    source = _make_source_row()
    account_with_sources = {**account, "calendar_sources": [source]}

    mock_cal_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[account_with_sources]
    )

    response = client.get("/api/calendar-accounts", headers=_auth_headers())

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["id"] == "account-uuid-1"
    assert data[0]["provider"] == "google"
    assert len(data[0]["sources"]) == 1


# ─── 2. test_list_accounts_empty ─────────────────────────────────────────────

@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_list_accounts_empty(mock_dep_svc, mock_cal_svc):
    """GET /api/calendar-accounts → 200 with empty list when no accounts."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    mock_cal_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    response = client.get("/api/calendar-accounts", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == []


# ─── 3. test_list_accounts_requires_auth ─────────────────────────────────────

def test_list_accounts_requires_auth():
    """GET /api/calendar-accounts without token → 403."""
    response = client.get("/api/calendar-accounts")
    assert response.status_code == 403


# ─── 4. test_disconnect_account_success ──────────────────────────────────────

@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_disconnect_account_success(mock_dep_svc, mock_cal_svc):
    """DELETE /api/calendar-accounts/{id} → 204 when account belongs to user."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    # Ownership check returns data
    mock_cal_svc.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_make_account_row()]
    )
    mock_cal_svc.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    response = client.delete("/api/calendar-accounts/account-uuid-1", headers=_auth_headers())

    assert response.status_code == 204


# ─── 5. test_disconnect_account_forbidden ────────────────────────────────────

@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_disconnect_account_forbidden(mock_dep_svc, mock_cal_svc):
    """DELETE /api/calendar-accounts/{id} → 403 when account belongs to another user."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    # Ownership check returns no data (different user)
    mock_cal_svc.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )

    response = client.delete("/api/calendar-accounts/account-uuid-1", headers=_auth_headers())

    assert response.status_code == 403


# ─── 5b. Token revocation on disconnect (Phase 2) ────────────────────────────

def _make_response(status_code: int, text: str = "") -> MagicMock:
    """Construct a fake httpx.Response with the given status and body text."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


@patch("app.utils.google_auth.httpx.post")
@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_disconnect_revokes_token_then_deletes_row(mock_dep_svc, mock_cal_svc, mock_httpx):
    """200 OK from Google revoke → DB row is deleted, response is 204."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    account = {**_make_account_row(), "credentials": {"refresh_token": "rt-123"}}
    mock_cal_svc.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[account])
    mock_cal_svc.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_httpx.return_value = _make_response(200)

    response = client.delete("/api/calendar-accounts/account-uuid-1", headers=_auth_headers())

    assert response.status_code == 204
    mock_httpx.assert_called_once()
    args, kwargs = mock_httpx.call_args
    assert args[0] == "https://oauth2.googleapis.com/revoke"
    assert kwargs["params"] == {"token": "rt-123"}
    mock_cal_svc.table.return_value.delete.return_value.eq.assert_called_with("id", "account-uuid-1")


@patch("app.utils.google_auth.httpx.post")
@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_disconnect_treats_invalid_token_as_revoked(mock_dep_svc, mock_cal_svc, mock_httpx):
    """400 invalid_token → already-dead at Google, safe to delete the DB row."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    account = {**_make_account_row(), "credentials": {"refresh_token": "rt-stale"}}
    mock_cal_svc.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[account])
    mock_cal_svc.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_httpx.return_value = _make_response(400, '{"error":"invalid_token"}')

    response = client.delete("/api/calendar-accounts/account-uuid-1", headers=_auth_headers())

    assert response.status_code == 204
    assert mock_cal_svc.table.return_value.delete.called


@patch("app.utils.google_auth.httpx.post")
@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_disconnect_aborts_on_revoke_500(mock_dep_svc, mock_cal_svc, mock_httpx):
    """5xx from Google → unknown state → keep the row, return 502."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    account = {**_make_account_row(), "credentials": {"refresh_token": "rt-live"}}
    mock_cal_svc.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[account])
    mock_httpx.return_value = _make_response(500, "Internal Server Error")

    response = client.delete("/api/calendar-accounts/account-uuid-1", headers=_auth_headers())

    assert response.status_code == 502
    assert not mock_cal_svc.table.return_value.delete.called


@patch("app.utils.google_auth.httpx.post")
@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_disconnect_aborts_on_revoke_network_error(mock_dep_svc, mock_cal_svc, mock_httpx):
    """Network error contacting Google → keep the row, return 502."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    account = {**_make_account_row(), "credentials": {"refresh_token": "rt-live"}}
    mock_cal_svc.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[account])
    mock_httpx.side_effect = httpx.ConnectError("DNS failure")

    response = client.delete("/api/calendar-accounts/account-uuid-1", headers=_auth_headers())

    assert response.status_code == 502
    assert not mock_cal_svc.table.return_value.delete.called


@patch("app.utils.google_auth.httpx.post")
@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_disconnect_skips_revoke_when_no_refresh_token(mock_dep_svc, mock_cal_svc, mock_httpx):
    """No refresh_token stored → no revoke call, DB row still deleted."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    account = {**_make_account_row(), "credentials": {}}
    mock_cal_svc.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[account])
    mock_cal_svc.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    response = client.delete("/api/calendar-accounts/account-uuid-1", headers=_auth_headers())

    assert response.status_code == 204
    mock_httpx.assert_not_called()
    assert mock_cal_svc.table.return_value.delete.called


# ─── 6. test_update_source_toggle_enabled ────────────────────────────────────

@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_update_source_toggle_enabled(mock_dep_svc, mock_cal_svc):
    """PATCH /api/calendar-sources/{id} → 200, toggles is_enabled."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    source = _make_source_row()
    source_with_account = {**source, "calendar_accounts": {"user_id": "user-uuid-1"}}
    mock_cal_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[source_with_account]
    )

    updated = {**source, "is_enabled": False}
    mock_cal_svc.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[updated]
    )

    response = client.patch(
        "/api/calendar-sources/source-uuid-1",
        json={"is_enabled": False},
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert response.json()["is_enabled"] is False


# ─── 7. test_update_source_forbidden ─────────────────────────────────────────

@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_update_source_forbidden(mock_dep_svc, mock_cal_svc):
    """PATCH /api/calendar-sources/{id} → 403 when source belongs to another user."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    source = _make_source_row()
    source_with_other_account = {**source, "calendar_accounts": {"user_id": "other-user"}}
    mock_cal_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[source_with_other_account]
    )

    response = client.patch(
        "/api/calendar-sources/source-uuid-1",
        json={"is_enabled": False},
        headers=_auth_headers(),
    )

    assert response.status_code == 403


# ─── 8. test_update_source_not_found ─────────────────────────────────────────

@patch("app.services.calendar_service.service_client")
@patch("app.dependencies.service_client")
def test_update_source_not_found(mock_dep_svc, mock_cal_svc):
    """PATCH /api/calendar-sources/{id} → 404 when source does not exist."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    mock_cal_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    response = client.patch(
        "/api/calendar-sources/nonexistent",
        json={"is_enabled": True},
        headers=_auth_headers(),
    )

    assert response.status_code == 404
