import logging

from fastapi import HTTPException, status

from app.models.calendar import (
    CalendarAccountResponse,
    CalendarSourceResponse,
    CalendarSourceUpdate,
)
from app.providers.base import ConnectedIdentity, TokenBundle
from app.providers.registry import get_provider
from app.utils.supabase import service_client

logger = logging.getLogger(__name__)


def get_calendar_accounts(user_id: str) -> list[CalendarAccountResponse]:
    result = (
        service_client.table("calendar_accounts")
        .select("*, calendar_sources(*)")
        .eq("user_id", user_id)
        .execute()
    )
    accounts = []
    for row in result.data or []:
        sources = [CalendarSourceResponse(**s) for s in (row.pop("calendar_sources") or [])]
        accounts.append(CalendarAccountResponse(**row, sources=sources))
    return accounts


def connect_account(
    user_id: str,
    provider_name: str,
    identity: ConnectedIdentity,
) -> CalendarAccountResponse:
    """Connect (or reconnect) a calendar account for any provider.

    Upserts the account, lists its calendars via the provider, and upserts a
    source row per calendar. The write calendar is designated only when the user
    does not already have one anywhere (across all accounts/providers) — so
    connecting a second account never steals an existing write calendar. The DB
    trigger ``calendar_sources_single_write`` is the backstop that keeps the
    "exactly one write calendar per user" invariant true regardless of code path.
    """
    # Upsert calendar_accounts row
    upsert_result = (
        service_client.table("calendar_accounts")
        .upsert(
            {
                "user_id": user_id,
                "provider": provider_name,
                "provider_email": identity.provider_email,
                "provider_account_id": identity.provider_account_id,
                "credentials": identity.credentials,
                "needs_reauth": False,
            },
            on_conflict="user_id,provider,provider_account_id",
        )
        .execute()
    )
    account_row = upsert_result.data[0]
    account_id = account_row["id"]

    # List calendars via the provider; persist rotated tokens if any.
    provider = get_provider(provider_name)
    tokens = TokenBundle(identity.credentials)
    calendars = provider.list_calendars(tokens)
    if tokens.dirty:
        service_client.table("calendar_accounts").update(
            {"credentials": tokens.data}
        ).eq("id", account_id).execute()

    # Upsert each calendar source. We omit is_write_calendar so reconnecting an
    # account never clobbers an existing write-calendar designation — EXCEPT for
    # read-only calendars, where we force it false so a stale designation on a
    # now-known-read-only calendar (or a user mistake) can never persist.
    for cal in calendars:
        source_data = {
            "account_id": account_id,
            "calendar_id": cal.calendar_id,
            "calendar_name": cal.name,
            "is_enabled": True,
            "color": cal.color,
            "is_writable": cal.is_writable,
        }
        if not cal.is_writable:
            source_data["is_write_calendar"] = False
        service_client.table("calendar_sources").upsert(
            source_data,
            on_conflict="account_id,calendar_id",
        ).execute()

    # Designate a write calendar only if the user has none anywhere (checked
    # AFTER the upserts above, so a write flag we just cleared off a read-only
    # calendar counts as "none"). Only writable calendars are eligible.
    if not _user_has_write_calendar(user_id):
        writable = [c for c in calendars if c.is_writable]
        primary = next((c for c in writable if c.is_primary), writable[0] if writable else None)
        if primary is not None:
            service_client.table("calendar_sources").update(
                {"is_write_calendar": True}
            ).eq("account_id", account_id).eq("calendar_id", primary.calendar_id).execute()

    # Re-read sources so the response reflects the final is_write_calendar state.
    sources_result = (
        service_client.table("calendar_sources")
        .select("*")
        .eq("account_id", account_id)
        .execute()
    )
    sources = [CalendarSourceResponse(**s) for s in (sources_result.data or [])]

    return CalendarAccountResponse(**account_row, sources=sources)


def _user_has_write_calendar(user_id: str) -> bool:
    """True if the user already has a write calendar on any connected account."""
    result = (
        service_client.table("calendar_sources")
        .select("id, calendar_accounts(user_id)")
        .eq("is_write_calendar", True)
        .execute()
    )
    for row in result.data or []:
        account = row.get("calendar_accounts") or {}
        if account.get("user_id") == user_id:
            return True
    return False


def disconnect_account(account_id: str, user_id: str) -> bool:
    """Disconnect a calendar account.

    Revokes the credentials at the issuer (via the provider) BEFORE deleting the
    row. If revocation fails for an uncertain reason (network/5xx), the provider
    raises :class:`TokenRevocationError` and the database is left untouched so the
    user can retry — never strands a valid token without a way to revoke it.
    Providers without a revoke endpoint (e.g. Microsoft) treat revoke as a no-op.
    """
    result = (
        service_client.table("calendar_accounts")
        .select("id, provider, credentials")
        .eq("id", account_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        return False
    row = result.data[0]
    provider = get_provider(row.get("provider") or "google")
    provider.revoke(TokenBundle(row.get("credentials") or {}))
    service_client.table("calendar_accounts").delete().eq("id", account_id).execute()
    return True


def update_calendar_source(
    source_id: str,
    user_id: str,
    data: CalendarSourceUpdate,
) -> CalendarSourceResponse:
    # Verify ownership: source → account → user
    result = (
        service_client.table("calendar_sources")
        .select("*, calendar_accounts(user_id)")
        .eq("id", source_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar source not found",
        )
    source_row = result.data[0]
    if source_row["calendar_accounts"]["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    update_payload: dict = {}

    if data.is_enabled is not None:
        update_payload["is_enabled"] = data.is_enabled

    if data.is_write_calendar is True:
        # Read-only calendars cannot be the write calendar — creating events on
        # them fails at the provider (e.g. Google 403 requiredAccessLevel).
        if not source_row.get("is_writable", True):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="calendar_not_writable",
            )
        # Clear is_write_calendar on all other sources belonging to this user
        service_client.rpc(
            "clear_write_calendar_for_user",
            {"p_user_id": user_id, "p_exclude_source_id": source_id},
        ).execute()
        update_payload["is_write_calendar"] = True
    elif data.is_write_calendar is False:
        update_payload["is_write_calendar"] = False

    if not update_payload:
        # Nothing to update — return current state
        return _source_from_row(source_row)

    updated = (
        service_client.table("calendar_sources")
        .update(update_payload)
        .eq("id", source_id)
        .execute()
    )
    return CalendarSourceResponse(**updated.data[0])


def _source_from_row(row: dict) -> CalendarSourceResponse:
    return CalendarSourceResponse(
        id=row["id"],
        account_id=row["account_id"],
        calendar_id=row["calendar_id"],
        calendar_name=row["calendar_name"],
        is_enabled=row["is_enabled"],
        is_write_calendar=row["is_write_calendar"],
        is_writable=row.get("is_writable", True),
        color=row.get("color"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )
