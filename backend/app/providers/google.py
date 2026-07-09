"""Google Calendar provider.

A thin adapter over the low-level helpers in :mod:`app.utils.google_auth` (OAuth
flow, credential (de)serialisation, event creation, token revocation) plus the
Google Calendar list/read calls. Translates Google-specific failures into the
provider-neutral exceptions defined in :mod:`app.providers.base`.
"""

from __future__ import annotations

import logging
from datetime import datetime

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.providers.base import (
    BusyEvent,
    CalendarProvider,
    ConnectedIdentity,
    EventPayload,
    ProviderAPIError,
    ProviderAuthError,
    ProviderCalendar,
    TokenBundle,
    iso_to_utc,
)
from app.utils.google_auth import (
    build_calendar_flow,
    create_calendar_event,
    credentials_from_dict,
    revoke_google_token,
)

logger = logging.getLogger(__name__)


class GoogleProvider(CalendarProvider):
    name = "google"

    # ─── OAuth ────────────────────────────────────────────────────────────────

    def get_authorization_url(self, state: str) -> str:
        flow = build_calendar_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            state=state,
            include_granted_scopes="false",
        )
        return auth_url

    def exchange_code(self, code: str, state: str) -> ConnectedIdentity:
        # Build the flow with the echoed state via oauthlib's own API rather than
        # poking a private attribute. Cross-user CSRF protection comes from the
        # signed-state check in the router (see app.utils.oauth_state), verified
        # before this is ever called.
        flow = build_calendar_flow(state=state)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        assert isinstance(credentials, Credentials)

        user_info_svc = build("oauth2", "v2", credentials=credentials)
        user_info = user_info_svc.userinfo().get().execute()
        return ConnectedIdentity(
            credentials=_credentials_to_dict(credentials),
            provider_email=user_info["email"],
            provider_account_id=user_info["id"],
        )

    # ─── Calendars ────────────────────────────────────────────────────────────

    def list_calendars(self, tokens: TokenBundle) -> list[ProviderCalendar]:
        creds = credentials_from_dict(tokens.data)
        try:
            service = build("calendar", "v3", credentials=creds)
            calendar_list = service.calendarList().list().execute()
            items = calendar_list.get("items", [])
        except RefreshError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except Exception as exc:
            # Surface the failure instead of returning [] — an empty list is
            # indistinguishable from "no sources / no write calendar" to
            # connect_account, which would silently save a broken account.
            logger.error("Failed to fetch Google calendar list: %s", exc)
            raise ProviderAPIError(str(exc)) from exc
        self._capture_tokens(creds, tokens)
        return [
            ProviderCalendar(
                calendar_id=item["id"],
                name=item.get("summary", item["id"]),
                is_primary=bool(item.get("primary", False)),
                color=item.get("backgroundColor"),
                # accessRole is one of: owner, writer, reader, freeBusyReader.
                # Only owner/writer can have events created on them.
                is_writable=item.get("accessRole") in ("owner", "writer"),
            )
            for item in items
        ]

    def fetch_busy_events(
        self,
        tokens: TokenBundle,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
    ) -> list[BusyEvent]:
        creds = credentials_from_dict(tokens.data)
        try:
            service = build("calendar", "v3", credentials=creds)
            all_items = []
            page_token = None
            while True:
                response = (
                    service.events()
                    .list(
                        calendarId=calendar_id,
                        timeMin=time_min.isoformat(),
                        timeMax=time_max.isoformat(),
                        singleEvents=True,
                        maxResults=250,
                        pageToken=page_token,
                    )
                    .execute()
                )
                all_items.extend(response.get("items", []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except RefreshError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except Exception as exc:
            raise ProviderAPIError(f"Google events.list failed: {exc}") from exc
        self._capture_tokens(creds, tokens)

        busy: list[BusyEvent] = []
        for item in all_items:
            # Skip cancelled instances — absence makes them stale → deleted.
            if item.get("status") == "cancelled":
                continue
            start = item.get("start", {})
            end = item.get("end", {})
            start_time = start.get("dateTime") or start.get("date")
            end_time = end.get("dateTime") or end.get("date")
            if not start_time or not end_time:
                continue
            # Skip all-day events (date strings, not dateTime).
            if "T" not in start_time or "T" not in end_time:
                continue
            busy.append(
                BusyEvent(
                    event_id=item["id"],
                    start_utc=iso_to_utc(start_time),
                    end_utc=iso_to_utc(end_time),
                )
            )
        return busy

    # ─── Events ───────────────────────────────────────────────────────────────

    def create_event(self, tokens: TokenBundle, calendar_id: str, payload: EventPayload) -> str:
        creds = credentials_from_dict(tokens.data)
        body = {
            "summary": payload.summary,
            "description": payload.description,
            "start": {"dateTime": payload.start_utc, "timeZone": "UTC"},
            "end": {"dateTime": payload.end_utc, "timeZone": "UTC"},
            "attendees": [{"email": email} for email in payload.attendee_emails],
        }
        if payload.location:
            body["location"] = payload.location
        try:
            event_id = create_calendar_event(creds, calendar_id, body)
        except RefreshError as exc:
            raise ProviderAuthError(str(exc)) from exc
        self._capture_tokens(creds, tokens)
        return event_id

    # ─── Revocation ───────────────────────────────────────────────────────────

    def revoke(self, tokens: TokenBundle) -> None:
        revoke_google_token((tokens.data or {}).get("refresh_token"))

    # ─── Internals ────────────────────────────────────────────────────────────

    def _capture_tokens(self, creds: Credentials, tokens: TokenBundle) -> None:
        """Persist a refreshed access token back into the bundle. The Google
        client refreshes ``creds`` in place during an API call."""
        if creds.token and creds.token != tokens.data.get("access_token"):
            tokens.update(
                {
                    **tokens.data,
                    "access_token": creds.token,
                    "expiry": creds.expiry.isoformat() if creds.expiry else None,
                }
            )


def _credentials_to_dict(credentials: Credentials) -> dict:
    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }
