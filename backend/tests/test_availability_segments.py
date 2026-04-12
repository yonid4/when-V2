"""Tests for GET /api/events/{uid}/availability-segments."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.main import app

client = TestClient(app)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _auth_headers(user_id: str = "user-1") -> dict:
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = jwt.encode(
        {"sub": user_id, "email": "alice@example.com", "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def _user_profile(user_id: str = "user-1") -> dict:
    return {"id": user_id, "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}


def _busy(start: str, end: str, user_id: str = "user-1") -> dict:
    return {"id": "b1", "user_id": user_id, "start_time_utc": start, "end_time_utc": end, "calendar_source_id": "cs1"}


def _pref(start: str, end: str, user_id: str = "user-2") -> dict:
    return {"id": "p1", "event_id": "evt-1", "user_id": user_id, "start_time_utc": start, "end_time_utc": end, "created_at": "2026-01-01T00:00:00+00:00"}


URL = "/api/events/evt-uid-1/availability-segments"


# ─── Tests ────────────────────────────────────────────────────────────────────

@patch("app.dependencies.service_client")
@patch("app.services.availability_service.busy_slots_service")
@patch("app.services.availability_service.preferred_slots_service")
def test_empty_when_no_slots(mock_pref_svc, mock_busy_svc, mock_dep):
    mock_dep.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_user_profile())
    mock_busy_svc.get_event_busy_slots.return_value = []
    mock_pref_svc.get_preferred_slots.return_value = []

    resp = client.get(URL, headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json() == []


@patch("app.dependencies.service_client")
@patch("app.services.availability_service.busy_slots_service")
@patch("app.services.availability_service.preferred_slots_service")
def test_busy_only_no_overlap(mock_pref_svc, mock_busy_svc, mock_dep):
    """Two non-overlapping busy slots from different users — two separate segments."""
    mock_dep.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_user_profile())
    mock_busy_svc.get_event_busy_slots.return_value = [
        _busy("2026-04-10T09:00:00+00:00", "2026-04-10T10:00:00+00:00", "user-1"),
        _busy("2026-04-10T11:00:00+00:00", "2026-04-10T12:00:00+00:00", "user-2"),
    ]
    mock_pref_svc.get_preferred_slots.return_value = []

    resp = client.get(URL, headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(s["type"] == "busy" for s in data)
    assert data[0]["start_time_utc"].startswith("2026-04-10T09:00")
    assert data[1]["start_time_utc"].startswith("2026-04-10T11:00")


@patch("app.dependencies.service_client")
@patch("app.services.availability_service.busy_slots_service")
@patch("app.services.availability_service.preferred_slots_service")
def test_busy_overlap_splits_at_boundary(mock_pref_svc, mock_busy_svc, mock_dep):
    """Two busy slots overlapping 9:30–10:00 — should produce 3 segments with correct counts."""
    mock_dep.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_user_profile())
    mock_busy_svc.get_event_busy_slots.return_value = [
        _busy("2026-04-10T09:00:00+00:00", "2026-04-10T10:00:00+00:00", "user-1"),
        _busy("2026-04-10T09:30:00+00:00", "2026-04-10T10:30:00+00:00", "user-2"),
    ]
    mock_pref_svc.get_preferred_slots.return_value = []

    resp = client.get(URL, headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    # 9:00–9:30 (count=1), 9:30–10:00 (count=2), 10:00–10:30 (count=1)
    # All tier-1 (count < 3), so they merge into one segment
    assert len(data) == 1
    assert data[0]["type"] == "busy"
    assert data[0]["busy_count"] == 2  # max of the merged group
    assert data[0]["start_time_utc"].startswith("2026-04-10T09:00")
    assert data[0]["end_time_utc"].startswith("2026-04-10T10:30")


@patch("app.dependencies.service_client")
@patch("app.services.availability_service.busy_slots_service")
@patch("app.services.availability_service.preferred_slots_service")
def test_busy_tier_boundary_does_not_merge(mock_pref_svc, mock_busy_svc, mock_dep):
    """Count crossing a tier boundary (2→3) should NOT merge segments."""
    mock_dep.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_user_profile())
    # 3 users busy 9:00–10:00, 2 users busy only 9:00–9:30 → 9:00–9:30 count=5, 9:30–10:00 count=3
    mock_busy_svc.get_event_busy_slots.return_value = [
        _busy("2026-04-10T09:00:00+00:00", "2026-04-10T10:00:00+00:00", "user-1"),
        _busy("2026-04-10T09:00:00+00:00", "2026-04-10T10:00:00+00:00", "user-2"),
        _busy("2026-04-10T09:00:00+00:00", "2026-04-10T10:00:00+00:00", "user-3"),
        _busy("2026-04-10T09:00:00+00:00", "2026-04-10T09:30:00+00:00", "user-4"),
        _busy("2026-04-10T09:00:00+00:00", "2026-04-10T09:30:00+00:00", "user-5"),
    ]
    mock_pref_svc.get_preferred_slots.return_value = []

    resp = client.get(URL, headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    # tier(5)=3, tier(3)=2 — different tiers, should not merge
    assert len(data) == 2
    assert data[0]["busy_count"] == 5
    assert data[1]["busy_count"] == 3


@patch("app.dependencies.service_client")
@patch("app.services.availability_service.busy_slots_service")
@patch("app.services.availability_service.preferred_slots_service")
def test_preferred_only(mock_pref_svc, mock_busy_svc, mock_dep):
    """Preferred-only slots produce preferred-type segments."""
    mock_dep.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_user_profile())
    mock_busy_svc.get_event_busy_slots.return_value = []
    mock_pref_svc.get_preferred_slots.return_value = [
        _pref("2026-04-10T14:00:00+00:00", "2026-04-10T15:00:00+00:00", "user-2"),
    ]

    resp = client.get(URL, headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["type"] == "preferred"
    assert data[0]["preferred_count"] == 1
    assert data[0]["busy_count"] == 0


@patch("app.dependencies.service_client")
@patch("app.services.availability_service.busy_slots_service")
@patch("app.services.availability_service.preferred_slots_service")
def test_full_conflict(mock_pref_svc, mock_busy_svc, mock_dep):
    """Busy and preferred fully overlapping → single conflict segment."""
    mock_dep.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_user_profile())
    mock_busy_svc.get_event_busy_slots.return_value = [
        _busy("2026-04-10T10:00:00+00:00", "2026-04-10T11:00:00+00:00", "user-1"),
    ]
    mock_pref_svc.get_preferred_slots.return_value = [
        _pref("2026-04-10T10:00:00+00:00", "2026-04-10T11:00:00+00:00", "user-2"),
    ]

    resp = client.get(URL, headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["type"] == "conflict"
    assert data[0]["busy_count"] == 1
    assert data[0]["preferred_count"] == 1


@patch("app.dependencies.service_client")
@patch("app.services.availability_service.busy_slots_service")
@patch("app.services.availability_service.preferred_slots_service")
def test_partial_conflict(mock_pref_svc, mock_busy_svc, mock_dep):
    """Busy 9–10, preferred 9:30–10:30 → busy[9–9:30], conflict[9:30–10], preferred[10–10:30]."""
    mock_dep.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_user_profile())
    mock_busy_svc.get_event_busy_slots.return_value = [
        _busy("2026-04-10T09:00:00+00:00", "2026-04-10T10:00:00+00:00", "user-1"),
    ]
    mock_pref_svc.get_preferred_slots.return_value = [
        _pref("2026-04-10T09:30:00+00:00", "2026-04-10T10:30:00+00:00", "user-2"),
    ]

    resp = client.get(URL, headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert data[0]["type"] == "busy"
    assert data[1]["type"] == "conflict"
    assert data[2]["type"] == "preferred"
    assert data[0]["start_time_utc"].startswith("2026-04-10T09:00")
    assert data[1]["start_time_utc"].startswith("2026-04-10T09:30")
    assert data[2]["start_time_utc"].startswith("2026-04-10T10:00")


@patch("app.dependencies.service_client")
def test_requires_auth(mock_dep):
    """Unauthenticated request should be rejected."""
    resp = client.get(URL)
    assert resp.status_code == 403
