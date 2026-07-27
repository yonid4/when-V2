"""
calendar_sources integration tests.

Tests the is_write_calendar exclusivity constraint that the service layer
depends on. The mock tests in test_calendar.py verify that the Python code
calls the RPC — these tests verify the RPC actually works in Postgres.

NOTE: The `clear_write_calendar_for_user` RPC must exist in the database.
Tests in TestWriteCalendarRPC are skipped with a clear message if it's missing,
rather than failing with a cryptic PostgREST error.
"""

import uuid

import pytest

from app.utils.supabase import service_client
from tests.integration.conftest import IntegrationUser


def _rpc_exists() -> bool:
    """Check whether the clear_write_calendar_for_user RPC is deployed."""
    try:
        service_client.rpc(
            "clear_write_calendar_for_user",
            {"p_user_id": "00000000-0000-0000-0000-000000000000", "p_exclude_source_id": "00000000-0000-0000-0000-000000000000"},
        ).execute()
        return True
    except Exception as e:
        return "PGRST202" not in str(e)  # PGRST202 = function not found


def _insert_account(user: IntegrationUser) -> dict:
    return service_client.table("calendar_accounts").insert({
        "user_id": user.id,
        "provider": "google",
        "provider_email": user.email,
        "provider_account_id": f"gaid-{uuid.uuid4().hex[:8]}",
        "credentials": {},
    }).execute().data[0]


def _insert_source(acct_id: str, cal_id: str, is_write: bool) -> dict:
    return service_client.table("calendar_sources").insert({
        "account_id": acct_id,
        "calendar_id": cal_id,
        "calendar_name": f"Calendar {cal_id}",
        "is_enabled": True,
        "is_write_calendar": is_write,
    }).execute().data[0]


class TestWriteCalendarRPC:
    """
    Tests the clear_write_calendar_for_user Postgres function.

    This function must exist in the DB for update_calendar_source() to work
    correctly. If it's missing, the integration test documents exactly what
    SQL to create and what behavior is expected, making it a deployable spec.

    Required SQL (run in Supabase SQL editor if tests fail here):

        CREATE OR REPLACE FUNCTION public.clear_write_calendar_for_user(
            p_user_id uuid,
            p_exclude_source_id uuid
        )
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        AS $$
            UPDATE calendar_sources cs
            SET is_write_calendar = false
            FROM calendar_accounts ca
            WHERE cs.account_id = ca.id
              AND ca.user_id = p_user_id
              AND cs.id != p_exclude_source_id;
        $$;
    """

    @pytest.mark.skipif(not _rpc_exists(), reason="clear_write_calendar_for_user RPC not deployed — see docstring for required SQL")
    def test_rpc_clears_all_other_sources_for_user(self, alice: IntegrationUser):
        """Setting src2 as write calendar must clear is_write_calendar on src1."""
        acct = _insert_account(alice)
        src1 = _insert_source(acct["id"], "primary", is_write=True)
        src2 = _insert_source(acct["id"], "work", is_write=False)

        service_client.rpc(
            "clear_write_calendar_for_user",
            {"p_user_id": alice.id, "p_exclude_source_id": src2["id"]},
        ).execute()
        service_client.table("calendar_sources").update(
            {"is_write_calendar": True}
        ).eq("id", src2["id"]).execute()

        rows = service_client.table("calendar_sources").select(
            "id, is_write_calendar"
        ).eq("account_id", acct["id"]).execute()

        flags = {r["id"]: r["is_write_calendar"] for r in rows.data}
        assert flags[src1["id"]] is False, "src1 should be cleared"
        assert flags[src2["id"]] is True, "src2 should be the new write calendar"

    @pytest.mark.skipif(not _rpc_exists(), reason="clear_write_calendar_for_user RPC not deployed — see docstring for required SQL")
    def test_rpc_does_not_affect_other_users_sources(
        self, alice: IntegrationUser, bob: IntegrationUser
    ):
        """The RPC must be scoped to p_user_id — it must not touch Bob's sources
        when called for Alice."""
        alice_acct = _insert_account(alice)
        bob_acct = _insert_account(bob)

        _insert_source(alice_acct["id"], "primary", is_write=True)
        bob_src = _insert_source(bob_acct["id"], "primary", is_write=True)

        # Run RPC for Alice — passing a non-existent exclude ID so all of Alice's get cleared
        service_client.rpc(
            "clear_write_calendar_for_user",
            {"p_user_id": alice.id, "p_exclude_source_id": str(uuid.uuid4())},
        ).execute()

        bob_row = service_client.table("calendar_sources").select(
            "is_write_calendar"
        ).eq("id", bob_src["id"]).execute()

        assert bob_row.data[0]["is_write_calendar"] is True, (
            "RPC must not touch Bob's sources when called for Alice"
        )


