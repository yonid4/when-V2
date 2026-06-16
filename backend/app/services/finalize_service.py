"""Event finalization service — confirms the event and writes it onto each
participant's own calendar (via that calendar's provider)."""

import logging

from fastapi import HTTPException

from app.models.user import User
from app.providers.base import EventPayload, ProviderAuthError, TokenBundle
from app.providers.registry import get_provider
from app.services.event_service import fetch_event_by_uid
from app.utils.google_auth import mark_account_needs_reauth
from app.utils.notifications import create_notifications
from app.utils.supabase import service_client

logger = logging.getLogger(__name__)


def get_finalize_status(uid: str, user_id: str) -> dict | None:
    """Return finalization status for an event. Accessible by coordinator or accepted participant.
    Returns None if user is not authorized (router raises 403)."""
    event = fetch_event_by_uid(uid, db=service_client)

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
            return None

    return event


def _pick_attendee_email(participant: dict, write_provider: str = "google") -> str | None:
    """Return the best email to use for the calendar invite.

    Preference order:
    1. provider_email from a connected account matching the write calendar's
       provider — this is the account most likely to link the invite to the
       attendee's own calendar.
    2. provider_email from any other connected calendar account.
    3. profiles.email_address — app sign-up email, used when the attendee has no
       connected calendar account.
    """
    profile = participant.get("profiles") or {}
    cal_accounts = profile.get("calendar_accounts") or []
    if isinstance(cal_accounts, dict):
        cal_accounts = [cal_accounts]
    for account in cal_accounts:
        if account.get("provider") == write_provider and account.get("provider_email"):
            return account["provider_email"]
    for account in cal_accounts:
        if account.get("provider_email"):
            return account["provider_email"]
    return profile.get("email_address")


