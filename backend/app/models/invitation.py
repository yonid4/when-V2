from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr


class InviteRequest(BaseModel):
    email: EmailStr


class InvitationResponse(BaseModel):
    id: str
    event_id: str
    inviter_id: str
    invitee_id: str | None
    invitee_email: str
    status: str
    created_at: datetime
    updated_at: datetime


class InvitationRespondRequest(BaseModel):
    action: Literal['accept', 'decline']


class InvitationRespondResponse(BaseModel):
    event_uid: str | None = None
