"""Sprint 4 — Busy slot sync + retrieval tests."""

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


# ─── 1. test_get_my_busy_slots ────────────────────────────────────────────────

@patch("app.routers.busy_slots.service_client")
@patch("app.dependencies.service_client")
def test_get_my_busy_slots(mock_dep_svc, mock_router_svc):
    """GET /api/busy-slots → 200 with list of busy slots for current user."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    slot = _make_busy_slot()
    mock_router_svc.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[slot])

    response = client.get("/api/busy-slots", headers=_auth_headers())

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["id"] == "slot-uuid-1"


# ─── 2. test_get_event_busy_slots ────────────────────────────────────────────

@patch("app.routers.busy_slots.service_client")
@patch("app.dependencies.service_client")
def test_get_event_busy_slots(mock_dep_svc, mock_router_svc):
    """GET /api/busy-slots/event/{uid} → 200 with slots for event participants."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    def make_table(table_name):
        tbl = MagicMock()
        if table_name == "events":
            tbl.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={"id": "event-db-id-1"}
            )
        elif table_name == "event_participants":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"user_id": "user-uuid-1"}]
            )
        elif table_name == "busy_slots":
            slot = _make_busy_slot()
            tbl.select.return_value.in_.return_value.order.return_value.execute.return_value = MagicMock(data=[slot])
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.get("/api/busy-slots/event/test-uid-1", headers=_auth_headers())

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# ─── 3. test_sync_my_slots ───────────────────────────────────────────────────

@patch("app.services.sync_service.service_client")
@patch("app.dependencies.service_client")
def test_sync_my_slots(mock_dep_svc, mock_sync_svc):
    """POST /api/busy-slots/sync → 200 with synced count."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    # No accounts → syncs 0
    mock_sync_svc.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    response = client.post("/api/busy-slots/sync", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["synced"] == 0


# ─── 4. test_sync_event_slots_coordinator_only ───────────────────────────────

@patch("app.routers.busy_slots.service_client")
@patch("app.dependencies.service_client")
def test_sync_event_slots_coordinator_only(mock_dep_svc, mock_router_svc):
    """POST /api/busy-slots/sync/event/{uid} → 403 for non-coordinator."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    # Event coordinator is someone else
    mock_router_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={"id": "event-db-id-1", "coordinator_id": "other-user"}
    )

    response = client.post("/api/busy-slots/sync/event/test-uid-1", headers=_auth_headers())

    assert response.status_code == 403


# ─── 5. test_busy_slots_require_auth ─────────────────────────────────────────

def test_busy_slots_require_auth():
    """GET /api/busy-slots without token → 403."""
    response = client.get("/api/busy-slots")
    assert response.status_code == 403
