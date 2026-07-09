"""Sprint 6A — Proposals tests.

Tests the proposals router and proposal_service with mocked Supabase service_client.
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

def _auth_headers(user_id: str = "coordinator-uuid-1", email: str = "alice@example.com") -> dict:
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = jwt.encode(
        {"sub": user_id, "email": email, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def _current_user_profile(user_id: str = "coordinator-uuid-1") -> dict:
    return {"id": user_id, "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}


def _make_event_row(**overrides) -> dict:
    defaults = {
        "id": "event-db-id-1",
        "coordinator_id": "coordinator-uuid-1",
        "proposals_needs_regeneration": False,
        "duration_minutes": 60,
        "earliest_datetime_utc": "2026-04-10T09:00:00+00:00",
        "latest_datetime_utc": "2026-04-10T17:00:00+00:00",
    }
    return {**defaults, **overrides}


def _make_proposal_row(**overrides) -> dict:
    defaults = {
        "id": "proposal-uuid-1",
        "event_id": "event-db-id-1",
        "start_time_utc": "2026-04-10T09:00:00+00:00",
        "end_time_utc": "2026-04-10T10:00:00+00:00",
        "conflicts": 0,
        "preferred_count": 1,
        "reasoning": "2/2 participants free, 1 marked as preferred",
        "rank": 1,
    }
    return {**defaults, **overrides}


def _make_db_for_proposals(
    event_row: dict,
    proposals: list[dict] | None = None,
    participants: list[dict] | None = None,
    busy_slots: list[dict] | None = None,
    preferred_slots: list[dict] | None = None,
    participant_row: dict | None = None,
) -> MagicMock:
    """Build a db mock that routes table() calls to appropriate mocks."""
    proposals = proposals or []
    participants = participants or []
    busy_slots = busy_slots or []
    preferred_slots = preferred_slots or []

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "event_participants":
            if participant_row is not None:
                # For router access check (accepted participant)
                tbl.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                    data=participant_row
                )
            else:
                tbl.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                    data=None
                )
            # For generate_proposals — fetches accepted participants (no third .eq)
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=participants
            )
        elif name == "proposed_times":
            tbl.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
                data=proposals
            )
            tbl.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            tbl.insert.return_value.execute.return_value = MagicMock(data=proposals)
        elif name == "busy_slots":
            tbl.select.return_value.in_.return_value.lt.return_value.gt.return_value.execute.return_value = MagicMock(
                data=busy_slots
            )
        elif name == "preferred_slots":
            tbl.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(
                data=preferred_slots
            )
        return tbl

    db = MagicMock()
    db.table.side_effect = make_table
    return db


# ─── POST /api/events/{uid}/proposals ────────────────────────────────────────

@patch("app.services.proposal_service.service_client")
@patch("app.dependencies.service_client")
def test_get_proposals_returns_cached_when_fresh(mock_dep_svc, mock_router_svc):
    """Returns cached proposals when proposals_needs_regeneration is False and rows exist."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row(proposals_needs_regeneration=False)
    proposal_row = _make_proposal_row()

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
        elif name == "proposed_times":
            tbl.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
                data=[proposal_row]
            )
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.post(
        "/api/events/event-uid-1/proposals",
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "proposal-uuid-1"
    assert data[0]["conflict_count"] == 0
    assert data[0]["preferred_count"] == 1
    assert data[0]["rank"] == 1


@patch("app.services.proposal_service.service_client")
@patch("app.dependencies.service_client")
def test_get_proposals_regenerates_when_stale(mock_dep_svc, mock_svc_svc):
    """Calls generate_proposals when proposals_needs_regeneration is True."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row(proposals_needs_regeneration=True)
    proposal_row = _make_proposal_row()

    def make_svc_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"user_id": "coordinator-uuid-1"}]
            )
        elif name == "proposed_times":
            tbl.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            tbl.insert.return_value.execute.return_value = MagicMock(data=[proposal_row])
        elif name == "busy_slots":
            tbl.select.return_value.in_.return_value.lt.return_value.gt.return_value.execute.return_value = MagicMock(data=[])
        elif name == "preferred_slots":
            tbl.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    mock_svc_svc.table.side_effect = make_svc_table

    response = client.post(
        "/api/events/event-uid-1/proposals",
        headers=_auth_headers(),
    )
    assert response.status_code == 200


@patch("app.services.proposal_service.service_client")
@patch("app.dependencies.service_client")
def test_get_proposals_404_event_not_found(mock_dep_svc, mock_router_svc):
    """Returns 404 when event does not exist."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=None
            )
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.post(
        "/api/events/nonexistent-uid/proposals",
        headers=_auth_headers(),
    )
    assert response.status_code == 404


