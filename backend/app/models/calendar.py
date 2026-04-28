from datetime import datetime
from pydantic import BaseModel


class CalendarSourceResponse(BaseModel):
    id: str
    account_id: str
    calendar_id: str
    calendar_name: str
    is_enabled: bool
    is_write_calendar: bool
    color: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CalendarSourceUpdate(BaseModel):
    is_enabled: bool | None = None
    is_write_calendar: bool | None = None


class CalendarAccountResponse(BaseModel):
    id: str
    user_id: str
    provider: str
    provider_email: str
    provider_account_id: str
    connected_at: str | None = None
    last_synced_at: str | None = None
    needs_reauth: bool = False
    sources: list[CalendarSourceResponse] = []


class BusySlotResponse(BaseModel):
    id: str
    user_id: str
    start_time_utc: datetime
    end_time_utc: datetime
    calendar_source_id: str
