import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from jose import jwt

from app.config import settings
from app.models.user import User
from app.utils.email import normalize_email
from app.utils.supabase import service_client

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def build_oauth_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    return flow


def get_authorization_url() -> str:
    flow = build_oauth_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state="stateless",
    )
    return auth_url


def exchange_code_and_upsert_user(code: str) -> str:
    """Exchange OAuth code, upsert profile, check pending invites, return JWT."""
    flow = build_oauth_flow()
    # Use a fixed state to match what we sent in the authorization URL
    flow._state = "stateless"
    # Disable scope change validation — calendar scopes may not be returned
    # immediately if the consent screen is in testing mode
    flow.oauth2session.scope = None
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange OAuth code: {exc}",
        )

    credentials = flow.credentials
    user_info = _fetch_google_user_info(credentials)

    profile = _upsert_profile(user_info, credentials)
    _process_pending_invitations(profile["id"], normalize_email(user_info["email"]))

    return _create_jwt(user_id=profile["id"], email=user_info["email"])


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
        # User already exists in auth.users — look them up by email
        response = service_client.auth.admin.list_users()
        users = response if isinstance(response, list) else getattr(response, "users", [])
        matched = next((u for u in users if u.email == user_info["email"]), None)
        if not matched:
            # Try fetching all pages
            page = 1
            while not matched:
                page += 1
                response = service_client.auth.admin.list_users(page=page, per_page=1000)
                batch = response if isinstance(response, list) else getattr(response, "users", [])
                if not batch:
                    break
                matched = next((u for u in batch if u.email == user_info["email"]), None)
        if not matched:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to resolve auth user",
            )
        profile_id = matched.id

    profile_data = {
        "id": profile_id,
        "email_address": normalize_email(user_info["email"]),
        "full_name": user_info.get("name"),
        "avatar_url": user_info.get("picture"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    service_client.table("profiles").upsert(profile_data, on_conflict="id").execute()

    return profile_data


def _upsert_calendar_account(user_id: str, user_info: dict, credentials: Credentials) -> None:
    service_client.table("calendar_accounts").upsert(
        {
            "user_id": user_id,
            "provider": "google",
            "provider_email": user_info["email"],
            "provider_account_id": user_info["id"],
            "credentials": {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
            },
        },
        on_conflict="user_id,provider,provider_account_id",
    ).execute()


def _process_pending_invitations(user_id: str, email: str) -> None:
    """Find pending event_invitations by email, link the new user and notify them."""
    pending = (
        service_client.table("event_invitations")
        .select("*, events(name)")
        .eq("invitee_email", email)
        .eq("status", "pending")
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
                "metadata": {"event_id": invite["event_id"], "inviter_id": invite["inviter_id"]},
            }
        ).execute()


def _create_jwt(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_user_profile(user: User) -> User:
    result = service_client.table("profiles").select("*").eq("id", user.id).single().execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return User(**result.data)
