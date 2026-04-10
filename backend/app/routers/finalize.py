from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.models.user import User
from app.services.finalize_service import finalize_event
from app.utils.supabase import service_client

router = APIRouter(tags=["finalize"])


# ─── Models ──────────────────────────────────────────────────────────────────

class FinalizeRequest(BaseModel):
    proposed_time_id: str
    name: str
    excluded_user_ids: list[str] = []
    extra_emails: list[str] = []
    note: str = ""
    location: str = ""
    video_call_link: str = ""


class FinalizeStatusResponse(BaseModel):
    status: str
    finalized_start_time_utc: str | None
    finalized_end_time_utc: str | None
    google_calendar_event_id: str | None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_event_by_uid(uid: str) -> dict:
    result = (
        service_client.table("events")
        .select(
            "id, uid, coordinator_id, status, finalized_start_time_utc, "
            "finalized_end_time_utc, google_calendar_event_id"
        )
        .eq("uid", uid)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return result.data


# ─── Endpoints ────────────────────────────────────────────────────────────────

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
def get_finalize_status(
    uid: str,
    current_user: User = Depends(get_current_user),
):
    """Return finalization status for an event.

    Accessible by coordinator or any accepted participant.
    """
    event = _get_event_by_uid(uid)

    # Check access: coordinator or accepted participant
    if event["coordinator_id"] != current_user.id:
        participant_result = (
            service_client.table("event_participants")
            .select("user_id")
            .eq("event_id", event["id"])
            .eq("user_id", current_user.id)
            .eq("status", "accepted")
            .maybe_single()
            .execute()
        )
        if not participant_result or not participant_result.data:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return FinalizeStatusResponse(
        status=event["status"],
        finalized_start_time_utc=event.get("finalized_start_time_utc"),
        finalized_end_time_utc=event.get("finalized_end_time_utc"),
        google_calendar_event_id=event.get("google_calendar_event_id"),
    )
