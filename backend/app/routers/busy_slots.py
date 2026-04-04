from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models.calendar import BusySlotResponse
from app.models.user import User
from app.services import sync_service
from app.utils.supabase import service_client

router = APIRouter(prefix="/api/busy-slots", tags=["busy-slots"])


@router.get("", response_model=list[BusySlotResponse])
def get_my_busy_slots(current_user: User = Depends(get_current_user)):
    result = (
        service_client.table("busy_slots")
        .select("id, user_id, start_time_utc, end_time_utc, calendar_source_id")
        .eq("user_id", current_user.id)
        .order("start_time_utc")
        .execute()
    )
    return result.data or []


@router.get("/event/{event_uid}", response_model=list[BusySlotResponse])
def get_event_busy_slots(event_uid: str, current_user: User = Depends(get_current_user)):
    """Return busy slots for all participants of an event (for AvailabilityGrid)."""
    event = (
        service_client.table("events")
        .select("id")
        .eq("uid", event_uid)
        .single()
        .execute()
    )
    if not event.data:
        return []

    event_id = event.data["id"]

    participants = (
        service_client.table("event_participants")
        .select("user_id")
        .eq("event_id", event_id)
        .execute()
    )
    user_ids = [p["user_id"] for p in (participants.data or [])]
    if not user_ids:
        return []

    result = (
        service_client.table("busy_slots")
        .select("id, user_id, start_time_utc, end_time_utc, calendar_source_id")
        .in_("user_id", user_ids)
        .order("start_time_utc")
        .execute()
    )
    return result.data or []


@router.post("/sync", status_code=200)
def sync_my_slots(current_user: User = Depends(get_current_user)):
    count = sync_service.sync_busy_slots(current_user.id)
    return {"synced": count}


@router.post("/sync/event/{event_uid}", status_code=200)
def sync_event_slots(event_uid: str, current_user: User = Depends(get_current_user)):
    """Trigger sync for all participants of an event. Only the coordinator may call this."""
    event = (
        service_client.table("events")
        .select("id, coordinator_id")
        .eq("uid", event_uid)
        .single()
        .execute()
    )
    if not event.data:
        return {"synced": 0}

    if event.data["coordinator_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the coordinator can sync all participants",
        )

    results = sync_service.sync_event_participants(event.data["id"])
    total = sum(results.values())
    return {"synced": total, "by_user": results}
