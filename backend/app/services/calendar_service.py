import logging
from typing import Optional

from fastapi import HTTPException, status
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.models.calendar import (
    CalendarAccountResponse,
    CalendarSourceResponse,
    CalendarSourceUpdate,
)
from app.config import settings
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


def connect_google_account(
    user_id: str,
    credentials: Credentials,
    provider_email: str,
    provider_account_id: str,
) -> CalendarAccountResponse:
    # Upsert calendar_accounts row
    upsert_result = (
        service_client.table("calendar_accounts")
        .upsert(
            {
                "user_id": user_id,
                "provider": "google",
                "provider_email": provider_email,
                "provider_account_id": provider_account_id,
                "credentials": {
                    "access_token": credentials.token,
                    "refresh_token": credentials.refresh_token,
                },
            },
            on_conflict="user_id,provider,provider_account_id",
        )
        .execute()
    )
    account_row = upsert_result.data[0]
    account_id = account_row["id"]

    # Fetch calendars from Google
    try:
        cal_service = build("calendar", "v3", credentials=credentials)
        calendar_list = cal_service.calendarList().list().execute()
        items = calendar_list.get("items", [])
    except Exception as exc:
        logger.error("Failed to fetch Google calendar list: %s", exc)
        items = []

    # Upsert each calendar source
    sources = []
    for item in items:
        cal_id = item["id"]
        is_primary = cal_id == provider_email
        source_data = {
            "account_id": account_id,
            "calendar_id": cal_id,
            "calendar_name": item.get("summary", cal_id),
            "is_enabled": True,
            "is_write_calendar": is_primary,
            "color": item.get("backgroundColor"),
        }
        source_result = (
            service_client.table("calendar_sources")
            .upsert(source_data, on_conflict="account_id,calendar_id")
            .execute()
        )
        sources.append(CalendarSourceResponse(**source_result.data[0]))

    return CalendarAccountResponse(**account_row, sources=sources)


def disconnect_account(account_id: str, user_id: str) -> bool:
    result = (
        service_client.table("calendar_accounts")
        .select("id")
        .eq("id", account_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        return False
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


def get_credentials_for_account(account_id: str) -> Optional[Credentials]:
    result = (
        service_client.table("calendar_accounts")
        .select("credentials")
        .eq("id", account_id)
        .execute()
    )
    if not result.data:
        return None
    creds_data = result.data[0].get("credentials") or {}
    return Credentials(
        token=creds_data.get("access_token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def _source_from_row(row: dict) -> CalendarSourceResponse:
    return CalendarSourceResponse(
        id=row["id"],
        account_id=row["account_id"],
        calendar_id=row["calendar_id"],
        calendar_name=row["calendar_name"],
        is_enabled=row["is_enabled"],
        is_write_calendar=row["is_write_calendar"],
        color=row.get("color"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )
