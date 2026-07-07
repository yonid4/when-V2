from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator

from app.models.participant import ParticipantResponse  # noqa: F401 — re-exported for callers

EventType = Literal['meeting', 'social', 'birthday', 'other']
EventStatus = Literal['planning', 'confirmed', 'cancelled']


def validate_video_call_link(value: str | None) -> str | None:
    """Shared validator for user-supplied video-call links.

    A link is later rendered into an anchor `href` on the frontend, so a
    `javascript:` (or any non-http) scheme would be a stored-XSS sink. This is
    the server-side security boundary: `None`/empty means "no link"; any other
    value must be an http(s) URL with a network location. Rejection raises a
    ValueError, which Pydantic surfaces as a natural 422 at the router.
    """
    if value is None or not value.strip():
        return value
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError('video_call_link must be an http(s) URL')
    return value


class EventCreate(BaseModel):
    name: str
    description: str | None = None
    event_type: EventType
    earliest_datetime_utc: datetime
    latest_datetime_utc: datetime
    duration_minutes: int
    location: str | None = None
    video_call_link: str | None = None

    _validate_video_call_link = field_validator('video_call_link')(validate_video_call_link)


class EventUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    event_type: EventType | None = None
    earliest_datetime_utc: datetime | None = None
    latest_datetime_utc: datetime | None = None
    duration_minutes: int | None = None
    location: str | None = None
    video_call_link: str | None = None
    # NOTE: no `status` field (H11). Status transitions are state-machine
    # moves owned by dedicated flows — finalize_service sets 'confirmed'
    # (with finalized_* + calendar write), delete_event handles cancellation.
    # Exposing status here let a plain PATCH mark an event 'confirmed' with
    # no finalized times and no calendar event. Unknown body fields are
    # ignored by Pydantic, so stale clients sending `status` are harmless.

    _validate_video_call_link = field_validator('video_call_link')(validate_video_call_link)


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
    calendar_event_id: str | None
    proposals_needs_regeneration: bool
    proposals_last_generated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    finalized_at: datetime | None
    participants: list[ParticipantResponse] = []
