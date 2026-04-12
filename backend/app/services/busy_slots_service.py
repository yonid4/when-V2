"""Service layer for busy-slot read operations.

All Supabase queries that were previously in the busy_slots router have been
moved here so the router can stay free of database concerns.
"""

from app.services.event_service import fetch_event_by_uid
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


def get_event_busy_slots(event_uid: str, current_user_id: str) -> list[dict] | None:
    """Return busy slots for all non-declined participants of an event, within
    the event's datetime window.

    Returns None if the current_user is not the coordinator or an accepted/invited
    participant (router raises 403).
    Returns an empty list (not 404) when the event has no participants yet.
    Raises 404 (via fetch_event_by_uid) when the event does not exist.
    """
    event = fetch_event_by_uid(event_uid, db=service_client)
    event_id = event["id"]
    coordinator_id = event["coordinator_id"]
    earliest = event["earliest_datetime_utc"]
    latest = event["latest_datetime_utc"]

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
        if not participant or not participant.data:
            return None

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


def get_event_for_coordinator_sync(event_uid: str, current_user_id: str) -> dict | None:
    """Fetch event for coordinator-only sync endpoint.

    Raises 404 (via fetch_event_by_uid) if the event does not exist.
    Returns None if current_user is not the coordinator (router raises 403).
    Returns the event row dict on success.
    """
    event = fetch_event_by_uid(event_uid, db=service_client)

    if event["coordinator_id"] != current_user_id:
        return None

    return event
