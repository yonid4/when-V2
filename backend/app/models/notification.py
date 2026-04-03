from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    event_id: str | None
    notification_type: str
    title: str
    message: str
    is_read: bool
    action_taken: bool
    action_type: str | None
    metadata: dict | None
    created_at: datetime
    read_at: datetime | None
    action_at: datetime | None


class NotificationActionRequest(BaseModel):
    action: Literal['accept', 'decline']
