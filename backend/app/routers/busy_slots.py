from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user
from app.models.calendar import BusySlotResponse
from app.models.user import User
from app.services import busy_slots_service, sync_service

router = APIRouter(prefix="/api/busy-slots", tags=["busy-slots"])


@router.get("", response_model=list[BusySlotResponse])
def get_my_busy_slots(current_user: User = Depends(get_current_user)):
    return busy_slots_service.get_my_busy_slots(current_user.id)


@router.get("/event/{event_uid}", response_model=list[BusySlotResponse])
def get_event_busy_slots(event_uid: str, current_user: User = Depends(get_current_user)):
    """Return busy slots for all non-declined participants of an event."""
    result = busy_slots_service.get_event_busy_slots(event_uid, current_user.id)
    if result is None:
        raise HTTPException(status_code=403, detail="You are not a participant of this event")
    return result


@router.post("/sync", status_code=200)
def sync_my_slots(current_user: User = Depends(get_current_user)):
    count = sync_service.sync_busy_slots(current_user.id)
    return {"synced": count}


@router.post("/sync/event/{event_uid}", status_code=200)
def sync_event_slots(event_uid: str, current_user: User = Depends(get_current_user)):
    """Trigger a scoped sync for all participants of an event. Coordinator only."""
    event = busy_slots_service.get_event_for_coordinator_sync(event_uid, current_user.id)
    if event is None:
        raise HTTPException(status_code=403, detail="Only the coordinator can sync all participants")
    results = sync_service.sync_event_participants_scoped(
        event_id=event["id"],
        coordinator_id=event["coordinator_id"],
        time_min=event["earliest_datetime_utc"],
        time_max=event["latest_datetime_utc"],
    )
    total = sum(results.values())
    return {"synced": total, "by_user": results}