@patch("app.services.proposal_service.service_client")
@patch("app.dependencies.service_client")
def test_get_proposals_403_not_participant(mock_dep_svc, mock_router_svc):
    """Returns 403 when user is not coordinator or accepted participant."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("outsider-uuid")
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1")

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=None
            )
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.post(
        "/api/events/event-uid-1/proposals",
        headers=_auth_headers("outsider-uuid"),
    )
    assert response.status_code == 403


@patch("app.services.proposal_service.service_client")
@patch("app.dependencies.service_client")
def test_get_proposals_accepted_participant_can_access(mock_dep_svc, mock_router_svc):
    """Accepted participant (not coordinator) can fetch proposals."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("participant-uuid")
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1", proposals_needs_regeneration=False)
    proposal_row = _make_proposal_row()

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"user_id": "participant-uuid"}
            )
        elif name == "proposed_times":
            tbl.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
                data=[proposal_row]
            )
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.post(
        "/api/events/event-uid-1/proposals",
        headers=_auth_headers("participant-uuid"),
    )
    assert response.status_code == 200


# ─── POST /api/events/{uid}/proposals/refresh ────────────────────────────────

@patch("app.services.proposal_service.service_client")
@patch("app.dependencies.service_client")
def test_refresh_proposals_coordinator_only(mock_dep_svc, mock_router_svc):
    """Non-coordinator gets 403 on refresh endpoint."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("participant-uuid")
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1")

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.post(
        "/api/events/event-uid-1/proposals/refresh",
        headers=_auth_headers("participant-uuid"),
    )
    assert response.status_code == 403


@patch("app.services.proposal_service.service_client")
@patch("app.dependencies.service_client")
def test_refresh_proposals_success(mock_dep_svc, mock_svc_svc):
    """Coordinator can force-refresh proposals."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row()
    proposal_row = _make_proposal_row()

    def make_svc_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"user_id": "coordinator-uuid-1"}]
            )
        elif name == "proposed_times":
            tbl.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            tbl.insert.return_value.execute.return_value = MagicMock(data=[proposal_row])
        elif name == "busy_slots":
            tbl.select.return_value.in_.return_value.lt.return_value.gt.return_value.execute.return_value = MagicMock(data=[])
        elif name == "preferred_slots":
            tbl.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    mock_svc_svc.table.side_effect = make_svc_table

    response = client.post(
        "/api/events/event-uid-1/proposals/refresh",
        headers=_auth_headers(),
    )
    assert response.status_code == 200


# ─── generate_proposals unit tests ───────────────────────────────────────────

from app.services.proposal_service import generate_proposals


def _make_generate_db(
    event_row: dict,
    participants: list[dict],
    busy_slots: list[dict],
    preferred_slots: list[dict],
    inserted_rows: list[dict],
) -> MagicMock:
    """Build a db mock for generate_proposals unit tests."""
    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=participants
            )
        elif name == "busy_slots":
            tbl.select.return_value.in_.return_value.lt.return_value.gt.return_value.execute.return_value = MagicMock(
                data=busy_slots
            )
        elif name == "preferred_slots":
            tbl.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(
                data=preferred_slots
            )
        elif name == "proposed_times":
            tbl.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            tbl.insert.return_value.execute.return_value = MagicMock(data=inserted_rows)
        return tbl

    db = MagicMock()
    db.table.side_effect = make_table
    return db


def test_generate_proposals_returns_empty_when_event_not_found():
    """Returns [] when event row does not exist."""
    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=None
            )
        return tbl

    db = MagicMock()
    db.table.side_effect = make_table

    result = generate_proposals(
        "nonexistent-id",
        reference_time_utc=datetime(2026, 4, 1, tzinfo=timezone.utc),
        db=db,
    )
    assert result == []


