"""Provider-agnostic calendar interfaces and shared types.

A :class:`CalendarProvider` encapsulates everything provider-specific: OAuth,
listing calendars, reading busy events, and creating events. Services dispatch
on ``calendar_accounts.provider`` via :mod:`app.providers.registry`, so adding a
provider never touches the sync/finalize/connect flows.

Token persistence contract
--------------------------
Methods that make authenticated API calls receive a :class:`TokenBundle`. If the
provider refreshes/rotates credentials during the call it updates the bundle via
:meth:`TokenBundle.update` (which also flips ``dirty``). Callers MUST persist
``bundle.data`` back to ``calendar_accounts.credentials`` whenever ``dirty`` is
true. Google rotates only the access token; Microsoft rotates the *refresh*
token on every refresh — persisting the whole dict handles both correctly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ─── Exceptions ──────────────────────────────────────────────────────────────

class ProviderError(Exception):
    """Base class for all provider errors."""


class ProviderAuthError(ProviderError):
    """Credentials are invalid/expired and cannot be refreshed.

    The caller should mark the account ``needs_reauth``. Maps from Google's
    ``RefreshError`` and Microsoft's ``invalid_grant`` token response.
    """


class ProviderAPIError(ProviderError):
    """A non-auth API failure (5xx, network error, unexpected response)."""


class TokenRevocationError(ProviderError):
    """The provider refused to revoke a token for an uncertain reason (5xx,
    network timeout, unknown response). The caller MUST NOT delete the stored
    credentials — the token may still be valid at the issuer."""


# ─── Value types ─────────────────────────────────────────────────────────────

@dataclass
class TokenBundle:
    """Mutable wrapper around a provider's stored credentials dict.

    Providers replace :attr:`data` via :meth:`update` when tokens rotate; callers
    persist :attr:`data` when :attr:`dirty` is true.
    """

    data: dict
    dirty: bool = False

    def update(self, new_data: dict) -> None:
        self.data = new_data
        self.dirty = True


@dataclass
class ConnectedIdentity:
    """Result of exchanging an OAuth code: the stored credentials plus the
    provider-side identity used to key the ``calendar_accounts`` row."""

    credentials: dict
    provider_email: str
    provider_account_id: str


@dataclass
class ProviderCalendar:
    """One calendar within a connected account."""

    calendar_id: str
    name: str
    is_primary: bool
    color: str | None = None
    # Whether the connected user can create events on this calendar. Read-only
    # calendars (subscribed/imported/holiday or shared-as-reader) are still valid
    # busy sources but must never be chosen as the write calendar.
    is_writable: bool = True


@dataclass
class BusyEvent:
    """A single timed busy block, already normalised to UTC ISO strings.

    Providers are responsible for expanding recurring events, skipping cancelled
    and all-day events, and converting times to UTC, so the sync layer stays
    provider-agnostic.
    """

    event_id: str
    start_utc: str
    end_utc: str


@dataclass
class EventPayload:
    """A provider-agnostic event to create. Each provider translates this into
    its own request body."""

    summary: str
    description: str
    start_utc: str
    end_utc: str
    location: str = ""
    attendee_emails: list[str] = field(default_factory=list)


# ─── Shared helpers ──────────────────────────────────────────────────────────

def iso_to_utc(dt_str: str) -> str:
    """Parse a datetime string (possibly with a tz offset) and return a UTC ISO
    string. Used by providers to normalise event times before storage."""
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


# ─── Interface ───────────────────────────────────────────────────────────────

class CalendarProvider(ABC):
    """Interface implemented by each calendar provider (Google, Microsoft)."""

    name: str

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """Return the OAuth consent URL. ``state`` carries the user id back to
        the callback."""

    @abstractmethod
    def exchange_code(self, code: str, state: str) -> ConnectedIdentity:
        """Exchange an authorization ``code`` for credentials and identity."""

    @abstractmethod
    def list_calendars(self, tokens: TokenBundle) -> list[ProviderCalendar]:
        """List the calendars available in the connected account."""

    @abstractmethod
    def fetch_busy_events(
        self,
        tokens: TokenBundle,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
    ) -> list[BusyEvent]:
        """Return timed busy blocks in ``[time_min, time_max]`` for one calendar.

        Raises :class:`ProviderAuthError` if credentials cannot be refreshed.
        """

    @abstractmethod
    def create_event(self, tokens: TokenBundle, calendar_id: str, payload: EventPayload) -> str:
        """Create an event and return the provider event id.

        Raises :class:`ProviderAuthError` if credentials cannot be refreshed.
        """

    @abstractmethod
    def revoke(self, tokens: TokenBundle) -> None:
        """Best-effort revoke the stored credentials at the issuer.

        Raises :class:`TokenRevocationError` if revocation is uncertain (caller
        must keep the stored credentials). Providers without a revoke endpoint
        (e.g. Microsoft) treat this as a no-op.
        """
