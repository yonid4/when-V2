import logging
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.utils.supabase import service_client

logger = logging.getLogger(__name__)


def sync_busy_slots(user_id: str) -> int:
    """Sync busy slots for all enabled calendar sources belonging to user_id.
    Returns the number of slots upserted."""
    accounts = (
        service_client.table("calendar_accounts")
        .select("id, credentials, calendar_sources(id, calendar_id, is_enabled)")
        .eq("user_id", user_id)
        .execute()
    )

    total = 0
    for account in accounts.data or []:
        creds_data = account.get("credentials") or {}
        credentials = Credentials(
            token=creds_data.get("access_token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
        )

        try:
            cal_service = build("calendar", "v3", credentials=credentials)
        except Exception as exc:
            logger.error("Failed to build calendar service for account %s: %s", account["id"], exc)
            continue

        for source in account.get("calendar_sources") or []:
            if not source["is_enabled"]:
                continue
            total += _sync_source(user_id, source["id"], source["calendar_id"], cal_service)

        # Update last_synced_at
        service_client.table("calendar_accounts").update(
            {"last_synced_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", account["id"]).execute()

    return total


def sync_event_participants(event_id: str) -> dict[str, int]:
    """Sync busy slots for all accepted participants of an event.
    Returns a dict of {user_id: slots_upserted}."""
    participants = (
        service_client.table("event_participants")
        .select("user_id")
        .eq("event_id", event_id)
        .in_("status", ["accepted", "invited"])
        .execute()
    )

    results: dict[str, int] = {}
    for row in participants.data or []:
        uid = row["user_id"]
        try:
            count = sync_busy_slots(uid)
            results[uid] = count
        except Exception as exc:
            logger.error("Failed to sync busy slots for user %s: %s", uid, exc)
            results[uid] = 0
    return results


def _sync_source(
    user_id: str,
    source_id: str,
    calendar_id: str,
    cal_service,
) -> int:
    """Fetch events from one calendar source and upsert as busy slots. Returns count."""
    try:
        now = datetime.now(timezone.utc)
        # Look 90 days ahead
        time_max = now.replace(year=now.year + 1) if now.month <= 3 else now
        time_min = now.isoformat()
        time_max_iso = f"{now.year + 1}-01-01T00:00:00Z"

        events_result = (
            cal_service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max_iso,
                singleEvents=True,
                orderBy="startTime",
                maxResults=500,
            )
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch events for calendar %s: %s", calendar_id, exc)
        return 0

    items = events_result.get("items", [])
    slots_to_upsert = []

    for item in items:
        start = item.get("start", {})
        end = item.get("end", {})
        start_time = start.get("dateTime") or start.get("date")
        end_time = end.get("dateTime") or end.get("date")

        if not start_time or not end_time:
            continue

        # All-day events use date strings — convert to ISO with time
        if "T" not in start_time:
            start_time = f"{start_time}T00:00:00Z"
        if "T" not in end_time:
            end_time = f"{end_time}T00:00:00Z"

        slots_to_upsert.append(
            {
                "user_id": user_id,
                "calendar_source_id": source_id,
                "provider_event_id": item["id"],
                "start_time_utc": start_time,
                "end_time_utc": end_time,
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    if not slots_to_upsert:
        return 0

    service_client.table("busy_slots").upsert(
        slots_to_upsert,
        on_conflict="provider_event_id,calendar_source_id",
    ).execute()

    return len(slots_to_upsert)


def sync_all_users() -> dict[str, int]:
    """Sync busy slots for every user who has a connected calendar account."""
    users = (
        service_client.table("calendar_accounts")
        .select("user_id")
        .execute()
    )
    seen: set[str] = set()
    results: dict[str, int] = {}

    for row in users.data or []:
        uid = row["user_id"]
        if uid in seen:
            continue
        seen.add(uid)
        try:
            results[uid] = sync_busy_slots(uid)
        except Exception as exc:
            logger.error("Failed to sync busy slots for user %s: %s", uid, exc)
            results[uid] = 0

    return results
