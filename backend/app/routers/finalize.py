from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user
from app.models.slot import FinalizeRequest, FinalizeStatusResponse
from app.models.user import User
from app.services.finalize_service import finalize_event, get_finalize_status

router = APIRouter(tags=["finalize"])


@router.post("/api/events/{uid}/finalize")
def post_finalize(
    uid: str,
    body: FinalizeRequest,
    current_user: User = Depends(get_current_user),
):
    """Coordinator finalizes an event by selecting a proposed time.

    Creates a Google Calendar event for all accepted participants and marks
    the event as confirmed.
    """
    try:
        updated_event = finalize_event(
            uid=uid,
            proposed_time_id=body.proposed_time_id,
            name=body.name,
            excluded_user_ids=body.excluded_user_ids,
            extra_emails=body.extra_emails,
            note=body.note,
            location=body.location,
            video_call_link=body.video_call_link,
            current_user=current_user,
        )
    except HTTPException as exc:
        if exc.status_code == 502:
            raise HTTPException(status_code=502, detail="calendar_create_failed")
        if exc.status_code == 422:
            raise HTTPException(status_code=422, detail="no_write_calendar")
        raise
    return updated_event


@router.get(
    "/api/events/{uid}/finalize/status",
    response_model=FinalizeStatusResponse,
)
def get_finalize_status_endpoint(
    uid: str,
    current_user: User = Depends(get_current_user),
):
    """Return finalization status for an event.

    Accessible by coordinator or any accepted participant.
    """
    event = get_finalize_status(uid, current_user.id)
    if event is None:
        raise HTTPException(status_code=403, detail="Forbidden")
    return FinalizeStatusResponse(
        status=event["status"],
        finalized_start_time_utc=event.get("finalized_start_time_utc"),
        finalized_end_time_utc=event.get("finalized_end_time_utc"),
        google_calendar_event_id=event.get("google_calendar_event_id"),
    )
