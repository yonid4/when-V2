from fastapi import HTTPException, status

from app.models.slot import PreferredSlotCreate, PreferredSlotResponse
from app.utils.supabase import service_client


def get_event_and_check_participant(uid: str, user_id: str) -> dict:
    """Look up event by uid and verify the user is a coordinator or participant.
    Raises 404 if event not found, 403 if user is not a participant or coordinator.
    Returns the event row.
    """
    event_result = (
        service_client.table("events")
        .select("id, coordinator_id")
        .eq("uid", uid)
        .maybe_single()
        .execute()
    )
    if not event_result or not event_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    event = event_result.data

    if event["coordinator_id"] == user_id:
        return event

    participant_result = (
        service_client.table("event_participants")
        .select("user_id")
        .eq("event_id", event["id"])
        .eq("user_id", user_id)
        .in_("status", ["accepted", "invited"])
        .maybe_single()
        .execute()
    )
    if not participant_result or not participant_result.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant of this event")

    return event


def create_preferred_slot(uid: str, user_id: str, data: PreferredSlotCreate) -> dict:
    event = get_event_and_check_participant(uid, user_id)
    event_id = event["id"]

    insert_result = (
        service_client.table("preferred_slots")
        .insert({
            "event_id": event_id,
            "user_id": user_id,
            "start_time_utc": data.start_time_utc,
            "end_time_utc": data.end_time_utc,
        })
        .execute()
    )
    if not insert_result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create slot")

    service_client.table("events").update(
        {"proposals_needs_regeneration": True}
    ).eq("id", event_id).execute()

    return insert_result.data[0]


def get_preferred_slots(uid: str, user_id: str) -> list[dict]:
    event = get_event_and_check_participant(uid, user_id)
    event_id = event["id"]

    result = (
        service_client.table("preferred_slots")
        .select("id, event_id, user_id, start_time_utc, end_time_utc, created_at")
        .eq("event_id", event_id)
        .execute()
    )
    return result.data or []


def delete_preferred_slot(uid: str, slot_id: str, user_id: str) -> None:
    slot_result = (
        service_client.table("preferred_slots")
        .select("id, user_id")
        .eq("id", slot_id)
        .maybe_single()
        .execute()
    )
    if not slot_result or not slot_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")

    if slot_result.data["user_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your slot")

    service_client.table("preferred_slots").delete().eq("id", slot_id).execute()
