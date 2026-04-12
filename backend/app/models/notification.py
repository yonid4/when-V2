from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    event_id: str | None
    event_uid: str | None
    notification_type: Literal['event_invitation', 'invite_accepted', 'event_finalized', 'event_deleted']
    title: str
    message: str
    is_read: bool
    action_taken: bool
    action_type: Literal['accept', 'decline'] | None
    metadata: dict | None  # TODO: type metadata contents per notification_type
    created_at: datetime
    read_at: datetime | None
    action_at: datetime | None


class NotificationActionRequest(BaseModel):
    action: Literal['accept', 'decline']
