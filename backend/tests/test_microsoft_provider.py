"""MicrosoftProvider unit tests — Graph access via mocked ``msal`` and ``httpx``.

No network calls are made: ``app.providers.microsoft.msal`` and
``app.providers.microsoft.httpx`` are patched.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.providers.base import (
    EventPayload,
    ProviderAPIError,
    ProviderAuthError,
    TokenBundle,
)
from app.providers.microsoft import MicrosoftProvider


def _resp(status: int = 200, json_body: dict | None = None, text: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_body if json_body is not None else {}
    r.text = text
    return r


def _valid_tokens() -> TokenBundle:
    """Tokens with a future expiry, so _ensure_access_token does not refresh."""
    return TokenBundle(
        {
            "access_token": "at",
            "refresh_token": "rt",
            "expiry": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }
    )


def _expired_tokens() -> TokenBundle:
    return TokenBundle(
        {
            "access_token": "at-old",
            "refresh_token": "rt-old",
            "expiry": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        }
    )


# ─── exchange_code ────────────────────────────────────────────────────────────

@patch("app.providers.microsoft.httpx")
@patch("app.providers.microsoft.msal")
def test_exchange_code_returns_identity(mock_msal, mock_httpx):
    app = mock_msal.ConfidentialClientApplication.return_value
    app.acquire_token_by_authorization_code.return_value = {
        "access_token": "new-at",
        "refresh_token": "new-rt",
        "expires_in": 3600,
    }
    mock_httpx.get.return_value = _resp(json_body={"id": "ms-id-1", "mail": "user@outlook.com"})

    identity = MicrosoftProvider().exchange_code("the-code", "state-user-1")

    assert identity.provider_account_id == "ms-id-1"
    assert identity.provider_email == "user@outlook.com"
    assert identity.credentials["access_token"] == "new-at"
    assert identity.credentials["refresh_token"] == "new-rt"
    assert identity.credentials["expiry"] is not None


@patch("app.providers.microsoft.httpx")
@patch("app.providers.microsoft.msal")
def test_exchange_code_falls_back_to_upn(mock_msal, mock_httpx):
    app = mock_msal.ConfidentialClientApplication.return_value
    app.acquire_token_by_authorization_code.return_value = {
        "access_token": "new-at",
        "refresh_token": "new-rt",
        "expires_in": 3600,
    }
    # No 'mail' → use userPrincipalName.
    mock_httpx.get.return_value = _resp(json_body={"id": "ms-id-2", "userPrincipalName": "user@contoso.com"})

    identity = MicrosoftProvider().exchange_code("code", "state")
    assert identity.provider_email == "user@contoso.com"


@patch("app.providers.microsoft.msal")
def test_exchange_code_error_raises(mock_msal):
    app = mock_msal.ConfidentialClientApplication.return_value
    app.acquire_token_by_authorization_code.return_value = {
        "error": "invalid_grant",
        "error_description": "bad code",
    }
    with pytest.raises(ProviderAPIError):
        MicrosoftProvider().exchange_code("bad-code", "state")


# ─── list_calendars ───────────────────────────────────────────────────────────

@patch("app.providers.microsoft.httpx")
@patch("app.providers.microsoft.msal")
def test_list_calendars_maps_default_and_color(mock_msal, mock_httpx):
    mock_httpx.get.return_value = _resp(json_body={
        "value": [
            {"id": "cal-A", "name": "Calendar", "isDefaultCalendar": True, "hexColor": "#0078D4", "canEdit": True},
            {"id": "cal-B", "name": "Work", "isDefaultCalendar": False, "hexColor": "auto", "canEdit": True},
            {"id": "cal-RO", "name": "Subscribed", "isDefaultCalendar": False, "hexColor": "auto", "canEdit": False},
        ]
    })

    cals = MicrosoftProvider().list_calendars(_valid_tokens())

    assert len(cals) == 3
    primary = next(c for c in cals if c.calendar_id == "cal-A")
    other = next(c for c in cals if c.calendar_id == "cal-B")
    readonly = next(c for c in cals if c.calendar_id == "cal-RO")
    assert primary.is_primary is True
    assert primary.color == "#0078D4"
    assert primary.is_writable is True
    assert other.is_primary is False
    assert other.color is None  # 'auto' is not a real hex value
    assert other.is_writable is True
    assert readonly.is_writable is False  # canEdit False → read-only


# ─── fetch_busy_events ────────────────────────────────────────────────────────

@patch("app.providers.microsoft.httpx")
@patch("app.providers.microsoft.msal")
def test_fetch_busy_events_paginates_and_skips_all_day(mock_msal, mock_httpx):
    page1 = _resp(json_body={
        "value": [
            {"id": "e1", "start": {"dateTime": "2026-04-10T12:00:00.0000000"},
             "end": {"dateTime": "2026-04-10T13:00:00.0000000"}, "isAllDay": False},
            {"id": "e-allday", "start": {"dateTime": "2026-04-11T00:00:00.0000000"},
             "end": {"dateTime": "2026-04-12T00:00:00.0000000"}, "isAllDay": True},
        ],
        "@odata.nextLink": "https://graph.microsoft.com/v1.0/next-page",
    })
    page2 = _resp(json_body={
        "value": [
            {"id": "e2", "start": {"dateTime": "2026-04-12T09:00:00.0000000"},
             "end": {"dateTime": "2026-04-12T10:00:00.0000000"}, "isAllDay": False},
        ],
    })
    mock_httpx.get.side_effect = [page1, page2]

    now = datetime.now(timezone.utc)
    busy = MicrosoftProvider().fetch_busy_events(_valid_tokens(), "cal-A", now, now + timedelta(days=90))

    assert [b.event_id for b in busy] == ["e1", "e2"]
    assert mock_httpx.get.call_count == 2
    # Prefer header requested UTC.
    first_headers = mock_httpx.get.call_args_list[0].kwargs["headers"]
    assert first_headers["Prefer"] == 'outlook.timezone="UTC"'


@patch("app.providers.microsoft.httpx")
@patch("app.providers.microsoft.msal")
def test_fetch_busy_events_normalizes_to_utc(mock_msal, mock_httpx):
    mock_httpx.get.return_value = _resp(json_body={
        "value": [
            {"id": "e1", "start": {"dateTime": "2026-04-10T12:30:00.0000000"},
             "end": {"dateTime": "2026-04-10T13:30:00.0000000"}, "isAllDay": False},
        ]
    })

    now = datetime.now(timezone.utc)
    busy = MicrosoftProvider().fetch_busy_events(_valid_tokens(), "cal-A", now, now + timedelta(days=90))

    start = datetime.fromisoformat(busy[0].start_utc)
    assert start.hour == 12
    assert start.minute == 30
    assert start.utcoffset().total_seconds() == 0


# ─── create_event ─────────────────────────────────────────────────────────────

@patch("app.providers.microsoft.httpx")
@patch("app.providers.microsoft.msal")
def test_create_event_builds_graph_body(mock_msal, mock_httpx):
    mock_httpx.post.return_value = _resp(json_body={"id": "ms-evt-1"})

    payload = EventPayload(
        summary="Team Lunch",
        description="See you there",
        start_utc="2026-04-10T12:00:00+00:00",
        end_utc="2026-04-10T13:00:00+00:00",
        location="123 Main St",
        attendee_emails=["a@example.com", "b@example.com"],
    )
    event_id = MicrosoftProvider().create_event(_valid_tokens(), "cal-A", payload)

    assert event_id == "ms-evt-1"
    body = mock_httpx.post.call_args.kwargs["json"]
    assert body["subject"] == "Team Lunch"
    assert body["body"] == {"contentType": "text", "content": "See you there"}
    # Graph wants naive UTC alongside timeZone:"UTC" (no offset).
    assert body["start"] == {"dateTime": "2026-04-10T12:00:00", "timeZone": "UTC"}
    assert body["end"] == {"dateTime": "2026-04-10T13:00:00", "timeZone": "UTC"}
    assert body["location"] == {"displayName": "123 Main St"}
    assert body["attendees"] == [
        {"emailAddress": {"address": "a@example.com"}, "type": "required"},
        {"emailAddress": {"address": "b@example.com"}, "type": "required"},
    ]


@patch("app.providers.microsoft.httpx")
@patch("app.providers.microsoft.msal")
def test_create_event_api_error(mock_msal, mock_httpx):
    mock_httpx.post.return_value = _resp(status=500, text="server error")
    payload = EventPayload(
        summary="X", description="", start_utc="2026-04-10T12:00:00+00:00",
        end_utc="2026-04-10T13:00:00+00:00",
    )
    with pytest.raises(ProviderAPIError):
        MicrosoftProvider().create_event(_valid_tokens(), "cal-A", payload)


# ─── token refresh / rotation ─────────────────────────────────────────────────

@patch("app.providers.microsoft.httpx")
@patch("app.providers.microsoft.msal")
def test_refresh_rotates_refresh_token_and_marks_dirty(mock_msal, mock_httpx):
    """When the access token is expired, a refresh runs and the NEW refresh token
    is stored (Microsoft rotates it) with dirty=True so callers persist it."""
    app = mock_msal.ConfidentialClientApplication.return_value
    app.acquire_token_by_refresh_token.return_value = {
        "access_token": "at-new",
        "refresh_token": "rt-new",  # rotated
        "expires_in": 3600,
    }
    mock_httpx.post.return_value = _resp(json_body={"id": "ms-evt-2"})

    tokens = _expired_tokens()
    payload = EventPayload(
        summary="X", description="", start_utc="2026-04-10T12:00:00+00:00",
        end_utc="2026-04-10T13:00:00+00:00",
    )
    MicrosoftProvider().create_event(tokens, "cal-A", payload)

    app.acquire_token_by_refresh_token.assert_called_once()
    assert tokens.dirty is True
    assert tokens.data["access_token"] == "at-new"
    assert tokens.data["refresh_token"] == "rt-new"
    # The Bearer header used the refreshed access token.
    assert mock_httpx.post.call_args.kwargs["headers"]["Authorization"] == "Bearer at-new"


@patch("app.providers.microsoft.httpx")
@patch("app.providers.microsoft.msal")
def test_valid_token_skips_refresh(mock_msal, mock_httpx):
    app = mock_msal.ConfidentialClientApplication.return_value
    mock_httpx.post.return_value = _resp(json_body={"id": "ms-evt-3"})

    tokens = _valid_tokens()
    payload = EventPayload(
        summary="X", description="", start_utc="2026-04-10T12:00:00+00:00",
        end_utc="2026-04-10T13:00:00+00:00",
    )
    MicrosoftProvider().create_event(tokens, "cal-A", payload)

    app.acquire_token_by_refresh_token.assert_not_called()
    assert tokens.dirty is False


@patch("app.providers.microsoft.msal")
def test_refresh_invalid_grant_raises_auth_error(mock_msal):
    app = mock_msal.ConfidentialClientApplication.return_value
    app.acquire_token_by_refresh_token.return_value = {
        "error": "invalid_grant",
        "error_description": "refresh token expired",
    }

    tokens = _expired_tokens()
    payload = EventPayload(
        summary="X", description="", start_utc="2026-04-10T12:00:00+00:00",
        end_utc="2026-04-10T13:00:00+00:00",
    )
    with pytest.raises(ProviderAuthError):
        MicrosoftProvider().create_event(tokens, "cal-A", payload)


@patch("app.providers.microsoft.msal")
def test_refresh_without_refresh_token_raises_auth_error(mock_msal):
    tokens = TokenBundle({"access_token": "at", "refresh_token": None, "expiry": None})
    payload = EventPayload(
        summary="X", description="", start_utc="2026-04-10T12:00:00+00:00",
        end_utc="2026-04-10T13:00:00+00:00",
    )
    with pytest.raises(ProviderAuthError):
        MicrosoftProvider().create_event(tokens, "cal-A", payload)


def test_revoke_is_noop():
    # No exception, no network — Microsoft has no revoke endpoint for us.
    MicrosoftProvider().revoke(TokenBundle({"refresh_token": "rt"}))
