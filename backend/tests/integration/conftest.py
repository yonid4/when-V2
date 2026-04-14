"""
Integration test fixtures.

These tests hit the real hosted Supabase database. Each test function gets
fully isolated users that are deleted (cascaded) in teardown. No mocking.

Design rules:
- All test emails use the `@test.invalid` TLD — invalid by RFC, guaranteed
  never to collide with real users.
- All cleanup goes through `service_client.auth.admin.delete_user()`.
  Deleting the auth.users row cascades to profiles, calendar_accounts,
  calendar_sources, busy_slots, notifications via FK constraints.
- If a test creates events or other non-user-owned rows, it must delete them
  explicitly before deleting the user (FK order matters).
"""

import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass as _dataclass

import pytest
from jose import jwt

from app.config import settings
from app.utils.supabase import get_authed_client, service_client


# ─── User helper ─────────────────────────────────────────────────────────────

@_dataclass
class IntegrationUser:
    id: str
    email: str
    token: str

    @property
    def auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    @property
    def db(self):
        """Return a Supabase client scoped to this user (respects RLS)."""
        return get_authed_client(self.token)


def _create_test_user(full_name: str) -> IntegrationUser:
    """Create a real auth user + profile row. Returns a IntegrationUser."""
    email = f"itest-{uuid.uuid4().hex[:10]}@test.invalid"
    result = service_client.auth.admin.create_user({
        "email": email,
        "password": "integration-test-pw",
        "email_confirm": True,
    })
    user_id = result.user.id
    service_client.table("profiles").insert({
        "id": user_id,
        "email_address": email,
        "full_name": full_name,
    }).execute()
    token = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "role": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return IntegrationUser(id=user_id, email=email, token=token)


def _delete_test_user(user: IntegrationUser) -> None:
    """Delete the auth user — cascades to profile and all owned rows."""
    import logging
    try:
        service_client.auth.admin.delete_user(user.id)
    except Exception as exc:
        logging.warning("Failed to delete test user %s: %s", user.id, exc)


# ─── Pytest fixtures ─────────────────────────────────────────────────────────

@pytest.fixture()
def alice() -> IntegrationUser:
    user = _create_test_user("Alice Integration")
    yield user
    _delete_test_user(user)


@pytest.fixture()
def bob() -> IntegrationUser:
    user = _create_test_user("Bob Integration")
    yield user
    _delete_test_user(user)


@pytest.fixture()
def alice_with_calendar(alice: IntegrationUser):
    """Alice + a connected calendar account with two calendar sources."""
    acct = service_client.table("calendar_accounts").insert({
        "user_id": alice.id,
        "provider": "google",
        "provider_email": alice.email,
        "provider_account_id": f"gaid-{uuid.uuid4().hex[:8]}",
        "credentials": {},
    }).execute().data[0]

    src1 = service_client.table("calendar_sources").insert({
        "account_id": acct["id"],
        "calendar_id": "primary",
        "calendar_name": "Primary",
        "is_enabled": True,
        "is_write_calendar": True,
    }).execute().data[0]

    src2 = service_client.table("calendar_sources").insert({
        "account_id": acct["id"],
        "calendar_id": "work",
        "calendar_name": "Work",
        "is_enabled": True,
        "is_write_calendar": False,
    }).execute().data[0]

    yield alice, acct, src1, src2
    # alice fixture teardown deletes the auth user, which cascades to calendar_accounts
    # and then calendar_sources and busy_slots — no explicit cleanup needed here
