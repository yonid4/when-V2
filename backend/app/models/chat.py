"""Pydantic models for the agentic chat feature (Package 2 — plumbing).

Mirrors the `chat_threads` / `chat_messages` schema in DATA_MODEL.md. The
assistant message `payload` is stored as raw jsonb (`{"card": …, "buttons": […]}`)
so live responses and re-rendered history are byte-identical; the DraftCard /
ChatButton models below document that render-spec contract for the agent graph.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ─── Enums / literals (mirror the DB enums + text columns) ────────────────────

ChatThreadStatus = Literal[
    'idle', 'collecting', 'awaiting_email', 'awaiting_choice', 'awaiting_confirmation'
]
ChatRole = Literal['user', 'assistant']
ChatWorkflow = Literal['create_event', 'edit_event']
BookingMode = Literal['direct', 'in_app']
ChatActionType = Literal[
    'book_direct', 'use_in_app', 'confirm_draft', 'cancel', 'provide_email', 'pick_person'
]
DraftMode = Literal['create_direct', 'create_in_app', 'edit']


# ─── Page context (sent by the client each turn) ─────────────────────────────

class ChatPageContext(BaseModel):
    page: str
    event_uid: str | None = None


# ─── Structured action payload (button taps) ─────────────────────────────────

class DraftEdits(BaseModel):
    title: str | None = None
    duration_minutes: int | None = None
    location: str | None = None


class ChatActionPayload(BaseModel):
    type: ChatActionType
    email: str | None = None
    person_name: str | None = None
    user_id: str | None = None
    slot_index: int | None = None
    edits: DraftEdits | None = None


# ─── Turn request ────────────────────────────────────────────────────────────

class ChatTurnRequest(BaseModel):
    message: str | None = Field(default=None, max_length=2000)
    action: ChatActionPayload | None = None
    context: ChatPageContext | None = None

    @model_validator(mode='after')
    def _exactly_one_input(self) -> 'ChatTurnRequest':
        has_message = bool(self.message and self.message.strip())
        has_action = self.action is not None
        if has_message == has_action:
            raise ValueError('exactly one of `message` or `action` must be provided')
        return self


# ─── Assistant render spec (card + buttons) ──────────────────────────────────

class DraftCardParticipant(BaseModel):
    name: str | None = None
    email: str
    in_system: bool
    has_calendar: bool
    user_id: str | None = None


class DraftCardSlot(BaseModel):
    start_time_utc: datetime
    end_time_utc: datetime
    conflict_count: int
    free_count: int
    total: int
    reasoning: str


class EditChange(BaseModel):
    """A single before/after row shown in edit mode."""

    model_config = ConfigDict(populate_by_name=True)

    field: str
    label: str
    # `from` is a Python keyword — aliased so the jsonb key stays `from`.
    from_: str | int | None = Field(default=None, alias='from')
    to: str | int | None = None


class DraftCard(BaseModel):
    mode: DraftMode | None = None
    title: str
    event_type: str | None = None
    earliest_datetime_utc: datetime | None = None
    latest_datetime_utc: datetime | None = None
    duration_minutes: int | None = None
    participants: list[DraftCardParticipant] = []
    slots: list[DraftCardSlot] = []
    changes: list[EditChange] | None = None
    event_uid: str | None = None


class ChatButton(BaseModel):
    label: str
    action: ChatActionPayload


# ─── Responses ───────────────────────────────────────────────────────────────

class ChatMessageResponse(BaseModel):
    id: str
    thread_id: str
    role: ChatRole
    content: str
    # Raw jsonb sidecar: assistant → {"card": …, "buttons": […]}; user → action.
    payload: dict | None = None
    created_at: datetime


class ChatThreadResponse(BaseModel):
    id: str
    title: str | None = None
    status: ChatThreadStatus
    workflow: ChatWorkflow | None = None
    last_event_uid: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatTurnResponse(BaseModel):
    thread: ChatThreadResponse
    messages: list[ChatMessageResponse]
    # Set when an event was created OR edited — triggers frontend invalidation.
    event_uid: str | None = None
