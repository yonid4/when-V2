import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.config import settings
from app.dependencies import get_current_user
from app.models.calendar import CalendarAccountResponse
from app.models.user import User
from app.providers.base import TokenRevocationError
from app.providers.registry import get_provider
from app.services import calendar_service, sync_service
from app.utils.oauth_state import OAuthStateError, create_oauth_state, verify_oauth_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calendar-accounts", tags=["calendar-accounts"])


@router.get("", response_model=list[CalendarAccountResponse])
def list_accounts(current_user: User = Depends(get_current_user)):
    return calendar_service.get_calendar_accounts(current_user.id)


@router.get("/connect-url")
def connect_url(provider: str = "google", current_user: User = Depends(get_current_user)):
    """Return the provider OAuth URL as JSON so the frontend can redirect without
    losing the Authorization header. ``state`` is a short-lived signed token that
    binds the initiating user_id (verified in the callback)."""
    try:
        prov = get_provider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail="unsupported_provider")
    return {"url": prov.get_authorization_url(state=create_oauth_state(current_user.id))}


def _complete_connect(provider_name: str, code: str, state: str) -> RedirectResponse:
    """Shared callback tail: verify signed state → exchange code → connect
    account → kick off a sync.

    The ``user_id`` is taken ONLY from a valid signed ``state`` token — never the
    raw value — so a forged/replayed state cannot attach a calendar to another
    user. Any failure redirects back to settings with a readable error code
    rather than surfacing a raw 500 or leaking exception details.
    """
    try:
        user_id = verify_oauth_state(state)
    except OAuthStateError as exc:
        # Do not leak details — a bad/expired/forged state is a CSRF attempt or a
        # stale link. Reject before any token exchange or DB work.
        logger.warning(
            "Rejected %s calendar OAuth callback — invalid state: %s", provider_name, exc
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?error=calendar_auth_failed"
        )

    prov = get_provider(provider_name)
    try:
        identity = prov.exchange_code(code, state)
    except Exception as exc:
        logger.error("Failed to exchange %s calendar OAuth code: %s", provider_name, exc)
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?error=calendar_auth_failed"
        )

    try:
        calendar_service.connect_account(
            user_id=user_id, provider_name=provider_name, identity=identity
        )
    except Exception as exc:
        logger.error(
            "Failed to save %s calendar account to DB: %s", provider_name, exc, exc_info=True
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?error=calendar_save_failed"
        )

    try:
        sync_service.sync_busy_slots(user_id)
    except Exception as exc:
        logger.warning("Auto-sync after calendar connect failed for user %s: %s", user_id, exc)

    return RedirectResponse(url=f"{settings.frontend_url}/settings?connected=true")


@router.get("/callback")
def google_calendar_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Google OAuth callback. Path unchanged so the existing registered redirect
    URI keeps working. ``state`` is a signed token verified in _complete_connect;
    a denied consent returns ``error`` instead of a code."""
    if error or not code or not state:
        logger.warning("Google calendar OAuth callback error: %s", error)
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?error=calendar_auth_failed"
        )
    return _complete_connect("google", code, state)


@router.get("/callback/microsoft")
def microsoft_calendar_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """Microsoft OAuth callback. Locked-down tenants may return ``error`` (e.g.
    admin consent required) instead of a code — surface it gracefully. ``state``
    is a signed token verified in _complete_connect."""
    if error or not code or not state:
        logger.warning(
            "Microsoft calendar OAuth callback error: %s — %s", error, error_description
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?error=calendar_auth_failed"
        )
    return _complete_connect("microsoft", code, state)


@router.delete("/{account_id}", status_code=204)
def disconnect_account(account_id: str, current_user: User = Depends(get_current_user)):
    try:
        ok = calendar_service.disconnect_account(account_id, current_user.id)
    except TokenRevocationError as exc:
        logger.warning("Aborting disconnect for account %s: %s", account_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Could not revoke calendar access — please try again in a moment.",
        )
    if not ok:
        raise HTTPException(status_code=403, detail="Calendar account not found or access denied")
