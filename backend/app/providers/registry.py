"""Provider registry — maps ``calendar_accounts.provider`` to an implementation.

Imports are lazy so a Google-only deployment never imports the Microsoft
dependencies (``msal``), and vice versa.
"""

from __future__ import annotations

from app.providers.base import CalendarProvider

SUPPORTED_PROVIDERS = ("google", "microsoft")


def get_provider(name: str) -> CalendarProvider:
    """Return a provider instance for ``name``. Providers are stateless, so a
    fresh instance per call is fine. Raises :class:`ValueError` for unknown
    providers."""
    if name == "google":
        from app.providers.google import GoogleProvider

        return GoogleProvider()
    if name == "microsoft":
        from app.providers.microsoft import MicrosoftProvider

        return MicrosoftProvider()
    raise ValueError(f"Unknown calendar provider: {name!r}")
