"""
busy_slots integration tests.

Tests the behaviors that mocks cannot verify:
- Upsert deduplication on (provider_event_id, calendar_source_id)
- Cascade delete: removing a calendar_account deletes sources and busy_slots
- Cascade delete: removing a calendar_source deletes its busy_slots

busy_slots.user_id references auth.users(id), not profiles(id).
All writes must use service_client (RLS blocks anon writes).
"""

import uuid
from datetime import datetime, timezone


from app.utils.supabase import service_client
from tests.integration.conftest import IntegrationUser


def _insert_account_and_source(user: IntegrationUser) -> tuple[dict, dict]:
    """Helper: insert a calendar_account + calendar_source for a user."""
    acct = service_client.table("calendar_accounts").insert({
        "user_id": user.id,
        "provider": "google",
        "provider_email": user.email,
        "provider_account_id": f"gaid-{uuid.uuid4().hex[:8]}",
        "credentials": {},
    }).execute().data[0]

    src = service_client.table("calendar_sources").insert({
        "account_id": acct["id"],
        "calendar_id": "primary",
        "calendar_name": "Primary",
        "is_enabled": True,
        "is_write_calendar": True,
    }).execute().data[0]

    return acct, src


def _make_slot(user_id: str, source_id: str, provider_event_id: str, **overrides) -> dict:
    return {
        "user_id": user_id,
        "calendar_source_id": source_id,
        "provider_event_id": provider_event_id,
        "start_time_utc": "2026-05-01T09:00:00Z",
        "end_time_utc": "2026-05-01T10:00:00Z",
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
        **overrides,
    }


class TestBusySlotUpsertDedup:
    def test_upserting_same_provider_event_id_does_not_create_duplicate(self, alice: IntegrationUser):
        """Re-syncing the same Google event ID updates the existing row, not creates a new one.
        This is the core correctness guarantee of the sync service."""
        _, src = _insert_account_and_source(alice)
        event_id = f"google-event-{uuid.uuid4().hex[:8]}"
        slot = _make_slot(alice.id, src["id"], event_id)

        service_client.table("busy_slots").upsert(
            slot, on_conflict="provider_event_id,calendar_source_id"
        ).execute()
        service_client.table("busy_slots").upsert(
            slot, on_conflict="provider_event_id,calendar_source_id"
        ).execute()

        rows = service_client.table("busy_slots").select("id").eq(
            "calendar_source_id", src["id"]
        ).eq("provider_event_id", event_id).execute()

        assert len(rows.data) == 1, (
            "Two upserts with the same provider_event_id+calendar_source_id "
            "must produce exactly one row"
        )

    def test_upsert_updates_time_on_resync(self, alice: IntegrationUser):
        """When the same event's time changes, re-syncing updates start/end times."""
        _, src = _insert_account_and_source(alice)
        event_id = f"google-event-{uuid.uuid4().hex[:8]}"

        service_client.table("busy_slots").upsert(
            _make_slot(alice.id, src["id"], event_id, start_time_utc="2026-05-01T09:00:00Z"),
            on_conflict="provider_event_id,calendar_source_id",
        ).execute()
        service_client.table("busy_slots").upsert(
            _make_slot(alice.id, src["id"], event_id, start_time_utc="2026-05-01T10:00:00Z"),
            on_conflict="provider_event_id,calendar_source_id",
        ).execute()

        rows = service_client.table("busy_slots").select("start_time_utc").eq(
            "calendar_source_id", src["id"]
        ).eq("provider_event_id", event_id).execute()

        assert len(rows.data) == 1
        assert "10:00" in rows.data[0]["start_time_utc"], (
            "Re-upsert should update start_time_utc to the new value"
        )

    def test_different_provider_event_ids_create_separate_rows(self, alice: IntegrationUser):
        """Two distinct Google events → two distinct busy_slot rows."""
        _, src = _insert_account_and_source(alice)

        for i in range(3):
            service_client.table("busy_slots").upsert(
                _make_slot(alice.id, src["id"], f"google-event-unique-{i}"),
                on_conflict="provider_event_id,calendar_source_id",
            ).execute()

        rows = service_client.table("busy_slots").select("id").eq(
            "calendar_source_id", src["id"]
        ).execute()

        assert len(rows.data) == 3


class TestCascadeDeletes:
    def test_deleting_calendar_account_cascades_to_sources_and_busy_slots(
        self, alice: IntegrationUser
    ):
        """Disconnecting an account must remove all sources and all synced busy slots.
        This is what disconnect_account() relies on — no manual cleanup needed."""
        acct, src = _insert_account_and_source(alice)
        event_id = f"google-event-{uuid.uuid4().hex[:8]}"
        service_client.table("busy_slots").upsert(
            _make_slot(alice.id, src["id"], event_id),
            on_conflict="provider_event_id,calendar_source_id",
        ).execute()

        service_client.table("calendar_accounts").delete().eq("id", acct["id"]).execute()

        sources_after = service_client.table("calendar_sources").select("id").eq(
            "account_id", acct["id"]
        ).execute()
        slots_after = service_client.table("busy_slots").select("id").eq(
            "calendar_source_id", src["id"]
        ).execute()

        assert sources_after.data == [], "Sources must be deleted when account is deleted"
        assert slots_after.data == [], "Busy slots must be deleted when account is deleted"

    def test_deleting_calendar_source_cascades_to_busy_slots(self, alice: IntegrationUser):
        """Disabling a specific calendar (deleting the source) removes its busy slots
        without touching other sources on the same account."""
        acct, src = _insert_account_and_source(alice)

        # Add a second source
        src2 = service_client.table("calendar_sources").insert({
            "account_id": acct["id"],
            "calendar_id": "work",
            "calendar_name": "Work",
            "is_enabled": True,
            "is_write_calendar": False,
        }).execute().data[0]

        # Busy slots on both sources
        service_client.table("busy_slots").upsert(
            _make_slot(alice.id, src["id"], f"event-src1-{uuid.uuid4().hex[:6]}"),
            on_conflict="provider_event_id,calendar_source_id",
        ).execute()
        service_client.table("busy_slots").upsert(
            _make_slot(alice.id, src2["id"], f"event-src2-{uuid.uuid4().hex[:6]}"),
            on_conflict="provider_event_id,calendar_source_id",
        ).execute()

        # Delete only src
        service_client.table("calendar_sources").delete().eq("id", src["id"]).execute()

        slots_src1 = service_client.table("busy_slots").select("id").eq(
            "calendar_source_id", src["id"]
        ).execute()
        slots_src2 = service_client.table("busy_slots").select("id").eq(
            "calendar_source_id", src2["id"]
        ).execute()

        assert slots_src1.data == [], "Slots for deleted source must be gone"
        assert len(slots_src2.data) == 1, "Slots for the other source must be untouched"
