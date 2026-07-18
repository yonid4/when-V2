from datetime import datetime
from typing import Literal
from pydantic import BaseModel

ParticipantStatus = Literal['invited', 'accepted', 'declined', 'maybe']
RsvpStatus = Literal['pending', 'going', 'maybe', 'not_going']


class ParticipantResponse(BaseModel):
    event_id: str
    user_id: str
    status: ParticipantStatus
    rsvp_status: RsvpStatus | None
    can_invite: bool
    joined_at: datetime
    full_name: str | None = None
    avatar_url: str | None = None
    email_address: str | None = None


class RsvpUpdate(BaseModel):
    rsvp_status: RsvpStatus


class PermissionUpdate(BaseModel):
    can_invite: bool


class DirectInviteResponse(BaseModel):
    action: Literal['accept', 'decline']
