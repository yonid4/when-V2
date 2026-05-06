"""Shared Google OAuth and Calendar API helpers used across services."""

import logging
from datetime import datetime, timezone

import httpx
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import settings

logger = logging.getLogger(__name__)


class TokenRevocationError(Exception):
    """Raised when Google refuses to revoke a token for a non-recoverable reason
    (5xx, network timeout, unknown response). The caller must NOT delete the
    stored credentials — the token may still be valid at Google."""

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
        expiry=_parse_expiry(creds_data.get("expiry")),
    )


def _parse_expiry(value):
    """Parse a stored expiry string into a naive UTC datetime.

    The Google library compares expiry against ``datetime.utcnow()`` (naive),
    so any tz-aware value must be normalised to naive UTC before being passed
    to the ``Credentials`` constructor.
    """
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        logger.warning("Could not parse stored credential expiry %r: %s", value, exc)
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def revoke_google_token(refresh_token: str | None) -> None:
    """Revoke a Google OAuth refresh token at the issuer.

    Returns silently if Google confirms the token is revoked or already invalid.
    Raises :class:`TokenRevocationError` if the response is uncertain — in that
    case the caller MUST NOT delete the stored credentials, because the token
    may still be valid at Google and we'd otherwise lose the only way to revoke.

    Args:
        refresh_token: The refresh token to revoke. ``None`` or empty string
            is treated as a no-op (nothing to revoke).
    """
    if not refresh_token:
        return
    try:
        resp = httpx.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": refresh_token},
            headers={"content-type": "application/x-www-form-urlencoded"},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        raise TokenRevocationError(f"Network error contacting Google revoke: {exc}") from exc

    if resp.status_code == 200:
        return
    if resp.status_code == 400 and "invalid_token" in resp.text:
        logger.info("Token already invalid at Google — treating as revoked.")
        return
    raise TokenRevocationError(
        f"Google revoke failed: status={resp.status_code} body={resp.text!r}"
    )


def mark_account_needs_reauth(account_id: str) -> None:
    """Flip needs_reauth=true on a calendar_accounts row.

    Called when Google refuses to refresh the access token (revoked grant,
    expired refresh token, password change, etc).
    """
    from app.utils.supabase import service_client

    try:
        service_client.table("calendar_accounts").update(
            {"needs_reauth": True}
        ).eq("id", account_id).execute()
    except Exception as exc:
        logger.error("Failed to mark account %s as needs_reauth: %s", account_id, exc)
