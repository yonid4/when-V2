from pydantic import BaseModel


class User(BaseModel):
    id: str
    email_address: str
    full_name: str | None = None
    avatar_url: str | None = None
    # JWT for this request — used to authenticate Supabase queries. Internal
    # only: endpoints that serialize User must exclude it (the session JWT is
    # delivered exclusively via the HttpOnly ``session`` cookie).
    token: str = ''


class SessionExchangeRequest(BaseModel):
    """Body for POST /auth/session/exchange — the signed one-time login code
    handed to the frontend via the post-login redirect."""

    code: str
