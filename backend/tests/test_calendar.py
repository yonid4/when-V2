"""Sprint 4 — Calendar account + source tests.

Tests the calendar_accounts and calendar_sources routers with mocked Supabase/Google.
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
