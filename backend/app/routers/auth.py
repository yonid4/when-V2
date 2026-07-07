import hmac
import logging
import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.config import settings
from app.dependencies import get_current_user
from app.models.user import User
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Name of the short-lived cookie that pins a login flow to the browser it started
# in. Scoped to the callback path so it is only ever sent back to the endpoint
# that reads it.
_LOGIN_STATE_COOKIE = "oauth_login_state"
_LOGIN_CALLBACK_PATH = "/auth/google/callback"
# Login callbacks arrive within seconds; 10 minutes covers a slow consent screen.
_LOGIN_STATE_MAX_AGE = 600
# Secure only when the callback is served over HTTPS. In local dev the registered
# redirect URI is http://localhost, where a Secure cookie would be dropped by
# some browsers; in prod it is https and Secure must be on. Deriving from the
# configured redirect URI avoids introducing a separate env/debug flag.
_LOGIN_STATE_SECURE = settings.google_redirect_uri.lower().startswith("https")


@router.get("/google")
def google_login() -> RedirectResponse:
    """Start Google login.

    Generates a random ``state``, embeds it in the Google consent URL, and pins
    it to the browser via an HttpOnly cookie so the callback can prove the flow
    finished in the same browser that started it. Without this an attacker could
    initiate their own OAuth flow and complete it in a victim's browser (login
    CSRF / session fixation), because a bare/constant ``state`` binds to nothing.
    """
    state = secrets.token_urlsafe(32)
    auth_url = auth_service.get_authorization_url(state)
    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        key=_LOGIN_STATE_COOKIE,
        value=state,
        max_age=_LOGIN_STATE_MAX_AGE,
        httponly=True,
        secure=_LOGIN_STATE_SECURE,
        samesite="lax",  # top-level GET redirect from Google — Strict would drop it
        path=_LOGIN_CALLBACK_PATH,
    )
    return response


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Google login callback.

    Requires the ``state`` query param to match the ``oauth_login_state`` cookie
    set at login start, compared in constant time, before the code is exchanged.
    An attacker who initiates their own flow cannot complete it in a victim's
    browser because they cannot set that cookie there. The cookie is single-use:
    cleared on every outcome. Failures redirect to the frontend with a generic
    error and never leak details.
    """
    cookie_state = request.cookies.get(_LOGIN_STATE_COOKIE)
    state_ok = (
        bool(state)
        and bool(cookie_state)
        and hmac.compare_digest(state, cookie_state)
    )

    if error or not code or not state_ok:
        if error:
            logger.warning("Google login OAuth callback returned error: %s", error)
        else:
            logger.warning("Rejected Google login callback — missing/mismatched state")
        response = RedirectResponse(url=f"{settings.frontend_url}/?error=auth_failed")
        response.delete_cookie(_LOGIN_STATE_COOKIE, path=_LOGIN_CALLBACK_PATH)
        return response

    token = auth_service.exchange_code_and_upsert_user(code, state)
    response = RedirectResponse(url=f"{settings.frontend_url}/auth/callback?token={token}")
    response.delete_cookie(_LOGIN_STATE_COOKIE, path=_LOGIN_CALLBACK_PATH)
    return response


@router.get("/me", response_model=User)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return auth_service.get_user_profile(current_user)
