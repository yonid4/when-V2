from typing import Optional
from pydantic import BaseModel


class CalendarSourceResponse(BaseModel):
    id: str
    account_id: str
    calendar_id: str
    calendar_name: str
    is_enabled: bool
    is_write_calendar: bool
    color: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CalendarSourceUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    is_write_calendar: Optional[bool] = None


class CalendarAccountResponse(BaseModel):
    id: str
    user_id: str
    provider: str
    provider_email: str
    provider_account_id: str
    connected_at: Optional[str] = None
    last_synced_at: Optional[str] = None
    sources: list[CalendarSourceResponse] = []


class BusySlotResponse(BaseModel):
    id: str
    user_id: str
    start_time_utc: str
    end_time_utc: str
    calendar_source_id: str
