"""Shared Google OAuth and Calendar API helpers used across services."""

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import settings

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def build_calendar_flow() -> Flow:
    """Build a Google OAuth Flow for calendar access."""
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_calendar_redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = settings.google_calendar_redirect_uri
    return flow


def create_calendar_event(credentials: Credentials, calendar_id: str, event_body: dict) -> str:
    """Create a Google Calendar event and return the created event's ID.

    Args:
        credentials: A :class:`google.oauth2.credentials.Credentials` instance.
        calendar_id: The calendar ID to insert the event into (e.g. ``'primary'``).
        event_body: The Google Calendar event resource dict.

    Returns:
        The ``id`` string of the newly created Google Calendar event.

    Raises:
        :class:`googleapiclient.errors.HttpError`: If the API returns an error.
        :exc:`Exception`: For any unexpected error from the API call.
    """
    cal_service = build("calendar", "v3", credentials=credentials)
    created = cal_service.events().insert(calendarId=calendar_id, body=event_body).execute()
    return created["id"]


def credentials_from_dict(creds_data: dict) -> Credentials:
    """Build a Google Credentials object from a stored credentials dict.

    Args:
        creds_data: Dict with keys ``access_token``, ``refresh_token``, and
            optionally ``expiry``.

    Returns:
        A :class:`google.oauth2.credentials.Credentials` instance configured
        with the application's client_id and client_secret from settings.
    """
    return Credentials(
        token=creds_data.get("access_token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
