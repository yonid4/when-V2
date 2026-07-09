"""Signed one-time login codes for the browser session handoff.

After Google login completes on the BACKEND origin, the session JWT must reach
the FRONTEND origin as an HttpOnly cookie. The backend cannot set cookies for
the frontend origin directly (split origins in dev: :8000 vs :3000), so the
callback instead redirects with a short-lived signed code; the frontend
immediately exchanges it via the same-origin API proxy (POST
/auth/session/exchange), whose response sets the ``session`` cookie. This keeps
the 7-day JWT out of URLs, browser history, Referer headers, and JS-readable
storage (see AUDIT_REPORT.md M4/M5).

The code is a stateless HMAC-signed token carrying the ``user_id``, an issue
timestamp, and a random nonce — the same construction as
:mod:`app.utils.oauth_state`, under its own domain prefix.

NOT true single-use: there is no server-side store, so a code can technically
be exchanged more than once within its TTL. The residual exposure is a
60-second code in one redirect URL instead of a 7-day JWT — anyone who can
read the URL that fast could equally have hijacked the login redirect itself.

Crypto (stdlib only):
    message   = "v1.<b64u(user_id)>.<issued_ts>.<b64u(nonce)>"
    signature = b64u(HMAC-SHA256(jwt_secret, b"login-code:" + message))
    token     = message + "." + signature

The signing key is the app's existing JWT secret, but every signed message is
prefixed with the domain tag ``b"login-code:"`` so a login code can never be
mistaken for — or cross-validated against — a real JWT or an oauth-state token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from app.config import settings

_CODE_VERSION = "v1"
# Domain-separation tag mixed into every signed message so these codes can never
# collide with JWTs or oauth-state tokens signed under the same secret.
_DOMAIN_PREFIX = b"login-code:"
_NONCE_BYTES = 16
# The frontend exchanges the code immediately after the redirect lands; 60
# seconds is generous and keeps the not-single-use window tight.
DEFAULT_MAX_AGE_SECONDS = 60
# Tolerate minor clock skew for codes that appear issued slightly in the future.
_CLOCK_SKEW_SECONDS = 60


class LoginCodeError(Exception):
    """Raised when a login code is missing, malformed, tampered with, or
    expired. Callers translate this into a 401 and must NOT leak the message
    to the user."""


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


def create_login_code(user_id: str) -> str:
    """Return a signed login code binding ``user_id`` at the current time."""
    issued = int(time.time())
    nonce = _b64u_encode(secrets.token_bytes(_NONCE_BYTES))
    message = f"{_CODE_VERSION}.{_b64u_encode(user_id.encode('utf-8'))}.{issued}.{nonce}"
    return f"{message}.{_sign(message)}"


def verify_login_code(code: str, *, max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS) -> str:
    """Verify a signed login code and return the embedded ``user_id``.

    Raises :class:`LoginCodeError` if the code is missing, malformed, has a bad
    signature, or is older than ``max_age_seconds``. The signature is checked in
    constant time and BEFORE the payload is decoded, so a tampered code never
    yields a ``user_id``.
    """
    if not code or not isinstance(code, str):
        raise LoginCodeError("missing code")

    parts = code.split(".")
    if len(parts) != 5:
        raise LoginCodeError("malformed code")

    version, user_b64, issued_str, nonce, signature = parts
    if version != _CODE_VERSION:
        raise LoginCodeError("unsupported code version")

    message = f"{version}.{user_b64}.{issued_str}.{nonce}"
    if not hmac.compare_digest(_sign(message), signature):
        raise LoginCodeError("bad signature")

    try:
        issued = int(issued_str)
    except ValueError as exc:
        raise LoginCodeError("bad timestamp") from exc

    age = int(time.time()) - issued
    if age > max_age_seconds or age < -_CLOCK_SKEW_SECONDS:
        raise LoginCodeError("expired code")

    try:
        user_id = _b64u_decode(user_b64).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise LoginCodeError("bad payload") from exc
    if not user_id:
        raise LoginCodeError("empty user id")

    return user_id
