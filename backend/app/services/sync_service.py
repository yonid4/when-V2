import logging
from datetime import datetime, timedelta, timezone

from app.providers.base import ProviderAPIError, ProviderAuthError, TokenBundle
from app.providers.registry import get_provider
from app.utils.google_auth import mark_account_needs_reauth
from app.utils.supabase import service_client

logger = logging.getLogger(__name__)


def sync_busy_slots(user_id: str) -> int:
    """Sync busy slots for all enabled calendar sources belonging to user_id.

    The forward end of the window is fixed at NOW + 90 days. The start of the
    window normally is NOW, but if the user is part of any active event whose
    ``earliest_datetime_utc`` is in the past, the start is widened backwards
    so we still sync the user's busy data covering that event's window.

    Returns the number of slots upserted.
    """
    now = datetime.now(timezone.utc)
    time_min = _earliest_active_event_start(user_id, default=now)
    time_max = now + timedelta(days=90)
    return _sync_user(user_id, time_min, time_max)


def _earliest_active_event_start(user_id: str, default: datetime) -> datetime:
    """Return the earliest ``earliest_datetime_utc`` across active (planning or
    confirmed) events the user is in — either as coordinator or as a
    non-declined participant — but never later than ``default``.

    If the user is in no such events, returns ``default``.
    """
    candidates: list[datetime] = [default]

    coord = (
        service_client.table("events")
        .select("earliest_datetime_utc")
        .eq("coordinator_id", user_id)
        .in_("status", ["planning", "confirmed"])
        .execute()
    )
    for row in coord.data or []:
        candidates.append(_parse_iso_utc(row["earliest_datetime_utc"]))

    participant_rows = (
        service_client.table("event_participants")
        .select("event_id")
        .eq("user_id", user_id)
        .neq("status", "declined")
        .execute()
    )
    event_ids = [r["event_id"] for r in (participant_rows.data or [])]
    if event_ids:
        participant_events = (
            service_client.table("events")
            .select("earliest_datetime_utc")
            .in_("id", event_ids)
            .in_("status", ["planning", "confirmed"])
            .execute()
        )
        for row in participant_events.data or []:
            candidates.append(_parse_iso_utc(row["earliest_datetime_utc"]))

    return min(candidates)


def _parse_iso_utc(value: str) -> datetime:
    """Parse an ISO datetime string and normalise to tz-aware UTC."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _sync_user(user_id: str, time_min: datetime, time_max: datetime) -> int:
    """Sync all enabled calendar sources for user_id within [time_min, time_max].

    Dispatches to the provider for each account based on ``account.provider`` so
    Google and Microsoft accounts sync through the same flow.

    If the sync changed any busy slot (upsert or stale deletion), the user's
    planning events are flagged ``proposals_needs_regeneration`` so cached
    proposals are not served against stale availability data.
    """
    accounts = (
        service_client.table("calendar_accounts")
        .select("id, provider, credentials, calendar_sources(id, calendar_id, is_enabled)")
        .eq("user_id", user_id)
        .execute()
    )

    total = 0
    changed = False
    for account in accounts.data or []:
        provider = get_provider(account["provider"])
        tokens = TokenBundle(account.get("credentials") or {})

        try:
            for source in account.get("calendar_sources") or []:
                if not source["is_enabled"]:
                    continue
                upserted, deleted = _sync_source(
                    user_id, source["id"], source["calendar_id"], provider, tokens, time_min, time_max
                )
                total += upserted
                changed = changed or bool(upserted or deleted)
        except ProviderAuthError as exc:
            logger.warning(
                "Refresh token invalid for account %s — marking needs_reauth: %s",
                account["id"],
                exc,
            )
            mark_account_needs_reauth(account["id"])
            continue

        _persist_account_after_sync(account["id"], tokens)

    if changed:
        _mark_user_events_stale(user_id)

    return total


def _mark_user_events_stale(user_id: str) -> None:
    """Set ``proposals_needs_regeneration`` on planning events the user is a
    non-declined participant of (the coordinator is always a participant row).

    DATA_MODEL staleness rule: any write to busy_slots for participants of an
    event must flag that event so the proposal service regenerates instead of
    serving cached results.
    """
    participant_rows = (
        service_client.table("event_participants")
        .select("event_id")
        .eq("user_id", user_id)
        .neq("status", "declined")
        .execute()
    )
    event_ids = [r["event_id"] for r in (participant_rows.data or [])]
    if not event_ids:
        return

    service_client.table("events").update(
        {"proposals_needs_regeneration": True}
    ).in_("id", event_ids).eq("status", "planning").execute()


def _persist_account_after_sync(account_id: str, tokens: TokenBundle) -> None:
    """Stamp last_synced_at and persist rotated credentials if the provider
    refreshed them during the sync (whole dict, so Microsoft's rotated refresh
    token is saved too)."""
    update_payload: dict = {"last_synced_at": datetime.now(timezone.utc).isoformat()}
    if tokens.dirty:
        update_payload["credentials"] = tokens.data
    service_client.table("calendar_accounts").update(update_payload).eq("id", account_id).execute()


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
    provider,
    tokens: TokenBundle,
    time_min: datetime,
    time_max: datetime,
) -> tuple[int, int]:
    """Fetch busy events from one calendar source and upsert as busy slots.

    Returns ``(upserted, deleted)`` slot counts so the caller can tell whether
    the sync changed anything. A :class:`ProviderAuthError` bubbles up so
    ``_sync_user`` can mark the account ``needs_reauth``; any other provider
    API error skips this source without touching its existing slots.
    """
    try:
        busy_events = provider.fetch_busy_events(tokens, calendar_id, time_min, time_max)
    except ProviderAuthError:
        raise
    except ProviderAPIError as exc:
        logger.error("Failed to fetch events for calendar %s: %s", calendar_id, exc)
        return 0, 0

    # The provider already expanded recurring events, dropped cancelled/all-day
    # events, and normalised times to UTC. Events the provider no longer returns
    # are treated as stale and deleted below.
    fetched_event_ids: set[str] = {be.event_id for be in busy_events}
    now_iso = datetime.now(timezone.utc).isoformat()
    slots_to_upsert = [
        {
            "user_id": user_id,
            "calendar_source_id": source_id,
            "provider_event_id": be.event_id,
            "start_time_utc": be.start_utc,
            "end_time_utc": be.end_utc,
            "last_synced_at": now_iso,
        }
        for be in busy_events
    ]

    if slots_to_upsert:
        service_client.table("busy_slots").upsert(
            slots_to_upsert,
            on_conflict="provider_event_id,calendar_source_id",
        ).execute()

    # Delete stale slots: any slot for this source within the fetch window that
    # was not returned by the provider (or was returned as cancelled). Both
    # bounds matter: without the lower bound, a narrow event-scoped sync would
    # treat every stored slot ending before time_max as stale and wipe busy
    # data outside the window it actually fetched.
    time_min_iso = time_min.isoformat()
    time_max_iso = time_max.isoformat()
    existing = (
        service_client.table("busy_slots")
        .select("provider_event_id")
        .eq("calendar_source_id", source_id)
        .gte("end_time_utc", time_min_iso)
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

    return len(slots_to_upsert), len(stale_event_ids)


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
