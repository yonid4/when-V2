import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from jose import jwt

from app.config import settings
from app.models.user import User
from app.utils.email import normalize_email
from app.utils.login_code import create_login_code
from app.utils.supabase import service_client

logger = logging.getLogger(__name__)

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def build_oauth_flow(state: str | None = None) -> Flow:
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    # ``state`` is threaded through oauthlib's own API (OAuth2Session state) so we
    # never reach into private flow attributes — mirrors build_calendar_flow.
    flow = Flow.from_client_config(client_config, scopes=SCOPES, state=state)
    flow.redirect_uri = settings.google_redirect_uri
    return flow


def get_authorization_url(state: str) -> str:
    """Build the Google login consent URL, embedding ``state`` for CSRF binding.

    The caller (auth router) generates a random ``state``, pins it to the browser
    in an HttpOnly cookie on the redirect response, and re-checks it in the
    callback before the code is exchanged. See app/routers/auth.py.
    """
    flow = build_oauth_flow()
    # include_granted_scopes=false (matching the calendar flow): login credentials
    # are used only to fetch userinfo and are never persisted, so the incremental-
    # auth scope union buys login nothing — and with it off, Google echoes exactly
    # the requested scopes, so oauthlib's strict scope validation passes.
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="false",
        prompt="consent",
        state=state,
    )
    return auth_url


def exchange_code_and_upsert_user(code: str, state: str) -> str:
    """Exchange OAuth code, upsert profile, check pending invites, and return a
    short-lived signed login code (NOT the session JWT).

    The code is handed to the frontend via the post-login redirect and traded
    for the real 7-day JWT at POST /auth/session/exchange, which delivers it as
    an HttpOnly cookie. Redirecting with the JWT itself would leak a 7-day
    credential into browser history, Referer headers, and logs (M4).

    ``state`` is threaded through oauthlib's own API rather than a private
    attribute. Login CSRF protection is enforced upstream in the router, which
    compares the returned ``state`` against the ``oauth_login_state`` cookie set
    in the initiating browser before this is ever called.

    oauthlib's scope validation is deliberately left enabled: the login URL
    requests include_granted_scopes=false, so Google returns exactly the
    requested scopes and any mismatch here is genuinely suspicious.
    """
    flow = build_oauth_flow(state=state)
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        logger.error("fetch_token failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="oauth_exchange_failed",
        )

    credentials = flow.credentials
    assert isinstance(credentials, Credentials)
    user_info = _fetch_google_user_info(credentials)

    profile = _upsert_profile(user_info, credentials)
    _process_pending_invitations(profile["id"], normalize_email(user_info["email"]))

    return create_login_code(profile["id"])


def create_session_for_user(user_id: str) -> tuple[str, User]:
    """Mint the 7-day session JWT for ``user_id`` and return it with the user.

    Called by the session-exchange endpoint after the login code's signature
    and freshness have been verified. The router sets the JWT as the HttpOnly
    ``session`` cookie and returns only the User payload in the body.
    """
    result = service_client.table("profiles").select("*").eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    token = _create_jwt(user_id=user_id, email=result.data["email_address"])
    return token, User(**result.data)


# Realtime tokens are handed to JavaScript (supabase-js needs a readable JWT to
# join channels as `authenticated`), so they must be short-lived: an XSS that
# steals one gets 1 hour, not 7 days.
REALTIME_TOKEN_EXPIRE_MINUTES = 60


def create_realtime_token(user: User) -> str:
    """Mint a short-lived JWT (same claims as the session JWT, shorter exp)
    for the Supabase realtime client."""
    return _create_jwt(
        user_id=user.id,
        email=user.email_address,
        expires_minutes=REALTIME_TOKEN_EXPIRE_MINUTES,
    )


def _fetch_google_user_info(credentials: Credentials) -> dict:
    service = build("oauth2", "v2", credentials=credentials)
    return service.userinfo().get().execute()


def _upsert_profile(user_info: dict, credentials: Credentials) -> dict:
    # Ensure an auth.users row exists — profiles.id is a FK to auth.users.id
    try:
        auth_user = service_client.auth.admin.create_user({
            "email": user_info["email"],
            "email_confirm": True,
            "user_metadata": {
                "full_name": user_info.get("name"),
                "avatar_url": user_info.get("picture"),
            },
        })
        profile_id = auth_user.user.id
    except Exception as e:
        logger.error("create_user failed: %s", e)
        # User already exists in auth.users — resolve their id through our own
        # profiles table instead of paging auth.admin.list_users (H7: the old
        # listing skipped users at indices ~51–1000 and was O(N) per login;
        # gotrue 2.x has no admin get-user-by-email).
        # profiles.id is a FK to auth.users.id and a row is guaranteed by the
        # on_auth_user_created trigger, so the profile id IS the auth user id.
        # The trigger stores the raw auth email; a completed login rewrites it
        # normalized — so match either form (prefer normalized).
        normalized_email = normalize_email(user_info["email"])
        candidates = [normalized_email]
        if user_info["email"] != normalized_email:
            candidates.append(user_info["email"])
        lookup = (
            service_client.table("profiles")
            .select("id, email_address")
            .in_("email_address", candidates)
            .execute()
        )
        by_email = {row["email_address"]: row for row in (lookup.data or [])}
        matched = by_email.get(normalized_email) or by_email.get(user_info["email"])
        if not matched:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to resolve auth user",
            )
        profile_id = matched["id"]

    profile_data = {
        "id": profile_id,
        "email_address": normalize_email(user_info["email"]),
        "full_name": user_info.get("name"),
        "avatar_url": user_info.get("picture"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    service_client.table("profiles").upsert(profile_data, on_conflict="id").execute()

    return profile_data


def _process_pending_invitations(user_id: str, email: str) -> None:
    """Find pending event_invitations by email, link the new user and notify them.

    Only processes invitations where invitee_id is NULL — i.e. ones we have not
    linked to a user yet. After the first run for a given invite, invitee_id is
    populated and the row is excluded from subsequent calls, which makes this
    function idempotent across re-logins while the invitation is still pending.
    """
    pending = (
        service_client.table("event_invitations")
        .select("*, events(name)")
        .eq("invitee_email", email)
        .eq("status", "pending")
        .is_("invitee_id", "null")
        .execute()
    )
    if not pending.data:
        return

    for invite in pending.data:
        service_client.table("event_invitations").update({"invitee_id": user_id}).eq("id", invite["id"]).execute()

        service_client.table("notifications").insert(
            {
                "user_id": user_id,
                "event_id": invite["event_id"],
                "notification_type": "event_invitation",
                "title": "You have been invited",
                "message": f"You have been invited to {invite['events']['name']}.",
                "metadata": {
                    "event_id": invite["event_id"],
                    "inviter_id": invite["inviter_id"],
                    "invitation_id": invite["id"],
                },
            }
        ).execute()


def _create_jwt(user_id: str, email: str, expires_minutes: int | None = None) -> str:
    if expires_minutes is None:
        expires_minutes = settings.jwt_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_user_profile(user: User) -> User:
    result = service_client.table("profiles").select("*").eq("id", user.id).single().execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return User(**result.data)


def update_user_timezone(user_id: str, tz_name: str) -> User:
    """Persist the user's IANA timezone on their profile and return the
    updated user. The value is validated upstream (AccountUpdateRequest);
    the chat agent reads it to render slot times as local wall-clock."""
    result = (
        service_client.table("profiles")
        .update({
            "timezone": tz_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return User(**result.data[0])
