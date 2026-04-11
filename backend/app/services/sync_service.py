import logging
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build

from app.utils.google_auth import credentials_from_dict
from app.utils.supabase import service_client

logger = logging.getLogger(__name__)


def _to_utc(dt_str: str) -> str:
    """Parse a datetime string (possibly with timezone offset) and return a UTC ISO string."""
    dt = datetime.fromisoformat(dt_str)
    return dt.astimezone(timezone.utc).isoformat()


def sync_busy_slots(user_id: str) -> int:
    """Sync busy slots for all enabled calendar sources belonging to user_id.
    Returns the number of slots upserted."""
    now = datetime.now(timezone.utc)
    time_min = now
    time_max = now + timedelta(days=90)
    return _sync_user(user_id, time_min, time_max)


def _sync_user(user_id: str, time_min: datetime, time_max: datetime) -> int:
    """Sync all calendar sources for user_id within [time_min, time_max]."""
    accounts = (
        service_client.table("calendar_accounts")
        .select("id, credentials, calendar_sources(id, calendar_id, is_enabled)")
        .eq("user_id", user_id)
        .execute()
    )

    total = 0
    for account in accounts.data or []:
        creds_data = account.get("credentials") or {}
        original_token = creds_data.get("access_token")
        credentials = credentials_from_dict(creds_data)

        try:
            cal_service = build("calendar", "v3", credentials=credentials)
        except Exception as exc:
            logger.error("Failed to build calendar service for account %s: %s", account["id"], exc)
            continue

        for source in account.get("calendar_sources") or []:
            if not source["is_enabled"]:
                continue
            total += _sync_source(
                user_id, source["id"], source["calendar_id"], cal_service, time_min, time_max
            )

        # Persist refreshed credentials if the token was renewed during the API call
        if credentials.token and credentials.token != original_token:
            service_client.table("calendar_accounts").update(
                {
                    "credentials": {
                        **creds_data,
                        "access_token": credentials.token,
                        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
                    },
                    "last_synced_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", account["id"]).execute()
        else:
            service_client.table("calendar_accounts").update(
                {"last_synced_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", account["id"]).execute()

    return total


def sync_event_participants(event_id: str) -> dict[str, int]:
    """Sync busy slots for all accepted/invited participants of an event (global 90-day window).
    Returns a dict of {user_id: slots_upserted}."""
    now = datetime.now(timezone.utc)
    time_min = now
    time_max = now + timedelta(days=90)
    return _sync_participants_in_range(event_id, time_min, time_max)


def sync_event_participants_scoped(
    event_id: str,
    coordinator_id: str,
    time_min: str,
    time_max: str,
) -> dict[str, int]:
    """Sync busy slots for all accepted/invited participants of an event, bounded
    to the event's own datetime window.  Also syncs the coordinator even if they
    are not listed in event_participants.

    time_min / time_max are ISO strings from the events row.
    """
    try:
        t_min = datetime.fromisoformat(time_min).astimezone(timezone.utc)
        t_max = datetime.fromisoformat(time_max).astimezone(timezone.utc)
    except Exception as exc:
        logger.error("Invalid event datetime bounds: %s", exc)
        t_min = datetime.now(timezone.utc)
        t_max = t_min + timedelta(days=90)

    results = _sync_participants_in_range(event_id, t_min, t_max)

    # Also sync the coordinator, deduplicating if already in results
    if coordinator_id not in results:
        try:
            results[coordinator_id] = _sync_user(coordinator_id, t_min, t_max)
        except Exception as exc:
            logger.error("Failed to sync coordinator %s: %s", coordinator_id, exc)
            results[coordinator_id] = 0

    return results


def _sync_participants_in_range(
    event_id: str, time_min: datetime, time_max: datetime
) -> dict[str, int]:
    """Fetch accepted/invited participants for event_id and sync each one within
    [time_min, time_max].  Returns {user_id: slots_upserted}."""
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
            count = _sync_user(uid, time_min, time_max)
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
    time_min: datetime,
    time_max: datetime,
) -> int:
    """Fetch events from one calendar source and upsert as busy slots. Returns count."""
    try:
        all_items = []
        page_token = None
        while True:
            response = (
                cal_service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    maxResults=250,
                    pageToken=page_token,
                )
                .execute()
            )
            all_items.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except Exception as exc:
        logger.error("Failed to fetch events for calendar %s: %s", calendar_id, exc)
        return 0

    slots_to_upsert = []
    # Track all non-cancelled event IDs returned by Google so stale deletion
    # works correctly even for events that were skipped (all-day, missing times).
    # Cancelled events are intentionally excluded — they should be treated as
    # stale and deleted from the DB if they exist.
    fetched_event_ids: set[str] = set()

    for item in all_items:
        # Skip cancelled instances — treat them as stale so they get deleted.
        if item.get("status") == "cancelled":
            continue

        fetched_event_ids.add(item["id"])

        start = item.get("start", {})
        end = item.get("end", {})
        start_time = start.get("dateTime") or start.get("date")
        end_time = end.get("dateTime") or end.get("date")

        if not start_time or not end_time:
            continue

        # Skip all-day events (they use date strings, not dateTime)
        if "T" not in start_time or "T" not in end_time:
            continue

        slots_to_upsert.append(
            {
                "user_id": user_id,
                "calendar_source_id": source_id,
                "provider_event_id": item["id"],
                "start_time_utc": _to_utc(start_time),
                "end_time_utc": _to_utc(end_time),
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    if slots_to_upsert:
        service_client.table("busy_slots").upsert(
            slots_to_upsert,
            on_conflict="provider_event_id,calendar_source_id",
        ).execute()

    # Delete stale slots: any slot for this source within the fetch window that
    # was not returned by Google (or was returned as cancelled).
    time_max_iso = time_max.isoformat()
    existing = (
        service_client.table("busy_slots")
        .select("provider_event_id")
        .eq("calendar_source_id", source_id)
        .lt("end_time_utc", time_max_iso)
        .execute()
    )
    stale_event_ids = [
        row["provider_event_id"]
        for row in (existing.data or [])
        if row["provider_event_id"] not in fetched_event_ids
    ]
    if stale_event_ids:
        logger.info(
            "Deleting %d stale busy slot(s) for calendar_source_id=%s",
            len(stale_event_ids),
            source_id,
        )
        service_client.table("busy_slots").delete().eq(
            "calendar_source_id", source_id
        ).in_("provider_event_id", stale_event_ids).execute()

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
