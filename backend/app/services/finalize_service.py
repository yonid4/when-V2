"""Event finalization service — creates Google Calendar event and confirms event."""

import logging

from fastapi import HTTPException
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings
from app.models.user import User
from app.utils.supabase import service_client

logger = logging.getLogger(__name__)


def get_event_by_uid(uid: str) -> dict:
    """Look up event by uid. Raises 404 if not found."""
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
        raise HTTPException(status_code=404, detail="Event not found")
    return result.data


def get_finalize_status(uid: str, user_id: str) -> dict:
    """Return finalization status for an event. Accessible by coordinator or accepted participant."""
    event = get_event_by_uid(uid)

    if event["coordinator_id"] != user_id:
        participant_result = (
            service_client.table("event_participants")
            .select("user_id")
            .eq("event_id", event["id"])
            .eq("user_id", user_id)
            .eq("status", "accepted")
            .maybe_single()
            .execute()
        )
        if not participant_result or not participant_result.data:
            raise HTTPException(status_code=403, detail="Forbidden")

    return event


def _pick_attendee_email(participant: dict) -> str | None:
    """Return the best email to use for a Google Calendar invite.

    Preference order:
    1. provider_email from the user's connected Google calendar account — this is
       the actual Google account so Calendar can link the invite to their calendar.
    2. profiles.email_address — app sign-up email, used as fallback when the user
       has no connected Google account.
    """
    profile = participant.get("profiles") or {}
    cal_accounts = profile.get("calendar_accounts") or []
    if isinstance(cal_accounts, dict):
        cal_accounts = [cal_accounts]
    for account in cal_accounts:
        if account.get("provider") == "google" and account.get("provider_email"):
            return account["provider_email"]
    return profile.get("email_address")


