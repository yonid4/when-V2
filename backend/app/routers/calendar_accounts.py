import logging

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings
from app.dependencies import get_current_user
from app.models.calendar import CalendarAccountResponse
from app.models.user import User
from app.services import calendar_service
from app.utils.google_auth import build_calendar_flow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calendar-accounts", tags=["calendar-accounts"])


@router.get("", response_model=list[CalendarAccountResponse])
def list_accounts(current_user: User = Depends(get_current_user)):
    return calendar_service.get_calendar_accounts(current_user.id)


@router.get("/connect-url")
def connect_google_url(current_user: User = Depends(get_current_user)):
    """Returns the Google OAuth URL as JSON so the frontend can redirect without losing the Authorization header."""
    flow = build_calendar_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=current_user.id,
        include_granted_scopes="false",
    )
    return {"url": auth_url}


@router.get("/connect")
def connect_google(current_user: User = Depends(get_current_user)):
    flow = build_calendar_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=current_user.id,
    )
    return RedirectResponse(url=auth_url)


@router.get("/callback")
def google_calendar_callback(code: str, state: str):
    """Receives the OAuth callback. `state` carries the user_id."""
    flow = build_calendar_flow()
    flow._state = state
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

    try:
        calendar_service.connect_google_account(
            user_id=state,
            credentials=credentials,
            provider_email=provider_email,
            provider_account_id=provider_account_id,
        )
    except Exception as exc:
        logger.error("Failed to save calendar account to DB: %s", exc, exc_info=True)
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?error=calendar_save_failed"
        )

    return RedirectResponse(url=f"{settings.frontend_url}/settings?connected=true")


@router.delete("/{account_id}", status_code=204)
def disconnect_account(account_id: str, current_user: User = Depends(get_current_user)):
    calendar_service.disconnect_account(account_id, current_user.id)
