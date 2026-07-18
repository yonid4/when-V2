"""Package 4 — chat booking orchestration tests (agent/booking.py).

Deterministic, no LLM. All collaborators (event_service, finalize_service,
invitation_service, Supabase clients) are mocked — no network.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.models.user import User
from app.services.agent import booking


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _coord() -> User:
    return User(
        id="coordinator-uuid-1",
        email_address="alice@example.com",
        full_name="Alice",
        token="tok",
    )


def _draft() -> dict:
    return {
        "title": "Lunch",
        "event_type": "social",
        "earliest_datetime_utc": "2026-04-10T00:00:00+00:00",
        "latest_datetime_utc": "2026-04-11T00:00:00+00:00",
        "duration_minutes": 60,
        "location": "Cafe",
    }


def _slot() -> dict:
    return {
        "start_time_utc": "2026-04-10T12:00:00+00:00",
        "end_time_utc": "2026-04-10T13:00:00+00:00",
        "conflict_count": 2,
        "free_count": 3,
        "total": 5,
        "reasoning": "3/5 free",
    }


_REF = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)


# ─── book_direct ─────────────────────────────────────────────────────────────

@patch("app.services.agent.booking.service_client")
@patch("app.services.agent.booking.get_authed_client")
@patch("app.services.agent.booking.finalize_service")
@patch("app.services.agent.booking.event_service")
def test_book_direct_rows_and_finalize(mock_event, mock_finalize, mock_get_authed, mock_service_client):
    """book_direct: in-system participants get invited/pending rows via the
    authed client, the confirmed slot is written as proposed_times rank 1 via the
    service client, and finalize is called with the pending user ids."""
    mock_event.create_event.return_value = SimpleNamespace(id="evt-db-1", uid="evt-uid-1", name="Lunch")

    db = MagicMock()
    mock_get_authed.return_value = db
    mock_service_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "pt-1"}]
    )
    mock_finalize.finalize_event.return_value = {"status": "confirmed"}

    participants = [
        {"user_id": "u2", "full_name": "Bob", "email": "bob@x.com", "in_system": True, "has_calendar": True, "source": "contact"},
        {"user_id": None, "full_name": "Ext", "email": "ext@x.com", "in_system": False, "has_calendar": False, "source": "manual"},
    ]

    result = booking.book_direct(_coord(), _draft(), participants, _slot(), _REF)

    assert result == {"event_uid": "evt-uid-1"}

    # Participant rows: only the in-system, non-coordinator user; correct shape.
    part_rows = db.table.return_value.insert.call_args[0][0]
    assert part_rows == [{
        "event_id": "evt-db-1",
        "user_id": "u2",
        "status": "invited",
        "rsvp_status": "pending",
        "can_invite": False,
        "joined_at": "2026-04-01T09:00:00+00:00",
    }]

    # proposed_times rank-1 row via the service client.
    assert mock_service_client.table.call_args[0][0] == "proposed_times"
    pt_row = mock_service_client.table.return_value.insert.call_args[0][0]
    assert pt_row == {
        "event_id": "evt-db-1",
        "start_time_utc": "2026-04-10T12:00:00+00:00",
        "end_time_utc": "2026-04-10T13:00:00+00:00",
        "conflicts": 2,
        "preferred_count": 0,
        "reasoning": "Booked via chat",
        "rank": 1,
    }

    # finalize called with the pending ids and the event uid + proposed time id.
    call = mock_finalize.finalize_event.call_args
    assert call.args[0] == "evt-uid-1"
    assert call.args[1] == "pt-1"
    assert call.args[2] == "Lunch"
    assert call.kwargs["pending_attendee_user_ids"] == ["u2"]
    assert call.kwargs["location"] == "Cafe"


@patch("app.services.agent.booking.service_client")
@patch("app.services.agent.booking.get_authed_client")
@patch("app.services.agent.booking.finalize_service")
@patch("app.services.agent.booking.event_service")
def test_book_direct_finalize_error_returns_error_code(mock_event, mock_finalize, mock_get_authed, mock_service_client):
    """A finalize HTTPException (e.g. no_write_calendar) is caught and surfaced as
    an error_code — never raised — and the planning event uid is still returned."""
    mock_event.create_event.return_value = SimpleNamespace(id="evt-db-1", uid="evt-uid-1", name="Lunch")

    mock_get_authed.return_value = MagicMock()
    mock_service_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "pt-1"}]
    )
    mock_finalize.finalize_event.side_effect = HTTPException(status_code=422, detail="no_write_calendar")

    participants = [
        {"user_id": "u2", "full_name": "Bob", "email": "bob@x.com", "in_system": True, "has_calendar": True, "source": "contact"},
    ]

    result = booking.book_direct(_coord(), _draft(), participants, _slot(), _REF)

    assert result == {"event_uid": "evt-uid-1", "error_code": "no_write_calendar"}


@patch("app.services.agent.booking.service_client")
@patch("app.services.agent.booking.get_authed_client")
@patch("app.services.agent.booking.finalize_service")
@patch("app.services.agent.booking.event_service")
def test_book_direct_creates_no_invitations(mock_event, mock_finalize, mock_get_authed, mock_service_client):
    """book_direct must NOT create event_invitations rows (they would PK-collide
    with the participant row on accept)."""
    mock_event.create_event.return_value = SimpleNamespace(id="evt-db-1", uid="evt-uid-1", name="Lunch")
    db = MagicMock()
    mock_get_authed.return_value = db
    mock_service_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "pt-1"}]
    )
    mock_finalize.finalize_event.return_value = {"status": "confirmed"}

    participants = [
        {"user_id": "u2", "full_name": "Bob", "email": "bob@x.com", "in_system": True, "has_calendar": True, "source": "contact"},
    ]
    booking.book_direct(_coord(), _draft(), participants, _slot(), _REF)

    authed_tables = [c.args[0] for c in db.table.call_args_list]
    service_tables = [c.args[0] for c in mock_service_client.table.call_args_list]
    assert "event_invitations" not in authed_tables
    assert "event_invitations" not in service_tables


# ─── create_in_app_event ─────────────────────────────────────────────────────

@patch("app.services.agent.booking.invitation_service")
@patch("app.services.agent.booking.event_service")
def test_create_in_app_event_invites_each_and_tolerates_409(mock_event, mock_invitation):
    """create_in_app_event invites every non-coordinator participant by email;
    a 409 (already participant/invited) is tolerated, not raised."""
    mock_event.create_event.return_value = SimpleNamespace(id="evt-db-1", uid="evt-uid-1", name="Lunch")

    invited: list = []

    def _invite(uid, current_user, email):
        invited.append(email)
        if email == "carol@x.com":
            raise HTTPException(status_code=409, detail="User is already a participant")
        return MagicMock()

    mock_invitation.invite_by_email.side_effect = _invite

    participants = [
        {"user_id": "coordinator-uuid-1", "email": "alice@example.com", "in_system": True},  # coordinator → skipped
        {"user_id": "u2", "full_name": "Bob", "email": "bob@x.com", "in_system": True},
        {"user_id": None, "full_name": "Carol", "email": "carol@x.com", "in_system": False},
    ]

    result = booking.create_in_app_event(_coord(), _draft(), participants)

    assert result == {"event_uid": "evt-uid-1"}
    # One invite per non-coordinator person; the coordinator was not invited.
    assert invited == ["bob@x.com", "carol@x.com"]


@patch("app.services.agent.booking.invitation_service")
@patch("app.services.agent.booking.event_service")
def test_create_in_app_event_reraises_non_409(mock_event, mock_invitation):
    """A non-409 invite error propagates (only 409 is tolerated)."""
    mock_event.create_event.return_value = SimpleNamespace(id="evt-db-1", uid="evt-uid-1", name="Lunch")
    mock_invitation.invite_by_email.side_effect = HTTPException(status_code=403, detail="nope")

    participants = [{"user_id": "u2", "email": "bob@x.com", "in_system": True}]

    try:
        booking.create_in_app_event(_coord(), _draft(), participants)
        assert False, "expected HTTPException to propagate"
    except HTTPException as exc:
        assert exc.status_code == 403