def test_generate_proposals_scores_conflicts():
    """Candidates overlapping a busy slot get a higher conflict_count."""
    event_row = {
        "id": "event-db-id-1",
        "duration_minutes": 60,
        "earliest_datetime_utc": "2026-04-10T09:00:00+00:00",
        "latest_datetime_utc": "2026-04-10T12:00:00+00:00",
    }
    participants = [{"user_id": "alice"}, {"user_id": "bob"}]
    # Bob is busy 09:00–10:00
    busy_slots = [
        {"user_id": "bob", "start_time_utc": "2026-04-10T09:00:00+00:00", "end_time_utc": "2026-04-10T10:00:00+00:00"}
    ]
    inserted_rows = [
        {
            "id": "p1", "event_id": "event-db-id-1",
            "start_time_utc": "2026-04-10T10:00:00+00:00",
            "end_time_utc": "2026-04-10T11:00:00+00:00",
            "conflicts": 0, "preferred_count": 0,
            "reasoning": "2/2 participants free", "rank": 1,
        }
    ]

    proposed_times_mock = MagicMock()
    proposed_times_mock.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    proposed_times_mock.insert.return_value.execute.return_value = MagicMock(data=inserted_rows)

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=participants)
        elif name == "busy_slots":
            tbl.select.return_value.in_.return_value.lt.return_value.gt.return_value.execute.return_value = MagicMock(data=busy_slots)
        elif name == "preferred_slots":
            tbl.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
        elif name == "proposed_times":
            return proposed_times_mock
        return tbl

    db = MagicMock()
    db.table.side_effect = make_table

    generate_proposals(
        "event-db-id-1",
        reference_time_utc=datetime(2026, 4, 1, tzinfo=timezone.utc),
        db=db,
    )

    # Verify insert was called and the rank-1 row has 0 conflicts (conflict-free slots ranked first)
    call_args = proposed_times_mock.insert.call_args
    assert call_args is not None
    inserted = call_args[0][0]
    assert inserted[0]["conflicts"] == 0


def test_generate_proposals_preferred_count_scored():
    """Candidates overlapping a preferred slot get a higher preferred_count."""
    event_row = {
        "id": "event-db-id-1",
        "duration_minutes": 60,
        "earliest_datetime_utc": "2026-04-10T09:00:00+00:00",
        "latest_datetime_utc": "2026-04-10T12:00:00+00:00",
    }
    participants = [{"user_id": "alice"}]
    preferred_slots = [
        {"user_id": "alice", "start_time_utc": "2026-04-10T10:00:00+00:00", "end_time_utc": "2026-04-10T11:00:00+00:00"}
    ]
    inserted_rows = [
        {
            "id": "p1", "event_id": "event-db-id-1",
            "start_time_utc": "2026-04-10T10:00:00+00:00",
            "end_time_utc": "2026-04-10T11:00:00+00:00",
            "conflicts": 0, "preferred_count": 1,
            "reasoning": "1/1 participants free, 1 marked as preferred", "rank": 1,
        }
    ]

    proposed_times_mock = MagicMock()
    proposed_times_mock.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    proposed_times_mock.insert.return_value.execute.return_value = MagicMock(data=inserted_rows)

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=participants)
        elif name == "busy_slots":
            tbl.select.return_value.in_.return_value.lt.return_value.gt.return_value.execute.return_value = MagicMock(data=[])
        elif name == "preferred_slots":
            tbl.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(data=preferred_slots)
        elif name == "proposed_times":
            return proposed_times_mock
        return tbl

    db = MagicMock()
    db.table.side_effect = make_table

    generate_proposals(
        "event-db-id-1",
        reference_time_utc=datetime(2026, 4, 1, tzinfo=timezone.utc),
        db=db,
    )

    call_args = proposed_times_mock.insert.call_args
    assert call_args is not None
    inserted = call_args[0][0]
    # The slot overlapping the preferred window should have preferred_count=1
    preferred_slot = next((r for r in inserted if r["start_time_utc"].startswith("2026-04-10T10:00")), None)
    assert preferred_slot is not None
    assert preferred_slot["preferred_count"] == 1


def test_generate_proposals_updates_event_metadata():
    """generate_proposals sets proposals_needs_regeneration=False on the event."""
    event_row = {
        "id": "event-db-id-1",
        "duration_minutes": 60,
        "earliest_datetime_utc": "2026-04-10T09:00:00+00:00",
        "latest_datetime_utc": "2026-04-10T11:00:00+00:00",
    }

    events_mock = MagicMock()
    events_mock.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=event_row
    )
    update_mock = MagicMock()
    events_mock.update.return_value = update_mock

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            return events_mock
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "proposed_times":
            tbl.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            tbl.insert.return_value.execute.return_value = MagicMock(data=[])
        elif name == "busy_slots":
            tbl.select.return_value.in_.return_value.lt.return_value.gt.return_value.execute.return_value = MagicMock(data=[])
        elif name == "preferred_slots":
            tbl.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    db = MagicMock()
    db.table.side_effect = make_table

    generate_proposals(
        "event-db-id-1",
        reference_time_utc=datetime(2026, 4, 1, tzinfo=timezone.utc),
        db=db,
    )

    update_call = events_mock.update.call_args[0][0]
    assert update_call["proposals_needs_regeneration"] is False
    assert "proposals_last_generated_at" in update_call


