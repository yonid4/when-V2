from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.config import settings
from app.dependencies import get_current_user
from app.models.user import User
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google")
def google_login() -> RedirectResponse:
    auth_url = auth_service.get_authorization_url()
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
def google_callback(code: str, state: str = "stateless") -> RedirectResponse:
    token = auth_service.exchange_code_and_upsert_user(code, state)
    redirect_url = f"{settings.frontend_url}/auth/callback?token={token}"
    return RedirectResponse(url=redirect_url)


@router.get("/me", response_model=User)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return auth_service.get_user_profile(current_user)
