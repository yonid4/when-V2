"""Chat booking orchestration (deterministic — no LLM).

Two entry points, both consumed by the chat graph package:

* :func:`book_direct` — the coordinator books an event straight onto everyone's
  calendars now. Reuses the hardened finalize path (optimistic claim, rollback,
  notifications); in-system participants get an ``invited``/``pending`` row plus a
  real provider invite as attendees on the coordinator's copy — no
  ``event_invitations`` rows (they would PK-collide with the participant row).
* :func:`create_in_app_event` — the normal When. planning flow: create the event
  and invite each participant by email (in-system → notification, non-users →
  pending invitation matched at signup), exactly like the wizard.
"""

from datetime import datetime

from fastapi import HTTPException

from app.models.event import EventCreate
from app.models.user import User
from app.services import event_service, finalize_service, invitation_service
from app.utils.supabase import get_authed_client, service_client


def _draft_to_event_create(draft: dict) -> EventCreate:
    """Map a chat draft (plain dict from the thread jsonb) to an ``EventCreate``.

    ``earliest_datetime_utc`` / ``latest_datetime_utc`` may be ISO strings or
    ``datetime`` objects — Pydantic v2 coerces both.
    """
    return EventCreate(
        name=draft["title"],
        event_type=draft["event_type"],
        earliest_datetime_utc=draft["earliest_datetime_utc"],
        latest_datetime_utc=draft["latest_datetime_utc"],
        duration_minutes=draft["duration_minutes"],
        location=draft.get("location"),
    )


def book_direct(
    current_user: User,
    draft: dict,
    participants: list[dict],
    slot: dict,
    reference_time_utc: datetime,
) -> dict:
    """Create the event, add participants, pin the chosen slot, and finalize.

    Args:
        current_user: The coordinator (auto-added accepted/going by create_event).
        draft: ``{title, event_type, earliest_datetime_utc, latest_datetime_utc,
            duration_minutes, location?}``.
        participants: ``{user_id?, full_name, email, in_system, has_calendar,
            source}`` items. Only in-system participants (``in_system`` + a
            ``user_id``) get participant rows; the direct path is gated upstream
            on everyone being in-system.
        slot: ``{start_time_utc, end_time_utc, conflict_count, free_count, total,
            reasoning}`` — the confirmed booking slot.
        reference_time_utc: Deterministic "now" for the participant ``joined_at``.

    Returns:
        ``{"event_uid": <uid>}`` on success, or
        ``{"event_uid": <uid>, "error_code": <str>}`` when finalize fails (the
        planning event still exists and is recoverable through the normal UI), or
        ``{"event_uid": None, "error_code": "event_create_failed"}`` if the event
        could not be created.
    """
    created = event_service.create_event(_draft_to_event_create(draft), current_user)
    if created is None:
        return {"event_uid": None, "error_code": "event_create_failed"}
    event_id = created.id
    event_uid = created.uid

    # Insert participant rows via the authed client (RLS-verified: the coordinator
    # may insert any participant row). No event_invitations rows — responses go
    # through the direct-invite endpoint (participant_service.respond_to_direct_invite).
    db = get_authed_client(current_user.token)
    joined_at = reference_time_utc.isoformat()
    pending_user_ids: list[str] = []
    participant_rows: list[dict] = []
    for p in participants:
        user_id = p.get("user_id")
        if not (p.get("in_system") and user_id):
            continue
        if user_id == current_user.id:
            continue  # coordinator already added (accepted/going) by create_event
        pending_user_ids.append(user_id)
        participant_rows.append({
            "event_id": event_id,
            "user_id": user_id,
            "status": "invited",
            "rsvp_status": "pending",
            "can_invite": False,
            "joined_at": joined_at,
        })
    if participant_rows:
        db.table("event_participants").insert(participant_rows).execute()

    # Pin the confirmed slot as proposed_times rank 1 via the service client
    # (fresh event → no (event_id, rank) unique-constraint collision).
    pt_result = (
        service_client.table("proposed_times")
        .insert({
            "event_id": event_id,
            "start_time_utc": slot["start_time_utc"],
            "end_time_utc": slot["end_time_utc"],
            "conflicts": slot.get("conflict_count", 0),
            "preferred_count": 0,
            "reasoning": "Booked via chat",
            "rank": 1,
        })
        .execute()
    )
    proposed_time_id = pt_result.data[0]["id"]

    # Reuse the hardened finalize path. Pending (invited) users are emailed as
    # attendees on the coordinator copy, never written onto their own calendars.
    try:
        finalize_service.finalize_event(
            event_uid,
            proposed_time_id,
            created.name,
            current_user,
            note="",
            location=draft.get("location") or "",
            pending_attendee_user_ids=pending_user_ids,
        )
    except HTTPException as exc:
        error_code = exc.detail if isinstance(exc.detail, str) else "finalize_failed"
        return {"event_uid": event_uid, "error_code": error_code}

    return {"event_uid": event_uid}


def create_in_app_event(
    current_user: User,
    draft: dict,
    participants: list[dict],
) -> dict:
    """Create the planning event and invite every non-coordinator participant.

    Mirrors the wizard's client-side flow: one ``invite_by_email`` per person —
    covers in-system users (notification) and non-users (pending invitation
    matched at signup). A 409 (already a participant / already invited) is
    tolerated; other errors propagate.

    Returns:
        ``{"event_uid": <uid>}``, or
        ``{"event_uid": None, "error_code": "event_create_failed"}`` if the event
        could not be created.
    """
    created = event_service.create_event(_draft_to_event_create(draft), current_user)
    if created is None:
        return {"event_uid": None, "error_code": "event_create_failed"}
    event_uid = created.uid

    for p in participants:
        if p.get("user_id") == current_user.id:
            continue  # the coordinator is already a participant
        email = p.get("email")
        if not email:
            continue
        try:
            invitation_service.invite_by_email(event_uid, current_user, email)
        except HTTPException as exc:
            if exc.status_code == 409:
                continue
            raise

    return {"event_uid": event_uid}