def _create_event_on_write_calendar(client, write_cal_row: dict, payload: EventPayload) -> str:
    """Create ``payload`` on the given write calendar via its provider, persisting
    any rotated credentials (e.g. Microsoft rotates its refresh token on every
    refresh). Raises :class:`ProviderAuthError` / generic exceptions to the caller.
    """
    account = write_cal_row["calendar_accounts"]
    provider = get_provider(account["provider"])
    tokens = TokenBundle(account.get("credentials") or {})
    try:
        return provider.create_event(tokens, write_cal_row["calendar_id"], payload)
    finally:
        if tokens.dirty:
            client.table("calendar_accounts").update(
                {"credentials": tokens.data}
            ).eq("id", account["id"]).execute()


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
    """Finalize an event: confirm it and put it on everyone's calendar.

    The event is written directly onto EACH accepted participant's own write
    calendar using that calendar's provider (Google or Microsoft) and the
    participant's own stored credentials — so it appears reliably for everyone,
    cross-provider, without depending on invitation emails (which are unreliable
    across providers, e.g. personal Outlook → Gmail spam). When. tracks RSVP
    itself, so participants are not added as email attendees.

    Participants without a connected write calendar, plus any extra (external,
    non-app) emails, are invited as email attendees on the coordinator's copy.

    Steps:
    1. Fetch event by uid — 404 if not found, 409 if already confirmed, 403 if
       not coordinator.
    2. Fetch proposed_time row — 404 if not found / not this event's.
    3. Fetch accepted participants.
    4. Map every user's write calendar; the coordinator must have one (422).
    5. Split participants into direct-write (have a write calendar) vs emailed.
    6. Create the coordinator's copy (required); then best-effort write to each
       other participant's own calendar.
    7. Mark the event confirmed and insert notifications.
    8. Return the updated event row.
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

    # Idempotency guard: refuse to re-finalize an already-confirmed event so we
    # don't create a second Google Calendar event or duplicate notifications.
    if event["status"] == "confirmed":
        raise HTTPException(status_code=409, detail="event_already_finalized")

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

    # 4. Look up every user's write calendar in one query, keyed by user_id. Each
    #    user has at most one write calendar across all providers (DB-enforced),
    #    so this map tells us where to write for everyone.
    write_cal_result = (
        client.table("calendar_sources")
        .select("id, calendar_id, is_writable, calendar_accounts(id, user_id, provider, credentials)")
        .eq("is_write_calendar", True)
        .execute()
    )
    write_cals_by_user: dict[str, dict] = {}
    for row in write_cal_result.data or []:
        account = row.get("calendar_accounts") or {}
        owner_id = account.get("user_id")
        if owner_id:
            write_cals_by_user[owner_id] = row

    coordinator_write = write_cals_by_user.get(current_user.id)
    if not coordinator_write:
        raise HTTPException(status_code=422, detail="no_write_calendar")
    # Defensive: a read-only calendar can't have events created on it. This is
    # normally prevented when setting the write calendar, but guard here too so
    # we return a clear error instead of a provider 403 → 502.
    if not coordinator_write.get("is_writable", True):
        raise HTTPException(status_code=422, detail="write_calendar_not_writable")
    coordinator_provider = coordinator_write["calendar_accounts"]["provider"]
    coordinator_account_id = coordinator_write["calendar_accounts"]["id"]

    # 5. Split accepted participants (minus excluded, minus the coordinator) into:
    #      - direct writes: those WITH a connected write calendar — the event is
    #        written straight onto their own calendar via their own provider, so
    #        it shows up reliably regardless of provider and without depending on
    #        a cross-provider invitation email. When. already tracks RSVP.
    #      - emailed attendees: those WITHOUT a write calendar — invited by email
    #        as attendees on the coordinator's copy (the best we can do for them).
    #    extra_emails (true external, non-app people) are always emailed attendees.
    direct_write_user_ids: list[str] = []
    emailed_attendees: list[str] = []
    seen_emails: set[str] = set()

    for p in participants:
        participant_id = p["user_id"]
        if participant_id in _excluded or participant_id == current_user.id:
            continue
        if participant_id in write_cals_by_user:
            direct_write_user_ids.append(participant_id)
        else:
            email = _pick_attendee_email(p, coordinator_provider)
            if email and email not in seen_emails:
                seen_emails.add(email)
                emailed_attendees.append(email)

    for email in _extra:
        if email and email not in seen_emails:
            seen_emails.add(email)
            emailed_attendees.append(email)

    # Build description: note + video call link
    description_parts = []
    if note:
        description_parts.append(note)
    if video_call_link:
        description_parts.append(f"Video call: {video_call_link}")
    description = "\n\n".join(description_parts)

    def _build_payload(attendee_emails: list[str]) -> EventPayload:
        return EventPayload(
            summary=name,
            description=description,
            start_utc=proposed_time["start_time_utc"],
            end_utc=proposed_time["end_time_utc"],
            location=location or "",
            attendee_emails=attendee_emails,
        )

    # 6. Create the coordinator's (organizer) copy — REQUIRED. It carries the
    #    emailed attendees. Abort the whole finalize if this fails.
    try:
        calendar_event_id = _create_event_on_write_calendar(
            client, coordinator_write, _build_payload(emailed_attendees)
        )
    except ProviderAuthError as exc:
        logger.warning(
            "Coordinator calendar credentials invalid during finalization for account %s: %s",
            coordinator_account_id,
            exc,
        )
        mark_account_needs_reauth(coordinator_account_id)
        raise HTTPException(status_code=422, detail="calendar_credentials_expired")
    except Exception as exc:
        logger.error("Calendar API error during finalization: %s", exc)
        raise HTTPException(status_code=502, detail="calendar_create_failed")

    # 6b. Best-effort: write the event onto each other participant's own calendar
    #     via their own provider. A failure here never aborts finalization — the
    #     event is already confirmed and When. tracks RSVP independently.
    for participant_id in direct_write_user_ids:
        participant_write = write_cals_by_user[participant_id]
        try:
            _create_event_on_write_calendar(client, participant_write, _build_payload([]))
        except ProviderAuthError as exc:
            logger.warning(
                "Skipping calendar write for participant %s — needs reauth: %s",
                participant_id,
                exc,
            )
            mark_account_needs_reauth(participant_write["calendar_accounts"]["id"])
        except Exception as exc:
            logger.error(
                "Failed to write event to participant %s calendar: %s", participant_id, exc
            )

    # 8. Atomically update DB (only after successful calendar creation)
    update_payload: dict = {
        "status": "confirmed",
        "finalized_start_time_utc": proposed_time["start_time_utc"],
        "finalized_end_time_utc": proposed_time["end_time_utc"],
        "calendar_event_id": calendar_event_id,
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
                "calendar_event_id": calendar_event_id,
            },
        })

    create_notifications(notification_rows)

    return updated_event
