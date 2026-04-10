"""Service layer for busy-slot read operations.

All Supabase queries that were previously in the busy_slots router have been
moved here so the router can stay free of database concerns.
"""

from fastapi import HTTPException, status

from app.utils.supabase import service_client


def get_my_busy_slots(user_id: str) -> list[dict]:
    """Return all busy slots for a user, ordered by start time."""
    result = (
        service_client.table("busy_slots")
        .select("id, user_id, start_time_utc, end_time_utc, calendar_source_id")
        .eq("user_id", user_id)
        .order("start_time_utc")
        .execute()
    )
    return result.data or []


def get_event_busy_slots(event_uid: str, current_user_id: str) -> list[dict]:
    """Return busy slots for all non-declined participants of an event, within
    the event's datetime window.

    Authorization: current_user must be the coordinator or an accepted/invited
    participant. Raises 403 otherwise.

    Returns an empty list (not 404) when the event has no participants yet.
    Raises 404 when the event does not exist.
    """
    # Fetch the event — use maybe_single so missing rows return None gracefully
    event = (
        service_client.table("events")
        .select("id, coordinator_id, earliest_datetime_utc, latest_datetime_utc")
        .eq("uid", event_uid)
        .maybe_single()
        .execute()
    )
    if not event.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    event_id = event.data["id"]
    coordinator_id = event.data["coordinator_id"]
    earliest = event.data["earliest_datetime_utc"]
    latest = event.data["latest_datetime_utc"]

    # Authorization check: must be coordinator or accepted/invited participant
    if current_user_id != coordinator_id:
        participant = (
            service_client.table("event_participants")
            .select("user_id")
            .eq("event_id", event_id)
            .eq("user_id", current_user_id)
            .in_("status", ["accepted", "invited"])
            .maybe_single()
            .execute()
        )
        if not participant.data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant of this event",
            )

    # Fetch all non-declined participants
    participants = (
        service_client.table("event_participants")
        .select("user_id")
        .eq("event_id", event_id)
        .neq("status", "declined")
        .execute()
    )
    user_ids = [p["user_id"] for p in (participants.data or [])]
    if not user_ids:
        return []

    result = (
        service_client.table("busy_slots")
        .select("id, user_id, start_time_utc, end_time_utc, calendar_source_id")
        .in_("user_id", user_ids)
        .lt("start_time_utc", latest)
        .gt("end_time_utc", earliest)
        .order("start_time_utc")
        .execute()
    )
    return result.data or []


def get_event_for_coordinator_sync(event_uid: str, current_user_id: str) -> dict:
    """Fetch event for coordinator-only sync endpoint.

    Raises 404 if the event does not exist.
    Raises 403 if current_user is not the coordinator.
    Returns the event row dict on success.
    """
    event = (
        service_client.table("events")
        .select("id, coordinator_id, earliest_datetime_utc, latest_datetime_utc")
        .eq("uid", event_uid)
        .maybe_single()
        .execute()
    )
    if not event.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if event.data["coordinator_id"] != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the coordinator can sync all participants",
        )

    return event.data