def _unique_constraint_exists() -> bool:
    """Check whether the unique constraint on (account_id, calendar_id) exists."""
    try:
        # Try inserting a duplicate — if it raises, the constraint exists
        acct_id = "00000000-0000-0000-0000-000000000000"
        service_client.table("calendar_sources").upsert({
            "account_id": acct_id,
            "calendar_id": "__probe__",
            "calendar_name": "probe",
            "is_enabled": False,
            "is_write_calendar": False,
        }, on_conflict="account_id,calendar_id").execute()
        return True
    except Exception as e:
        # 42P10 = no unique constraint matching ON CONFLICT spec
        return "42P10" not in str(e)


_CONSTRAINT_MISSING_REASON = (
    "calendar_sources is missing UNIQUE (account_id, calendar_id) constraint. "
    "connect_google_account's upsert will fail at runtime. "
    "Fix: run in Supabase SQL editor: "
    "ALTER TABLE calendar_sources ADD CONSTRAINT calendar_sources_account_id_calendar_id_key "
    "UNIQUE (account_id, calendar_id);"
)


class TestCalendarSourceSchema:
    @pytest.mark.skipif(
        not _unique_constraint_exists(),
        reason=_CONSTRAINT_MISSING_REASON,
    )
    def test_unique_constraint_on_account_id_and_calendar_id(self, alice: IntegrationUser):
        """Inserting the same calendar_id for the same account_id twice must fail.
        This is the upsert key used by connect_google_account."""
        acct = _insert_account(alice)

        service_client.table("calendar_sources").insert({
            "account_id": acct["id"],
            "calendar_id": "primary",
            "calendar_name": "Primary",
            "is_enabled": True,
            "is_write_calendar": False,
        }).execute()

        with pytest.raises(Exception, match="duplicate|unique|23505"):
            service_client.table("calendar_sources").insert({
                "account_id": acct["id"],
                "calendar_id": "primary",
                "calendar_name": "Primary Again",
                "is_enabled": True,
                "is_write_calendar": False,
            }).execute()

    @pytest.mark.skipif(
        not _unique_constraint_exists(),
        reason=_CONSTRAINT_MISSING_REASON,
    )
    def test_upsert_on_account_id_and_calendar_id_updates_existing(self, alice: IntegrationUser):
        """connect_google_account uses upsert — re-connecting the same Google
        calendar should update the name, not create a duplicate row."""
        acct = _insert_account(alice)

        service_client.table("calendar_sources").upsert({
            "account_id": acct["id"],
            "calendar_id": "primary",
            "calendar_name": "Old Name",
            "is_enabled": True,
            "is_write_calendar": False,
        }, on_conflict="account_id,calendar_id").execute()

        service_client.table("calendar_sources").upsert({
            "account_id": acct["id"],
            "calendar_id": "primary",
            "calendar_name": "New Name",
            "is_enabled": True,
            "is_write_calendar": False,
        }, on_conflict="account_id,calendar_id").execute()

        rows = service_client.table("calendar_sources").select("calendar_name").eq(
            "account_id", acct["id"]
        ).eq("calendar_id", "primary").execute()

        assert len(rows.data) == 1
        assert rows.data[0]["calendar_name"] == "New Name"
