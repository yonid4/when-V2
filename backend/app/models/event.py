from datetime import datetime
from typing import Literal
from pydantic import BaseModel

from app.models.participant import ParticipantResponse  # noqa: F401 — re-exported for callers

EventType = Literal['meeting', 'social', 'birthday', 'other']
EventStatus = Literal['planning', 'confirmed', 'cancelled']


class EventCreate(BaseModel):
    name: str
    description: str | None = None
    event_type: EventType
    earliest_datetime_utc: datetime
    latest_datetime_utc: datetime
    duration_minutes: int
    location: str | None = None
    video_call_link: str | None = None


class EventUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    event_type: EventType | None = None
    earliest_datetime_utc: datetime | None = None
    latest_datetime_utc: datetime | None = None
    duration_minutes: int | None = None
    location: str | None = None
    video_call_link: str | None = None
    status: EventStatus | None = None


class EventResponse(BaseModel):
    id: str
    uid: str
    name: str
    description: str | None
    event_type: EventType
    coordinator_id: str
    earliest_datetime_utc: datetime
    latest_datetime_utc: datetime
    duration_minutes: int
    status: EventStatus
    location: str | None
    video_call_link: str | None
    finalized_start_time_utc: datetime | None
    finalized_end_time_utc: datetime | None
    google_calendar_event_id: str | None
    proposals_needs_regeneration: bool
    proposals_last_generated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    finalized_at: datetime | None
    participants: list[ParticipantResponse] = []