def finalize_event(
    uid: str,
    proposed_time_id: str,
    name: str,
    current_user: User,
    excluded_user_ids: list[str] | None = None,
    extra_emails: list[str] | None = None,
    note: str = "",
    location: str = "",
    video_call_link: str = "",
    db=None,
) -> dict:
    """Finalize an event by creating a Google Calendar event and marking it confirmed.

    Steps:
    1. Fetch event by uid — 404 if not found, 403 if not coordinator.
    2. Fetch proposed_time row — 404 if not found, verify it belongs to this event.
    3. Fetch accepted participants with profile email + Google account email.
    4. Fetch coordinator's write calendar source — 422 if none.
    5. Fetch coordinator's Google credentials — load Credentials object.
    6. Build and create Google Calendar event.
    7. On success, atomically update DB and insert notifications.
    8. Return updated event row.
    """
    client = db if db is not None else service_client

    # 1. Fetch event
    event_result = (
        client.table("events")
        .select("id, uid, name, coordinator_id, status")
        .eq("uid", uid)
        .maybe_single()
        .execute()
    )
    if not event_result or not event_result.data:
        raise HTTPException(status_code=404, detail="Event not found")
    event = event_result.data

    if event["coordinator_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Coordinator only")

    # 2. Fetch proposed_time
    pt_result = (
        client.table("proposed_times")
        .select("id, event_id, start_time_utc, end_time_utc")
        .eq("id", proposed_time_id)
        .maybe_single()
        .execute()
    )
    if not pt_result or not pt_result.data:
        raise HTTPException(status_code=404, detail="Proposed time not found")
    proposed_time = pt_result.data
    if proposed_time["event_id"] != event["id"]:
        raise HTTPException(status_code=404, detail="Proposed time not found")

    # 3. Fetch accepted participants.
    # We fetch both the profile email (app sign-up) and the Google provider_email
    # (actual Google account). The Google provider_email is preferred for invites
    # because it ensures Calendar links the invite to the participant's calendar.
    participants_result = (
        client.table("event_participants")
        .select(
            "user_id, "
            "profiles(email_address, full_name, calendar_accounts(provider, provider_email))"
        )
        .eq("event_id", event["id"])
        .eq("status", "accepted")
        .execute()
    )
    participants = participants_result.data or []

    # Resolve excluded_user_ids / extra_emails defaults
    _excluded = set(excluded_user_ids or [])
    _extra = list(extra_emails or [])

    # 4. Fetch coordinator's write calendar source
    write_cal_result = (
        client.table("calendar_sources")
        .select("id, calendar_id, calendar_accounts(user_id)")
        .eq("is_write_calendar", True)
        .execute()
    )
    write_cal_rows = write_cal_result.data or []
    write_calendar = None
    for row in write_cal_rows:
        account = row.get("calendar_accounts") or {}
        if account.get("user_id") == current_user.id:
            write_calendar = row
            break

    if not write_calendar:
        raise HTTPException(status_code=422, detail="no_write_calendar")

    # 5. Fetch coordinator's Google credentials
    creds_result = (
        client.table("calendar_accounts")
        .select("id, credentials")
        .eq("user_id", current_user.id)
        .eq("provider", "google")
        .maybe_single()
        .execute()
    )
    if not creds_result or not creds_result.data:
        raise HTTPException(status_code=422, detail="no_write_calendar")

    creds_data = creds_result.data.get("credentials") or {}
    credentials = Credentials(
        token=creds_data.get("access_token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )

    # 6. Build attendees list.
    # Start with accepted participants minus excluded ones.
    # Always include coordinator (even if not in event_participants).
    # Append extra_emails.
    seen_emails: set[str] = set()
    attendees = []

    for p in participants:
        if p["user_id"] in _excluded:
            continue
        email = _pick_attendee_email(p)
        if email and email not in seen_emails:
            seen_emails.add(email)
            attendees.append({"email": email})

    # Ensure coordinator is always included
    coordinator_result = (
        client.table("event_participants")
        .select(
            "user_id, "
            "profiles(email_address, full_name, calendar_accounts(provider, provider_email))"
        )
        .eq("event_id", event["id"])
        .eq("user_id", current_user.id)
        .maybe_single()
        .execute()
    )
    if coordinator_result and coordinator_result.data:
        coord_email = _pick_attendee_email(coordinator_result.data)
    else:
        # Fall back to fetching directly from profiles
        coord_profile_result = (
            client.table("profiles")
            .select("email_address")
            .eq("id", current_user.id)
            .maybe_single()
            .execute()
        )
        coord_email = (coord_profile_result.data or {}).get("email_address") if coord_profile_result else None

    if coord_email and coord_email not in seen_emails:
        seen_emails.add(coord_email)
        attendees.append({"email": coord_email})

    # Add extra (non-When.) invitees
    for email in _extra:
        if email and email not in seen_emails:
            seen_emails.add(email)
            attendees.append({"email": email})

    # Build description: note + video call link
    description_parts = []
    if note:
        description_parts.append(note)
    if video_call_link:
        description_parts.append(f"Video call: {video_call_link}")
    description = "\n\n".join(description_parts)

    event_body = {
        "summary": name,
        "description": description,
        "start": {
            "dateTime": proposed_time["start_time_utc"],
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": proposed_time["end_time_utc"],
            "timeZone": "UTC",
        },
        "attendees": attendees,
    }
    if location:
        event_body["location"] = location

    # 7. Create Google Calendar event — DO NOT update DB if this fails
    try:
        cal_service = build("calendar", "v3", credentials=credentials)
        created = (
            cal_service.events()
            .insert(calendarId=write_calendar["calendar_id"], body=event_body)
            .execute()
        )
        google_event_id = created.get("id")
    except HttpError as exc:
        logger.error("Google Calendar API error during finalization: %s", exc)
        raise HTTPException(status_code=502, detail="calendar_create_failed")
    except Exception as exc:
        logger.error("Unexpected error creating Google Calendar event: %s", exc)
        raise HTTPException(status_code=502, detail="calendar_create_failed")

    # 8. Atomically update DB (only after successful calendar creation)
    update_payload: dict = {
        "status": "confirmed",
        "finalized_start_time_utc": proposed_time["start_time_utc"],
        "finalized_end_time_utc": proposed_time["end_time_utc"],
        "google_calendar_event_id": google_event_id,
        "location": location or None,
        "video_call_link": video_call_link or None,
    }
    if name != event["name"]:
        update_payload["name"] = name

    updated_event_result = (
        client.table("events")
        .update(update_payload)
        .eq("id", event["id"])
        .execute()
    )

    updated_event = (updated_event_result.data or [{}])[0]

    # Insert event_finalized notifications for all accepted participants
    notification_rows = []
    for p in participants:
        notification_rows.append({
            "user_id": p["user_id"],
            "event_id": event["id"],
            "notification_type": "event_finalized",
            "title": f"{event['name']} has been scheduled",
            "message": "The event time has been confirmed.",
            "is_read": False,
            "metadata": {
                "finalized_start_time_utc": proposed_time["start_time_utc"],
                "finalized_end_time_utc": proposed_time["end_time_utc"],
                "google_calendar_event_id": google_event_id,
            },
        })

    if notification_rows:
        client.table("notifications").insert(notification_rows).execute()

    return updated_event
