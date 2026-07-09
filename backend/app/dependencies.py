from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.config import settings
from app.models.user import User
from app.utils.supabase import service_client

# auto_error=False so a missing Authorization header falls through to the
# session cookie instead of an immediate 403.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: str | None = Cookie(default=None),
) -> User:
    """Resolve the authenticated user from a JWT.

    Accepts the token from either source, in this order:
    1. ``Authorization: Bearer`` header — explicit, used by tests and any
       non-browser client; takes precedence when both are present.
    2. ``session`` HttpOnly cookie — the browser path (set by
       /auth/session/exchange, forwarded by the frontend /api proxy).
    """
    token = credentials.credentials if credentials else session
    if not token:
        # Same status/detail HTTPBearer(auto_error=True) used, so existing
        # clients and tests see an unchanged contract for missing credentials.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated"
        )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str | None = payload.get("sub")
        email: str | None = payload.get("email")
        if user_id is None or email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = service_client.table("profiles").select("*").eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return User(**result.data, token=token)
