from fastapi import APIRouter, Depends, Response, status

from app.dependencies import get_current_user
from app.models.slot import ProposedTimeNoteCreate, ProposedTimeNoteResponse
from app.models.user import User
from app.services.proposal_notes_service import (
    create_note,
    delete_note,
    ensure_proposed_time_in_event,
    get_notes,
)
from app.services.proposal_service import get_event_and_check_access

router = APIRouter(tags=["proposal_notes"])


@router.get(
    "/api/events/{uid}/proposals/{proposed_time_id}/notes",
    response_model=list[ProposedTimeNoteResponse],
)
def list_notes(
    uid: str,
    proposed_time_id: str,
    current_user: User = Depends(get_current_user),
):
    event = get_event_and_check_access(uid, current_user.id)
    ensure_proposed_time_in_event(proposed_time_id, event["id"])
    return get_notes(proposed_time_id)


@router.post(
    "/api/events/{uid}/proposals/{proposed_time_id}/notes",
    response_model=ProposedTimeNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_note(
    uid: str,
    proposed_time_id: str,
    body: ProposedTimeNoteCreate,
    current_user: User = Depends(get_current_user),
):
    event = get_event_and_check_access(uid, current_user.id)
    ensure_proposed_time_in_event(proposed_time_id, event["id"])
    return create_note(proposed_time_id, current_user.id, body.content, uid)


@router.delete(
    "/api/events/{uid}/proposals/{proposed_time_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_note(
    uid: str,
    proposed_time_id: str,
    note_id: str,
    current_user: User = Depends(get_current_user),
):
    event = get_event_and_check_access(uid, current_user.id)
    ensure_proposed_time_in_event(proposed_time_id, event["id"])
    delete_note(note_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
