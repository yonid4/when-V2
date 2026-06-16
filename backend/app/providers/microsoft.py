"""Microsoft (Outlook) calendar provider via Microsoft Graph.

OAuth/token handling uses ``msal`` against our own JSONB credential storage
(stateless — no MSAL token cache); calendar REST calls use ``httpx`` directly.

Important: Microsoft rotates the **refresh token** on every refresh, so the
whole credentials dict must be persisted after any refresh. This provider writes
rotated tokens back into the :class:`TokenBundle` (setting ``dirty``); callers
persist them. See :mod:`app.providers.base`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
import msal

from app.config import settings
from app.providers.base import (
    BusyEvent,
    CalendarProvider,
    ConnectedIdentity,
    EventPayload,
    ProviderAPIError,
    ProviderAuthError,
    ProviderCalendar,
    TokenBundle,
)

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
AUTHORITY = "https://login.microsoftonline.com/common"
# Resource scopes only — MSAL adds openid/profile/offline_access automatically.
GRAPH_SCOPES = ["User.Read", "Calendars.ReadWrite"]
_HTTP_TIMEOUT = 30.0


class MicrosoftProvider(CalendarProvider):
    name = "microsoft"

    # ─── OAuth ────────────────────────────────────────────────────────────────

    def get_authorization_url(self, state: str) -> str:
        return self._app().get_authorization_request_url(
            GRAPH_SCOPES,
            state=state,
            redirect_uri=settings.microsoft_calendar_redirect_uri,
        )

    def exchange_code(self, code: str, state: str) -> ConnectedIdentity:
        result = self._app().acquire_token_by_authorization_code(
            code,
            scopes=GRAPH_SCOPES,
            redirect_uri=settings.microsoft_calendar_redirect_uri,
        )
        if "access_token" not in result:
            raise ProviderAPIError(
                result.get("error_description") or result.get("error") or "token exchange failed"
            )
        tokens = TokenBundle(
            {
                "access_token": result["access_token"],
                "refresh_token": result.get("refresh_token"),
                "expiry": _expiry_from_result(result),
            }
        )
        me = self._graph_get_one(tokens, "/me")
        return ConnectedIdentity(
            credentials=tokens.data,
            provider_email=me.get("mail") or me.get("userPrincipalName"),
            provider_account_id=me["id"],
        )

    # ─── Calendars ────────────────────────────────────────────────────────────

    def list_calendars(self, tokens: TokenBundle) -> list[ProviderCalendar]:
        items = self._graph_get_all(
            tokens,
            "/me/calendars",
            params={"$select": "id,name,isDefaultCalendar,hexColor,canEdit"},
        )
        return [
            ProviderCalendar(
                calendar_id=item["id"],
                name=item.get("name") or item["id"],
                is_primary=bool(item.get("isDefaultCalendar")),
                color=_hex_color(item.get("hexColor")),
                is_writable=bool(item.get("canEdit")),
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
        params = {
            "startDateTime": time_min.astimezone(timezone.utc).isoformat(),
            "endDateTime": time_max.astimezone(timezone.utc).isoformat(),
            "$select": "id,start,end,isAllDay",
            "$top": "250",
        }
        # calendarView expands recurring instances; Prefer UTC so times need no
        # offset interpretation. Cancelled instances are simply absent → stale.
        items = self._graph_get_all(
            tokens,
            f"/me/calendars/{calendar_id}/calendarView",
            params=params,
            headers={"Prefer": 'outlook.timezone="UTC"'},
        )

        busy: list[BusyEvent] = []
        for item in items:
            if item.get("isAllDay"):
                continue
            start = (item.get("start") or {}).get("dateTime")
            end = (item.get("end") or {}).get("dateTime")
            if not start or not end:
                continue
            busy.append(
                BusyEvent(
                    event_id=item["id"],
                    start_utc=_graph_dt_to_utc(start),
                    end_utc=_graph_dt_to_utc(end),
                )
            )
        return busy

    # ─── Events ───────────────────────────────────────────────────────────────

    def create_event(self, tokens: TokenBundle, calendar_id: str, payload: EventPayload) -> str:
        token = self._ensure_access_token(tokens)
        body = {
            "subject": payload.summary,
            "body": {"contentType": "text", "content": payload.description or ""},
            "start": {"dateTime": _to_graph_naive(payload.start_utc), "timeZone": "UTC"},
            "end": {"dateTime": _to_graph_naive(payload.end_utc), "timeZone": "UTC"},
            "attendees": [
                {"emailAddress": {"address": email}, "type": "required"}
                for email in payload.attendee_emails
            ],
        }
        if payload.location:
            body["location"] = {"displayName": payload.location}

        resp = httpx.post(
            f"{GRAPH_BASE}/me/calendars/{calendar_id}/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code == 401:
            raise ProviderAuthError("Graph returned 401 creating event")
        if resp.status_code >= 400:
            raise ProviderAPIError(f"Graph create event failed: {resp.status_code} {resp.text}")
        return resp.json()["id"]

    # ─── Revocation ───────────────────────────────────────────────────────────

    def revoke(self, tokens: TokenBundle) -> None:
        # Microsoft identity platform has no token-revocation endpoint for our
        # use case; disconnecting simply drops the stored credentials.
        return None

    # ─── Internals ────────────────────────────────────────────────────────────

    def _app(self) -> msal.ConfidentialClientApplication:
        return msal.ConfidentialClientApplication(
            client_id=settings.microsoft_client_id,
            authority=AUTHORITY,
            client_credential=settings.microsoft_client_secret,
        )

    def _ensure_access_token(self, tokens: TokenBundle) -> str:
        """Return a valid access token, refreshing (and rotating the refresh
        token) when the current one is missing or about to expire."""
        data = tokens.data
        expiry = _parse_iso(data.get("expiry"))
        if (
            data.get("access_token")
            and expiry is not None
            and expiry > datetime.now(timezone.utc) + timedelta(seconds=60)
        ):
            return data["access_token"]

        refresh_token = data.get("refresh_token")
        if not refresh_token:
            raise ProviderAuthError("No Microsoft refresh token available")

        result = self._app().acquire_token_by_refresh_token(refresh_token, scopes=GRAPH_SCOPES)
        if "access_token" not in result:
            raise ProviderAuthError(
                result.get("error_description") or result.get("error") or "token refresh failed"
            )
        tokens.update(
            {
                "access_token": result["access_token"],
                # Microsoft rotates the refresh token; fall back to the old one
                # only if (unexpectedly) none is returned.
                "refresh_token": result.get("refresh_token", refresh_token),
                "expiry": _expiry_from_result(result),
            }
        )
        return tokens.data["access_token"]

    def _graph_get_one(self, tokens: TokenBundle, path: str) -> dict:
        token = self._ensure_access_token(tokens)
        resp = httpx.get(
            f"{GRAPH_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code == 401:
            raise ProviderAuthError(f"Graph returned 401 for {path}")
        if resp.status_code >= 400:
            raise ProviderAPIError(f"Graph GET {path} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def _graph_get_all(
        self,
        tokens: TokenBundle,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> list[dict]:
        token = self._ensure_access_token(tokens)
        request_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            request_headers.update(headers)

        url: str | None = f"{GRAPH_BASE}{path}"
        first = True
        items: list[dict] = []
        while url:
            # @odata.nextLink already carries the query params, so only send
            # params on the first request.
            resp = httpx.get(
                url,
                headers=request_headers,
                params=params if first else None,
                timeout=_HTTP_TIMEOUT,
            )
            first = False
            if resp.status_code == 401:
                raise ProviderAuthError(f"Graph returned 401 for {path}")
            if resp.status_code >= 400:
                raise ProviderAPIError(f"Graph GET {path} failed: {resp.status_code} {resp.text}")
            body = resp.json()
            items.extend(body.get("value", []))
            url = body.get("@odata.nextLink")
        return items


# ─── Module helpers ──────────────────────────────────────────────────────────

def _expiry_from_result(result: dict) -> str | None:
    expires_in = result.get("expires_in")
    if expires_in is None:
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _graph_dt_to_utc(dt_str: str) -> str:
    """Convert a Graph dateTime (UTC via the Prefer header, no offset, up to 7
    fractional digits) into a UTC ISO string."""
    s = dt_str.rstrip("Z")
    if "." in s:
        head, frac = s.split(".", 1)
        s = f"{head}.{frac[:6]}"  # Python's fromisoformat caps microseconds at 6 digits
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _to_graph_naive(iso_str: str) -> str:
    """Convert a stored UTC ISO string (with offset) into the naive UTC form
    Graph expects alongside ``timeZone: "UTC"``."""
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat()


def _hex_color(value) -> str | None:
    """Graph returns hexColor as '' or 'auto' when unset; pass through only real
    hex values."""
    if isinstance(value, str) and value.startswith("#"):
        return value
    return None
