"""GoogleProvider unit tests — the Google-specific parsing/creation logic that
used to live inline in sync_service / calendar_service / finalize_service.

The Google client (`build`) and low-level event creation (`create_calendar_event`)
are mocked; no network calls are made.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError

from app.providers.base import (
    EventPayload,
    ProviderAPIError,
    ProviderAuthError,
    TokenBundle,
    iso_to_utc,
)
from app.providers.google import GoogleProvider


def _tokens() -> TokenBundle:
    return TokenBundle({"access_token": "tok", "refresh_token": "rt", "expiry": None})


def _event(event_id: str, start: str, end: str, **extra) -> dict:
    return {"id": event_id, "start": {"dateTime": start}, "end": {"dateTime": end}, **extra}


def _cal_service(pages: list) -> MagicMock:
    """A mock Google calendar service whose events().list().execute() yields the
    given page dicts in sequence."""
    cal = MagicMock()
    cal.events.return_value.list.return_value.execute.side_effect = pages
    return cal


# ─── iso_to_utc ───────────────────────────────────────────────────────────────

def test_iso_to_utc_converts_offset():
    # 09:00 PDT (-07:00) == 16:00 UTC
    dt = datetime.fromisoformat(iso_to_utc("2026-04-09T09:00:00-07:00"))
    assert dt.hour == 16
    assert dt.utcoffset().total_seconds() == 0


def test_iso_to_utc_preserves_utc():
    dt = datetime.fromisoformat(iso_to_utc("2026-04-09T16:00:00+00:00"))
    assert dt.hour == 16
    assert dt.utcoffset().total_seconds() == 0


# ─── fetch_busy_events ────────────────────────────────────────────────────────

@patch("app.providers.google.build")
def test_fetch_follows_page_token(mock_build):
    now = datetime.now(timezone.utc)
    e1 = _event("evt-1", now.isoformat(), (now + timedelta(hours=1)).isoformat())
    e2 = _event("evt-2", (now + timedelta(hours=2)).isoformat(), (now + timedelta(hours=3)).isoformat())
    cal = _cal_service([
        {"items": [e1], "nextPageToken": "page2"},
        {"items": [e2]},
    ])
    mock_build.return_value = cal

    busy = GoogleProvider().fetch_busy_events(_tokens(), "primary", now, now + timedelta(days=90))

    assert [b.event_id for b in busy] == ["evt-1", "evt-2"]
    assert cal.events.return_value.list.call_count == 2
    second_kwargs = cal.events.return_value.list.call_args_list[1].kwargs
    assert second_kwargs.get("pageToken") == "page2"


@patch("app.providers.google.build")
def test_fetch_passes_time_window(mock_build):
    now = datetime.now(timezone.utc)
    cal = _cal_service([{"items": []}])
    mock_build.return_value = cal

    GoogleProvider().fetch_busy_events(_tokens(), "primary", now, now + timedelta(days=90))

    kwargs = cal.events.return_value.list.call_args.kwargs
    parsed_min = datetime.fromisoformat(kwargs["timeMin"])
    parsed_max = datetime.fromisoformat(kwargs["timeMax"])
    assert timedelta(days=89) <= (parsed_max - parsed_min) <= timedelta(days=91)
    assert kwargs["singleEvents"] is True


@patch("app.providers.google.build")
def test_fetch_normalizes_to_utc(mock_build):
    now = datetime.now(timezone.utc)
    cal = _cal_service([{"items": [
        _event("evt-pdt", "2026-04-09T09:00:00-07:00", "2026-04-09T10:00:00-07:00")
    ]}])
    mock_build.return_value = cal

    busy = GoogleProvider().fetch_busy_events(_tokens(), "primary", now, now + timedelta(days=90))

    assert len(busy) == 1
    start = datetime.fromisoformat(busy[0].start_utc)
    assert start.hour == 16
    assert start.utcoffset().total_seconds() == 0


@patch("app.providers.google.build")
def test_fetch_skips_cancelled(mock_build):
    now = datetime.now(timezone.utc)
    active = _event("evt-active", now.isoformat(), (now + timedelta(hours=1)).isoformat())
    cancelled = {
        "id": "evt-cancelled",
        "status": "cancelled",
        "start": {"dateTime": now.isoformat()},
        "end": {"dateTime": (now + timedelta(hours=1)).isoformat()},
    }
    cal = _cal_service([{"items": [active, cancelled]}])
    mock_build.return_value = cal

    busy = GoogleProvider().fetch_busy_events(_tokens(), "primary", now, now + timedelta(days=90))

    ids = [b.event_id for b in busy]
    assert ids == ["evt-active"]


@patch("app.providers.google.build")
def test_fetch_skips_all_day(mock_build):
    now = datetime.now(timezone.utc)
    timed = _event("evt-timed", now.isoformat(), (now + timedelta(hours=1)).isoformat())
    all_day = {"id": "evt-allday", "start": {"date": "2026-04-10"}, "end": {"date": "2026-04-11"}}
    cal = _cal_service([{"items": [timed, all_day]}])
    mock_build.return_value = cal

    busy = GoogleProvider().fetch_busy_events(_tokens(), "primary", now, now + timedelta(days=90))

    assert [b.event_id for b in busy] == ["evt-timed"]


@patch("app.providers.google.build")
def test_fetch_refresh_error_becomes_auth_error(mock_build):
    now = datetime.now(timezone.utc)
    cal = MagicMock()
    cal.events.return_value.list.return_value.execute.side_effect = RefreshError("bad token")
    mock_build.return_value = cal

    with pytest.raises(ProviderAuthError):
        GoogleProvider().fetch_busy_events(_tokens(), "primary", now, now + timedelta(days=90))


@patch("app.providers.google.build")
def test_fetch_other_error_becomes_api_error(mock_build):
    now = datetime.now(timezone.utc)
    cal = MagicMock()
    cal.events.return_value.list.return_value.execute.side_effect = Exception("boom")
    mock_build.return_value = cal

    with pytest.raises(ProviderAPIError):
        GoogleProvider().fetch_busy_events(_tokens(), "primary", now, now + timedelta(days=90))


# ─── create_event ─────────────────────────────────────────────────────────────

@patch("app.providers.google.create_calendar_event")
def test_create_event_builds_google_body(mock_create):
    captured = {}

    def _capture(credentials, calendar_id, body):
        captured["calendar_id"] = calendar_id
        captured["body"] = body
        return "gcal-evt-1"

    mock_create.side_effect = _capture

    payload = EventPayload(
        summary="Team Lunch",
        description="See you there",
        start_utc="2026-04-10T12:00:00+00:00",
        end_utc="2026-04-10T13:00:00+00:00",
        location="123 Main St",
        attendee_emails=["a@example.com", "b@example.com"],
    )
    event_id = GoogleProvider().create_event(_tokens(), "primary", payload)

    assert event_id == "gcal-evt-1"
    body = captured["body"]
    assert body["summary"] == "Team Lunch"
    assert body["description"] == "See you there"
    assert body["start"] == {"dateTime": "2026-04-10T12:00:00+00:00", "timeZone": "UTC"}
    assert body["end"] == {"dateTime": "2026-04-10T13:00:00+00:00", "timeZone": "UTC"}
    assert body["location"] == "123 Main St"
    assert body["attendees"] == [{"email": "a@example.com"}, {"email": "b@example.com"}]


@patch("app.providers.google.create_calendar_event", side_effect=RefreshError("expired"))
def test_create_event_refresh_error_becomes_auth_error(mock_create):
    payload = EventPayload(
        summary="X", description="", start_utc="2026-04-10T12:00:00+00:00",
        end_utc="2026-04-10T13:00:00+00:00",
    )
    with pytest.raises(ProviderAuthError):
        GoogleProvider().create_event(_tokens(), "primary", payload)


# ─── token capture ────────────────────────────────────────────────────────────

def test_capture_tokens_marks_dirty_on_rotation():
    tokens = _tokens()
    creds = MagicMock()
    creds.token = "new-access"
    creds.expiry = datetime(2026, 6, 12, tzinfo=timezone.utc)
    GoogleProvider()._capture_tokens(creds, tokens)
    assert tokens.dirty is True
    assert tokens.data["access_token"] == "new-access"
    # original refresh token preserved
    assert tokens.data["refresh_token"] == "rt"


def test_capture_tokens_noop_when_unchanged():
    tokens = _tokens()
    creds = MagicMock()
    creds.token = "tok"  # same as stored
    GoogleProvider()._capture_tokens(creds, tokens)
    assert tokens.dirty is False


# ─── create_calendar_event (low-level insert) ─────────────────────────────────

@patch("app.utils.google_auth.build")
def test_create_calendar_event_sends_updates_to_all(mock_build):
    """The low-level insert must pass sendUpdates='all' so Google emails invites
    to attendees (its default is to send none)."""
    from app.utils.google_auth import create_calendar_event

    cal = MagicMock()
    cal.events.return_value.insert.return_value.execute.return_value = {"id": "gcal-1"}
    mock_build.return_value = cal

    event_id = create_calendar_event(MagicMock(), "primary", {"summary": "X"})

    assert event_id == "gcal-1"
    kwargs = cal.events.return_value.insert.call_args.kwargs
    assert kwargs.get("sendUpdates") == "all"
    assert kwargs.get("calendarId") == "primary"


# ─── list_calendars writability ──────────────────────────────────────────────

@patch("app.providers.google.build")
def test_list_calendars_maps_access_role_to_writable(mock_build):
    """accessRole owner/writer → writable; reader/freeBusyReader → not writable."""
    cal = MagicMock()
    cal.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [
            {"id": "me@gmail.com", "summary": "Primary", "primary": True, "accessRole": "owner"},
            {"id": "team", "summary": "Team", "accessRole": "writer"},
            {"id": "ro@import.calendar.google.com", "summary": "Imported", "accessRole": "reader"},
            {"id": "fb", "summary": "FreeBusy", "accessRole": "freeBusyReader"},
        ]
    }
    mock_build.return_value = cal

    by_id = {c.calendar_id: c for c in GoogleProvider().list_calendars(_tokens())}

    assert by_id["me@gmail.com"].is_writable is True
    assert by_id["me@gmail.com"].is_primary is True
    assert by_id["team"].is_writable is True
    assert by_id["ro@import.calendar.google.com"].is_writable is False
    assert by_id["fb"].is_writable is False


@patch("app.providers.google.build")
def test_list_calendars_other_error_becomes_api_error(mock_build):
    """A transient/generic failure must raise ProviderAPIError, not return [] —
    an empty list is indistinguishable from 'no calendars' to connect_account and
    would silently save a broken account with no write calendar."""
    cal = MagicMock()
    cal.calendarList.return_value.list.return_value.execute.side_effect = RuntimeError("boom")
    mock_build.return_value = cal

    with pytest.raises(ProviderAPIError):
        GoogleProvider().list_calendars(_tokens())


@patch("app.providers.google.build")
def test_list_calendars_refresh_error_becomes_auth_error(mock_build):
    """Parity/regression: an auth refresh failure still maps to ProviderAuthError."""
    cal = MagicMock()
    cal.calendarList.return_value.list.return_value.execute.side_effect = RefreshError("bad token")
    mock_build.return_value = cal

    with pytest.raises(ProviderAuthError):
        GoogleProvider().list_calendars(_tokens())
