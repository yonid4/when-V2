from pydantic import BaseModel, field_validator

from app.utils.dates import is_valid_timezone


class User(BaseModel):
    id: str
    email_address: str
    full_name: str | None = None
    avatar_url: str | None = None
    # IANA timezone name from profiles.timezone (e.g. "America/Los_Angeles").
    # Optional so it auto-populates from the profiles select("*") row.
    timezone: str | None = None
    # JWT for this request — used to authenticate Supabase queries. Internal
    # only: endpoints that serialize User must exclude it (the session JWT is
    # delivered exclusively via the HttpOnly ``session`` cookie).
    token: str = ''


class AccountUpdateRequest(BaseModel):
    """Body for PATCH /api/account — profile settings the user's client may
    update. Currently only the IANA timezone, auto-detected by the browser."""

    timezone: str

    @field_validator("timezone")
    @classmethod
    def _must_be_iana(cls, value: str) -> str:
        if not is_valid_timezone(value):
            raise ValueError("must be a valid IANA timezone name")
        return value


class SessionExchangeRequest(BaseModel):
    """Body for POST /auth/session/exchange — the signed one-time login code
    handed to the frontend via the post-login redirect."""

    code: str
