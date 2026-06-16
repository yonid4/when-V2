"""Calendar provider abstraction (Google, Microsoft).

Services dispatch on ``calendar_accounts.provider`` via :func:`get_provider`
rather than hard-coding any single provider.
"""

from app.providers.base import (
    BusyEvent,
    CalendarProvider,
    ConnectedIdentity,
    EventPayload,
    ProviderAPIError,
    ProviderAuthError,
    ProviderCalendar,
    ProviderError,
    TokenBundle,
    TokenRevocationError,
    iso_to_utc,
)
from app.providers.registry import SUPPORTED_PROVIDERS, get_provider

__all__ = [
    "BusyEvent",
    "CalendarProvider",
    "ConnectedIdentity",
    "EventPayload",
    "ProviderAPIError",
    "ProviderAuthError",
    "ProviderCalendar",
    "ProviderError",
    "TokenBundle",
    "TokenRevocationError",
    "iso_to_utc",
    "get_provider",
    "SUPPORTED_PROVIDERS",
]
