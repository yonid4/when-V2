import logging

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import settings
from app.dependencies import get_current_user
from app.models.calendar import CalendarAccountResponse
from app.models.user import User
from app.services import calendar_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calendar-accounts", tags=["calendar-accounts"])

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def _build_calendar_flow() -> Flow:
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


@router.get("", response_model=list[CalendarAccountResponse])
def list_accounts(current_user: User = Depends(get_current_user)):
    return calendar_service.get_calendar_accounts(current_user.id)


@router.get("/connect")
def connect_google(current_user: User = Depends(get_current_user)):
    flow = _build_calendar_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=current_user.id,
    )
    return RedirectResponse(url=auth_url)


@router.get("/callback")
def google_calendar_callback(code: str, state: str):
    """Receives the OAuth callback. `state` carries the user_id."""
    flow = _build_calendar_flow()
    flow._state = state
    flow.oauth2session.scope = None
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        logger.error("Failed to exchange calendar OAuth code: %s", exc)
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?error=calendar_auth_failed"
        )

    credentials: Credentials = flow.credentials

    try:
        user_info_svc = build("oauth2", "v2", credentials=credentials)
        user_info = user_info_svc.userinfo().get().execute()
        provider_email = user_info["email"]
        provider_account_id = user_info["id"]
    except Exception as exc:
        logger.error("Failed to fetch user info after calendar OAuth: %s", exc)
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?error=calendar_auth_failed"
        )

    calendar_service.connect_google_account(
        user_id=state,
        credentials=credentials,
        provider_email=provider_email,
        provider_account_id=provider_account_id,
    )

    return RedirectResponse(url=f"{settings.frontend_url}/settings?connected=true")


@router.delete("/{account_id}", status_code=204)
def disconnect_account(account_id: str, current_user: User = Depends(get_current_user)):
    calendar_service.disconnect_account(account_id, current_user.id)
