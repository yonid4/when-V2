from pydantic import BaseModel


class User(BaseModel):
    id: str
    email_address: str
    full_name: str | None = None
    avatar_url: str | None = None
    token: str = ''  # JWT for this request — used to authenticate Supabase queries