# ─── Regression: M8 wrap-around window upper-bound clamp ──────────────────────

def test_generate_proposals_clamps_wraparound_candidates_to_window():
    """M8 regression: a wrap-around (overnight) window must never propose a slot
    whose meeting extends past latest_datetime_utc.

    Window Jul 6 20:00 → Jul 10 03:00 UTC is a wrap window (20:00–03:00). The
    last day (Jul 10) would otherwise emit an evening segment starting 20:00,
    which lies entirely after the 03:00 upper bound. Duration is 240 min so that
    only in-window nightly slots exist and, without the clamp, the spurious
    Jul 10 evening candidate ranks into the persisted top-5 — making this a true
    regression test rather than one masked by top-5 truncation. Every inserted
    row's end must be <= latest_datetime_utc.
    """
    latest_iso = "2026-07-10T03:00:00+00:00"
    duration_min = 240
    event_row = {
        "id": "event-db-id-1",
        "duration_minutes": duration_min,
        "earliest_datetime_utc": "2026-07-06T20:00:00+00:00",
        "latest_datetime_utc": latest_iso,
    }

    proposed_times_mock = MagicMock()
    proposed_times_mock.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    proposed_times_mock.insert.return_value.execute.return_value = MagicMock(data=[])

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "busy_slots":
            tbl.select.return_value.in_.return_value.lt.return_value.gt.return_value.execute.return_value = MagicMock(data=[])
        elif name == "preferred_slots":
            tbl.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
        elif name == "proposed_times":
            return proposed_times_mock
        return tbl

    db = MagicMock()
    db.table.side_effect = make_table

    generate_proposals(
        "event-db-id-1",
        reference_time_utc=datetime(2026, 7, 1, tzinfo=timezone.utc),
        db=db,
    )

    call_args = proposed_times_mock.insert.call_args
    assert call_args is not None
    inserted = call_args[0][0]
    assert inserted, "expected at least one in-window candidate"

    latest_dt = datetime.fromisoformat(latest_iso)
    duration = timedelta(minutes=duration_min)
    for row in inserted:
        start = datetime.fromisoformat(row["start_time_utc"])
        end = datetime.fromisoformat(row["end_time_utc"])
        assert end <= latest_dt, f"candidate {row['start_time_utc']} extends past window end"
        assert start + duration <= latest_dt


# ─── Regression: M9 determinism ──────────────────────────────────────────────

def test_generate_proposals_is_deterministic_for_fixed_reference_time():
    """M9 regression: identical inputs and the same reference_time_utc must yield
    byte-identical persisted candidate rows, proving no wall-clock dependence."""
    event_row = {
        "id": "event-db-id-1",
        "duration_minutes": 60,
        "earliest_datetime_utc": "2026-04-10T09:00:00+00:00",
        "latest_datetime_utc": "2026-04-10T17:00:00+00:00",
    }
    reference_time = datetime(2026, 4, 1, tzinfo=timezone.utc)

    def run_once() -> list[dict]:
        proposed_times_mock = MagicMock()
        proposed_times_mock.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        proposed_times_mock.insert.return_value.execute.return_value = MagicMock(data=[])

        def make_table(name):
            tbl = MagicMock()
            if name == "events":
                tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
                tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            elif name == "event_participants":
                tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            elif name == "busy_slots":
                tbl.select.return_value.in_.return_value.lt.return_value.gt.return_value.execute.return_value = MagicMock(data=[])
            elif name == "preferred_slots":
                tbl.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
            elif name == "proposed_times":
                return proposed_times_mock
            return tbl

        db = MagicMock()
        db.table.side_effect = make_table
        generate_proposals("event-db-id-1", reference_time_utc=reference_time, db=db)
        return proposed_times_mock.insert.call_args[0][0]

    first = run_once()
    second = run_once()

    assert first == second
    assert [r["start_time_utc"] for r in first] == [r["start_time_utc"] for r in second]
    assert [r["end_time_utc"] for r in first] == [r["end_time_utc"] for r in second]
