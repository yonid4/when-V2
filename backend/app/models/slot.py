from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.event import validate_video_call_link

# Anti-fan-out cap: 100 is generous for a real meeting while blocking mass-mail abuse.
MAX_FINALIZE_RECIPIENTS = 100


class PreferredSlotCreate(BaseModel):
    start_time_utc: str
    end_time_utc: str


class PreferredSlotResponse(BaseModel):
    id: str
    event_id: str
    user_id: str
    start_time_utc: str
    end_time_utc: str
    created_at: str


class ProposalResponse(BaseModel):
    id: str
    event_id: str
    start_time_utc: str
    end_time_utc: str
    conflict_count: int
    preferred_count: int
    reasoning: str
    rank: int


class AvailabilitySegment(BaseModel):
    start_time_utc: str
    end_time_utc: str
    type: Literal["busy", "preferred", "conflict"]
    busy_count: int
    preferred_count: int


class FinalizeRequest(BaseModel):
    proposed_time_id: str
    name: str
    excluded_user_ids: list[str] = Field(default=[], max_length=MAX_FINALIZE_RECIPIENTS)
    extra_emails: list[EmailStr] = Field(default=[], max_length=MAX_FINALIZE_RECIPIENTS)
    note: str = ""
    location: str = ""
    video_call_link: str = ""

    _validate_video_call_link = field_validator('video_call_link')(validate_video_call_link)


class ProposedTimeNoteCreate(BaseModel):
    content: str


class ProposedTimeNoteResponse(BaseModel):
    id: str
    proposed_time_id: str
    user_id: str
    content: str
    created_at: datetime


class FinalizeStatusResponse(BaseModel):
    status: str
    finalized_start_time_utc: str | None
    finalized_end_time_utc: str | None
    calendar_event_id: str | None
