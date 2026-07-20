"""Phase 3 — Account deletion endpoint tests (mocked)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.main import app

client = TestClient(app)


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


def _make_response(status_code: int, text: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


@patch("app.utils.google_auth.httpx.post")
@patch("app.services.account_service.service_client")
@patch("app.dependencies.service_client")
def test_delete_account_revokes_all_calendar_tokens(
    mock_dep_svc, mock_account_svc, mock_httpx
):
    """All connected calendar accounts have their refresh tokens revoked."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    # User has 2 connected calendars
    mock_account_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {"credentials": {"refresh_token": "rt-A"}},
            {"credentials": {"refresh_token": "rt-B"}},
        ]
    )
    mock_account_svc.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_httpx.return_value = _make_response(200)

    response = client.delete("/api/account", headers=_auth_headers())

    assert response.status_code == 204
    assert mock_httpx.call_count == 2
    revoked_tokens = {call.kwargs["params"]["token"] for call in mock_httpx.call_args_list}
    assert revoked_tokens == {"rt-A", "rt-B"}


@patch("app.utils.google_auth.httpx.post")
@patch("app.services.account_service.service_client")
@patch("app.dependencies.service_client")
def test_delete_account_deletes_planning_events(
    mock_dep_svc, mock_account_svc, mock_httpx
):
    """A DELETE is issued against events where coordinator_id=me AND status='planning'."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    mock_account_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_account_svc.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_httpx.return_value = _make_response(200)

    response = client.delete("/api/account", headers=_auth_headers())

    assert response.status_code == 204
    # Verify the .eq("coordinator_id", me).eq("status", "planning") chain was issued
    delete_chain = mock_account_svc.table.return_value.delete.return_value
    delete_chain.eq.assert_any_call("coordinator_id", "user-uuid-1")
    delete_chain.eq.return_value.eq.assert_any_call("status", "planning")


@patch("app.utils.google_auth.httpx.post")
@patch("app.services.account_service.service_client")
@patch("app.dependencies.service_client")
def test_delete_account_calls_auth_admin_delete_user(
    mock_dep_svc, mock_account_svc, mock_httpx
):
    """auth.admin.delete_user is called as the final step."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    mock_account_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_account_svc.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_httpx.return_value = _make_response(200)

    response = client.delete("/api/account", headers=_auth_headers())

    assert response.status_code == 204
    mock_account_svc.auth.admin.delete_user.assert_called_once_with("user-uuid-1")


@patch("app.utils.google_auth.httpx.post")
@patch("app.services.account_service.service_client")
@patch("app.dependencies.service_client")
def test_delete_account_aborts_on_revoke_failure(
    mock_dep_svc, mock_account_svc, mock_httpx
):
    """If revoking any token fails (5xx), nothing is deleted and route returns 502."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    mock_account_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {"credentials": {"refresh_token": "rt-OK"}},
            {"credentials": {"refresh_token": "rt-BAD"}},
        ]
    )
    # First call succeeds, second 5xx
    mock_httpx.side_effect = [_make_response(200), _make_response(500, "boom")]

    response = client.delete("/api/account", headers=_auth_headers())

    assert response.status_code == 502
    assert not mock_account_svc.table.return_value.delete.called
    assert not mock_account_svc.auth.admin.delete_user.called


def test_delete_account_returns_401_unauthenticated():
    """No Bearer token → 403 (matches existing pattern in test_calendar.py)."""
    response = client.delete("/api/account")
    assert response.status_code == 403  # FastAPI HTTPBearer rejects with 403, not 401


# ─── PATCH /api/account — timezone update ────────────────────────────────────

@patch("app.services.auth_service.service_client")
@patch("app.dependencies.service_client")
def test_patch_account_updates_timezone(mock_dep_svc, mock_auth_svc):
    """A valid IANA timezone is persisted to profiles and the updated user
    (without token) is returned."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    updated_profile = {**_current_user_profile(), "timezone": "Asia/Jerusalem"}
    mock_auth_svc.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[updated_profile]
    )

    response = client.patch(
        "/api/account", json={"timezone": "Asia/Jerusalem"}, headers=_auth_headers()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "Asia/Jerusalem"
    assert "token" not in body

    update_payload = mock_auth_svc.table.return_value.update.call_args[0][0]
    assert update_payload["timezone"] == "Asia/Jerusalem"
    mock_auth_svc.table.return_value.update.return_value.eq.assert_called_once_with(
        "id", "user-uuid-1"
    )


@patch("app.services.auth_service.service_client")
@patch("app.dependencies.service_client")
def test_patch_account_rejects_invalid_timezone(mock_dep_svc, mock_auth_svc):
    """An unknown IANA name is rejected with 422 and nothing is written."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    response = client.patch(
        "/api/account", json={"timezone": "Not/AZone"}, headers=_auth_headers()
    )

    assert response.status_code == 422
    assert not mock_auth_svc.table.return_value.update.called


def test_patch_account_returns_403_unauthenticated():
    response = client.patch("/api/account", json={"timezone": "UTC"})
    assert response.status_code == 403
