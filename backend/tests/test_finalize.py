"""Sprint 6B/6C — Event finalization tests.

Tests the finalize router and finalize_service with mocked Supabase service_client
and mocked Google Calendar API.
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
        "uid": "event-uid-1",
        "name": "Team Lunch",
        "coordinator_id": "coordinator-uuid-1",
        "status": "planning",
        "finalized_start_time_utc": None,
        "finalized_end_time_utc": None,
        "google_calendar_event_id": None,
    }
    return {**defaults, **overrides}


def _make_proposed_time_row(**overrides) -> dict:
    defaults = {
        "id": "pt-uuid-1",
        "event_id": "event-db-id-1",
        "start_time_utc": "2026-04-10T12:00:00+00:00",
        "end_time_utc": "2026-04-10T13:00:00+00:00",
    }
    return {**defaults, **overrides}


def _make_finalize_db(
    event_row: dict,
    proposed_time_row: dict | None = None,
    participants: list[dict] | None = None,
    coordinator_participant: dict | None = None,
    write_cal_rows: list[dict] | None = None,
    creds_row: dict | None = None,
    updated_event: dict | None = None,
) -> MagicMock:
    """Build a db mock that routes table() calls for finalize_service."""
    participants = participants or []
    write_cal_rows = write_cal_rows or []
    creds_row = creds_row or {
        "id": "cal-account-1",
        "credentials": {
            "access_token": "access-tok",
            "refresh_token": "refresh-tok",
        },
    }
    updated_event = updated_event or {**event_row, "status": "confirmed", "google_calendar_event_id": "gcal-id-1"}

    # Default coordinator participant (for coordinator lookup)
    _coordinator_participant = coordinator_participant or {
        "user_id": "coordinator-uuid-1",
        "profiles": {
            "email_address": "alice@example.com",
            "full_name": "Alice",
            "calendar_accounts": [],
        },
    }

    # Track how many times event_participants is queried so the second call
    # (coordinator lookup) returns the coordinator row.
    _ep_call_count = [0]

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[updated_event]
            )
        elif name == "proposed_times":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=proposed_time_row
            )
        elif name == "event_participants":
            # First call: accepted participants list (no maybe_single, returns list)
            # Second call: coordinator lookup (maybe_single, returns single row)
            # We route by presence of maybe_single in the chain depth.
            # The accepted-participants query ends in .execute() without .maybe_single()
            # The coordinator query ends in .maybe_single().execute()
            # We can distinguish by returning different mocks for chained .eq calls.
            # Simplest: first call is .eq.eq.execute; second is .eq.eq.maybe_single.execute
            # We use side_effect on select to count calls.
            _ep_call_count[0] += 1
            call_num = _ep_call_count[0]
            if call_num == 1:
                # Accepted participants: .select().eq(event_id).eq(status).execute()
                tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=participants
                )
                tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                    data=_coordinator_participant
                )
            else:
                # Coordinator lookup: .select().eq(event_id).eq(user_id).maybe_single().execute()
                tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                    data=_coordinator_participant
                )
                tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=participants
                )
        elif name == "calendar_sources":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=write_cal_rows
            )
        elif name == "calendar_accounts":
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=creds_row
            )
        elif name == "notifications":
            tbl.insert.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    db = MagicMock()
    db.table.side_effect = make_table
    return db


def _make_write_cal_row(**overrides) -> dict:
    defaults = {
        "id": "cal-source-1",
        "calendar_id": "primary",
        "calendar_accounts": {"user_id": "coordinator-uuid-1"},
    }
    return {**defaults, **overrides}


def _make_participant(user_id: str, email: str, google_email: str | None = None) -> dict:
    cal_accounts = []
    if google_email:
        cal_accounts = [{"provider": "google", "provider_email": google_email}]
    return {
        "user_id": user_id,
        "profiles": {
            "email_address": email,
            "full_name": user_id.split("-")[0].capitalize(),
            "calendar_accounts": cal_accounts,
        },
    }


# ─── _pick_attendee_email unit tests ─────────────────────────────────────────

from app.services.finalize_service import _pick_attendee_email


def test_pick_attendee_email_prefers_google_provider_email():
    """When participant has a Google calendar_account, use provider_email."""
    participant = {
        "profiles": {
            "email_address": "bob@example.com",
            "full_name": "Bob",
            "calendar_accounts": [
                {"provider": "google", "provider_email": "bob@gmail.com"}
            ],
        }
    }
    assert _pick_attendee_email(participant) == "bob@gmail.com"


def test_pick_attendee_email_falls_back_to_profile_email():
    """When no Google calendar_account exists, fall back to profile email."""
    participant = {
        "profiles": {
            "email_address": "carol@example.com",
            "full_name": "Carol",
            "calendar_accounts": [],
        }
    }
    assert _pick_attendee_email(participant) == "carol@example.com"


def test_pick_attendee_email_no_calendar_accounts_key():
    """When calendar_accounts key is absent entirely, fall back to profile email."""
    participant = {
        "profiles": {
            "email_address": "dave@example.com",
            "full_name": "Dave",
        }
    }
    assert _pick_attendee_email(participant) == "dave@example.com"


def test_pick_attendee_email_skips_non_google_accounts():
    """Non-Google provider accounts are not used; falls back to profile email."""
    participant = {
        "profiles": {
            "email_address": "eve@example.com",
            "full_name": "Eve",
            "calendar_accounts": [
                {"provider": "microsoft", "provider_email": "eve@outlook.com"}
            ],
        }
    }
    assert _pick_attendee_email(participant) == "eve@example.com"


def test_pick_attendee_email_none_when_no_emails():
    """Returns None when both profile email and calendar accounts are absent."""
    participant = {"profiles": {}}
    assert _pick_attendee_email(participant) is None


# ─── POST /api/events/{uid}/finalize ─────────────────────────────────────────

@patch("app.utils.notifications.service_client")
@patch("app.services.finalize_service.create_calendar_event", return_value="gcal-event-123")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_success(mock_dep_svc, mock_svc_svc, mock_create_cal, mock_notif_svc):
    """Coordinator can finalize an event — returns confirmed event row."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row()
    proposed_time = _make_proposed_time_row()
    write_cal = _make_write_cal_row()

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=event_row,
        proposed_time_row=proposed_time,
        participants=[_make_participant("bob-uuid", "bob@example.com", "bob@gmail.com")],
        write_cal_rows=[write_cal],
    ).table.side_effect

    response = client.post(
        "/api/events/event-uid-1/finalize",
        json={
            "proposed_time_id": "pt-uuid-1",
            "name": "Team Lunch",
            "note": "Looking forward to it!",
            "excluded_user_ids": [],
            "extra_emails": [],
            "location": "",
            "video_call_link": "",
        },
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    assert mock_create_cal.called


@patch("app.services.finalize_service.create_calendar_event", return_value="gcal-event-123")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_404_event_not_found(mock_dep_svc, mock_svc_svc, mock_create_cal):
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

    mock_svc_svc.table.side_effect = make_table

    response = client.post(
        "/api/events/nonexistent-uid/finalize",
        json={
            "proposed_time_id": "pt-uuid-1",
            "name": "Event",
            "note": "",
            "excluded_user_ids": [],
            "extra_emails": [],
            "location": "",
            "video_call_link": "",
        },
        headers=_auth_headers(),
    )
    assert response.status_code == 404


@patch("app.services.finalize_service.create_calendar_event", return_value="gcal-event-123")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_403_not_coordinator(mock_dep_svc, mock_svc_svc, mock_create_cal):
    """Returns 403 when the caller is not the coordinator."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("other-user-uuid")
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1")

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
        return tbl

    mock_svc_svc.table.side_effect = make_table

    response = client.post(
        "/api/events/event-uid-1/finalize",
        json={
            "proposed_time_id": "pt-uuid-1",
            "name": "Event",
            "note": "",
            "excluded_user_ids": [],
            "extra_emails": [],
            "location": "",
            "video_call_link": "",
        },
        headers=_auth_headers("other-user-uuid"),
    )
    assert response.status_code == 403


@patch("app.services.finalize_service.create_calendar_event", return_value="gcal-event-123")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_422_no_write_calendar(mock_dep_svc, mock_svc_svc, mock_create_cal):
    """Returns 422 when coordinator has no write calendar configured."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row()
    proposed_time = _make_proposed_time_row()

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=event_row,
        proposed_time_row=proposed_time,
        write_cal_rows=[],  # No write calendar
    ).table.side_effect

    response = client.post(
        "/api/events/event-uid-1/finalize",
        json={
            "proposed_time_id": "pt-uuid-1",
            "name": "Team Lunch",
            "note": "",
            "excluded_user_ids": [],
            "extra_emails": [],
            "location": "",
            "video_call_link": "",
        },
        headers=_auth_headers(),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "no_write_calendar"


@patch("app.services.finalize_service.create_calendar_event", side_effect=Exception("Calendar API failed"))
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_502_calendar_api_error(mock_dep_svc, mock_svc_svc, mock_create_cal):
    """Returns 502 when Google Calendar API fails — DB is NOT updated."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row()
    proposed_time = _make_proposed_time_row()
    write_cal = _make_write_cal_row()

    db_mock = _make_finalize_db(
        event_row=event_row,
        proposed_time_row=proposed_time,
        write_cal_rows=[write_cal],
    )
    mock_svc_svc.table.side_effect = db_mock.table.side_effect

    response = client.post(
        "/api/events/event-uid-1/finalize",
        json={
            "proposed_time_id": "pt-uuid-1",
            "name": "Team Lunch",
            "note": "",
            "excluded_user_ids": [],
            "extra_emails": [],
            "location": "",
            "video_call_link": "",
        },
        headers=_auth_headers(),
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "calendar_create_failed"


# ─── Sprint 6C: new attendee / field tests ───────────────────────────────────

@patch("app.utils.notifications.service_client")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_excluded_user_ids_removed_from_attendees(mock_dep_svc, mock_svc_svc, mock_notif_svc):
    """Participants listed in excluded_user_ids are not added as attendees."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row()
    proposed_time = _make_proposed_time_row()
    write_cal = _make_write_cal_row()

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=event_row,
        proposed_time_row=proposed_time,
        participants=[
            _make_participant("bob-uuid", "bob@example.com"),
            _make_participant("carol-uuid", "carol@example.com"),
        ],
        write_cal_rows=[write_cal],
    ).table.side_effect

    captured_body = {}

    def fake_create(credentials, calendar_id, event_body):
        captured_body.update(event_body)
        return "gcal-1"

    with patch("app.services.finalize_service.create_calendar_event", side_effect=fake_create):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": ["carol-uuid"],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    attendee_emails = [a["email"] for a in captured_body.get("attendees", [])]
    assert "bob@example.com" in attendee_emails
    assert "carol@example.com" not in attendee_emails


@patch("app.utils.notifications.service_client")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_extra_emails_added_to_attendees(mock_dep_svc, mock_svc_svc, mock_notif_svc):
    """Emails in extra_emails are appended to the attendees list."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row()
    proposed_time = _make_proposed_time_row()
    write_cal = _make_write_cal_row()

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=event_row,
        proposed_time_row=proposed_time,
        participants=[_make_participant("bob-uuid", "bob@example.com")],
        write_cal_rows=[write_cal],
    ).table.side_effect

    captured_body = {}

    def fake_create(credentials, calendar_id, event_body):
        captured_body.update(event_body)
        return "gcal-1"

    with patch("app.services.finalize_service.create_calendar_event", side_effect=fake_create):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": ["external@partner.com"],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    attendee_emails = [a["email"] for a in captured_body.get("attendees", [])]
    assert "bob@example.com" in attendee_emails
    assert "external@partner.com" in attendee_emails


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_location_in_gcal_body(mock_dep_svc, mock_svc_svc):
    """location field appears in Google Calendar event body."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row()
    proposed_time = _make_proposed_time_row()
    write_cal = _make_write_cal_row()

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=event_row,
        proposed_time_row=proposed_time,
        write_cal_rows=[write_cal],
    ).table.side_effect

    captured_body = {}

    def fake_create(credentials, calendar_id, event_body):
        captured_body.update(event_body)
        return "gcal-1"

    with patch("app.services.finalize_service.create_calendar_event", side_effect=fake_create):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "123 Main St",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    assert captured_body.get("location") == "123 Main St"


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_video_call_link_in_description(mock_dep_svc, mock_svc_svc):
    """video_call_link appears in description as 'Video call: {link}'."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row()
    proposed_time = _make_proposed_time_row()
    write_cal = _make_write_cal_row()

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=event_row,
        proposed_time_row=proposed_time,
        write_cal_rows=[write_cal],
    ).table.side_effect

    captured_body = {}

    def fake_create(credentials, calendar_id, event_body):
        captured_body.update(event_body)
        return "gcal-1"

    with patch("app.services.finalize_service.create_calendar_event", side_effect=fake_create):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "https://meet.example.com/abc",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    assert captured_body.get("description") == "Video call: https://meet.example.com/abc"


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_note_and_video_call_link_combined(mock_dep_svc, mock_svc_svc):
    """note + video_call_link produces '{note}\n\nVideo call: {link}' description."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row()
    proposed_time = _make_proposed_time_row()
    write_cal = _make_write_cal_row()

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=event_row,
        proposed_time_row=proposed_time,
        write_cal_rows=[write_cal],
    ).table.side_effect

    captured_body = {}

    def fake_create(credentials, calendar_id, event_body):
        captured_body.update(event_body)
        return "gcal-1"

    with patch("app.services.finalize_service.create_calendar_event", side_effect=fake_create):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "See you there!",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "https://meet.example.com/xyz",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    expected = "See you there!\n\nVideo call: https://meet.example.com/xyz"
    assert captured_body.get("description") == expected


