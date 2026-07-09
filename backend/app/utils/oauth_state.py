"""Signed OAuth ``state`` tokens for the calendar-connect flow.

The calendar OAuth callbacks are unauthenticated (the provider redirects the
browser there with no Authorization header), so the only thing tying a callback
back to the initiating user is the ``state`` value we round-trip through the
provider. A raw ``user_id`` there is forgeable: an attacker could complete OAuth
with their own account while setting ``state=<victim_id>`` and attach their
calendar to the victim. See AUDIT_REPORT.md C1.

To close that, ``state`` is a short-lived HMAC-signed token carrying the
``user_id``, an issue timestamp, and a random nonce. The callback verifies the
signature and freshness before trusting the ``user_id``.

Crypto (stdlib only):
    message   = "v1.<b64u(user_id)>.<issued_ts>.<b64u(nonce)>"
    signature = b64u(HMAC-SHA256(jwt_secret, b"oauth-state:" + message))
    token     = message + "." + signature

The signing key is the app's existing JWT secret, but every signed message is
prefixed with the domain tag ``b"oauth-state:"`` so a state token can never be
mistaken for — or cross-validated against — a real JWT.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from app.config import settings

_STATE_VERSION = "v1"
# Domain-separation tag mixed into every signed message so these tokens can never
# collide with JWTs signed under the same secret.
_DOMAIN_PREFIX = b"oauth-state:"
_NONCE_BYTES = 16
# Callbacks normally arrive within seconds of consent; 10 minutes is generous.
DEFAULT_MAX_AGE_SECONDS = 600
# Tolerate minor clock skew for tokens that appear issued slightly in the future.
_CLOCK_SKEW_SECONDS = 60


class OAuthStateError(Exception):
    """Raised when an OAuth ``state`` token is missing, malformed, tampered with,
    or expired. Callers translate this into the redirect-error convention and
    must NOT leak the message to the user."""


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(message: str) -> str:
    mac = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        _DOMAIN_PREFIX + message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64u_encode(mac)


def create_oauth_state(user_id: str) -> str:
    """Return a signed ``state`` token binding ``user_id`` at the current time."""
    issued = int(time.time())
    nonce = _b64u_encode(secrets.token_bytes(_NONCE_BYTES))
    message = f"{_STATE_VERSION}.{_b64u_encode(user_id.encode('utf-8'))}.{issued}.{nonce}"
    return f"{message}.{_sign(message)}"


def verify_oauth_state(token: str, *, max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS) -> str:
    """Verify a signed ``state`` token and return the embedded ``user_id``.

    Raises :class:`OAuthStateError` if the token is missing, malformed, has a bad
    signature, or is older than ``max_age_seconds``. The signature is checked in
    constant time and BEFORE the payload is decoded, so a tampered token never
    yields a ``user_id``.
    """
    if not token or not isinstance(token, str):
        raise OAuthStateError("missing state")

    parts = token.split(".")
    if len(parts) != 5:
        raise OAuthStateError("malformed state")

    version, user_b64, issued_str, nonce, signature = parts
    if version != _STATE_VERSION:
        raise OAuthStateError("unsupported state version")

    message = f"{version}.{user_b64}.{issued_str}.{nonce}"
    if not hmac.compare_digest(_sign(message), signature):
        raise OAuthStateError("bad signature")

    try:
        issued = int(issued_str)
    except ValueError as exc:
        raise OAuthStateError("bad timestamp") from exc

    age = int(time.time()) - issued
    if age > max_age_seconds or age < -_CLOCK_SKEW_SECONDS:
        raise OAuthStateError("expired state")

    try:
        user_id = _b64u_decode(user_b64).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise OAuthStateError("bad payload") from exc
    if not user_id:
        raise OAuthStateError("empty user id")

    return user_id