@patch("app.services.finalize_service.create_calendar_event", return_value="gcal-1")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_name_differs_updates_event_name(mock_dep_svc, mock_svc_svc, mock_create_cal):
    """When name differs from event.name, the update payload includes name."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row(name="Team Lunch")
    proposed_time = _make_proposed_time_row()
    write_cal = _make_write_cal_row()

    captured_update = {}

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )

            def capture_update(payload):
                captured_update.update(payload)
                m = MagicMock()
                m.eq.return_value.execute.return_value = MagicMock(
                    data=[{**event_row, "status": "confirmed", "name": payload.get("name", event_row["name"])}]
                )
                return m

            tbl.update.side_effect = capture_update
        elif name == "proposed_times":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=proposed_time
            )
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={
                    "user_id": "coordinator-uuid-1",
                    "profiles": {"email_address": "alice@example.com", "full_name": "Alice", "calendar_accounts": []},
                }
            )
        elif name == "calendar_sources":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[write_cal])
        elif name == "calendar_accounts":
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "cal-1", "credentials": {"access_token": "tok", "refresh_token": "rtok"}}
            )
        elif name == "notifications":
            tbl.insert.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    mock_svc_svc.table.side_effect = make_table

    response = client.post(
        "/api/events/event-uid-1/finalize",
        json={
            "proposed_time_id": "pt-uuid-1",
            "name": "Renamed Lunch",
            "note": "",
            "excluded_user_ids": [],
            "extra_emails": [],
            "location": "",
            "video_call_link": "",
        },
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    assert captured_update.get("name") == "Renamed Lunch"


# ─── GET /api/events/{uid}/finalize/status ────────────────────────────────────

@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_get_finalize_status_coordinator(mock_dep_svc, mock_router_svc):
    """Coordinator can fetch finalize status."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row(
        status="confirmed",
        finalized_start_time_utc="2026-04-10T12:00:00+00:00",
        finalized_end_time_utc="2026-04-10T13:00:00+00:00",
        google_calendar_event_id="gcal-123",
    )

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.get(
        "/api/events/event-uid-1/finalize/status",
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmed"
    assert data["finalized_start_time_utc"] == "2026-04-10T12:00:00+00:00"
    assert data["google_calendar_event_id"] == "gcal-123"


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_get_finalize_status_403_outsider(mock_dep_svc, mock_router_svc):
    """Non-participant gets 403 on finalize/status."""
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

    response = client.get(
        "/api/events/event-uid-1/finalize/status",
        headers=_auth_headers("outsider-uuid"),
    )
    assert response.status_code == 403
