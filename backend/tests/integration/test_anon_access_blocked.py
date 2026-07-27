"""
Verify that anonymous (unauthenticated) clients cannot read user data.

Before the privacy hardening migration (20260430000001_privacy_hardening.sql),
six tables had RLS policies allowing anon SELECT on every row. These tests
confirm those policies are gone and the tables are inaccessible without a
valid JWT.
"""

import uuid
from datetime import datetime, timedelta, timezone


from app.utils.supabase import anon_client, service_client
from tests.integration.conftest import IntegrationUser


def _seed_event_for(user: IntegrationUser) -> str:
    """Create a real event coordinated by user. Returns event_id."""
    now = datetime.now(timezone.utc)
    row = service_client.table("events").insert({
        "uid": uuid.uuid4().hex[:10],
        "name": "Anon Block Test",
        "event_type": "meeting",
        "coordinator_id": user.id,
        "earliest_datetime_utc": now.isoformat(),
        "latest_datetime_utc": (now + timedelta(days=1)).isoformat(),
        "duration_minutes": 30,
        "status": "planning",
        "proposals_needs_regeneration": False,
    }).execute().data[0]
    return row["id"]


class TestAnonAccessBlocked:
    """Each previously-readable table must now return [] for anon clients."""

    def test_anon_cannot_read_busy_slots(self, alice: IntegrationUser):
        # Need an account+source first because busy_slots FK to calendar_sources
        acct = service_client.table("calendar_accounts").insert({
            "user_id": alice.id,
            "provider": "google",
            "provider_email": alice.email,
            "provider_account_id": f"gaid-{uuid.uuid4().hex[:8]}",
            "credentials": {},
        }).execute().data[0]
        src = service_client.table("calendar_sources").insert({
            "account_id": acct["id"],
            "calendar_id": "primary",
            "calendar_name": "Primary",
            "is_enabled": True,
        }).execute().data[0]
        now = datetime.now(timezone.utc)
        service_client.table("busy_slots").insert({
            "user_id": alice.id,
            "calendar_source_id": src["id"],
            "provider_event_id": f"evt-{uuid.uuid4().hex[:8]}",
            "start_time_utc": now.isoformat(),
            "end_time_utc": (now + timedelta(hours=1)).isoformat(),
        }).execute()

        result = anon_client.table("busy_slots").select("*").eq("user_id", alice.id).execute()
        assert result.data == [], "anon must not read busy_slots"

    def test_anon_cannot_read_events(self, alice: IntegrationUser):
        event_id = _seed_event_for(alice)
        try:
            result = anon_client.table("events").select("*").eq("id", event_id).execute()
            assert result.data == [], "anon must not read events"
        finally:
            service_client.table("events").delete().eq("id", event_id).execute()

    def test_anon_cannot_read_event_participants(self, alice: IntegrationUser):
        event_id = _seed_event_for(alice)
        try:
            service_client.table("event_participants").insert({
                "event_id": event_id,
                "user_id": alice.id,
                "status": "accepted",
            }).execute()
            result = anon_client.table("event_participants").select("*").eq("event_id", event_id).execute()
            assert result.data == [], "anon must not read event_participants"
        finally:
            service_client.table("events").delete().eq("id", event_id).execute()

    def test_anon_cannot_read_notifications(self, alice: IntegrationUser):
        service_client.table("notifications").insert({
            "user_id": alice.id,
            "notification_type": "event_deleted",
            "title": "Anon Block",
            "message": "x",
            "is_read": False,
            "action_taken": False,
        }).execute()
        result = anon_client.table("notifications").select("*").eq("user_id", alice.id).execute()
        assert result.data == [], "anon must not read notifications"

    def test_anon_cannot_read_preferred_slots(self, alice: IntegrationUser):
        event_id = _seed_event_for(alice)
        try:
            service_client.table("event_participants").insert({
                "event_id": event_id, "user_id": alice.id, "status": "accepted",
            }).execute()
            now = datetime.now(timezone.utc)
            service_client.table("preferred_slots").insert({
                "user_id": alice.id,
                "event_id": event_id,
                "start_time_utc": now.isoformat(),
                "end_time_utc": (now + timedelta(hours=1)).isoformat(),
            }).execute()
            result = anon_client.table("preferred_slots").select("*").eq("event_id", event_id).execute()
            assert result.data == [], "anon must not read preferred_slots"
        finally:
            service_client.table("events").delete().eq("id", event_id).execute()

    def test_anon_cannot_read_proposed_time_notes(self, alice: IntegrationUser):
        event_id = _seed_event_for(alice)
        try:
            now = datetime.now(timezone.utc)
            pt = service_client.table("proposed_times").insert({
                "event_id": event_id,
                "start_time_utc": now.isoformat(),
                "end_time_utc": (now + timedelta(minutes=30)).isoformat(),
                "rank": 1,
            }).execute().data[0]
            event_uid = service_client.table("events").select("uid").eq("id", event_id).single().execute().data["uid"]
            service_client.table("proposed_time_notes").insert({
                "proposed_time_id": pt["id"],
                "user_id": alice.id,
                "content": "anon-block test",
                "event_uid": event_uid,
            }).execute()
            result = anon_client.table("proposed_time_notes").select("*").eq("event_uid", event_uid).execute()
            assert result.data == [], "anon must not read proposed_time_notes"
        finally:
            service_client.table("events").delete().eq("id", event_id).execute()


class TestAuthenticatedAccessStillWorks:
    """Confirm scoped, authenticated reads continue to function."""

    def test_authenticated_user_can_read_own_busy_slots(self, alice: IntegrationUser):
        acct = service_client.table("calendar_accounts").insert({
            "user_id": alice.id,
            "provider": "google",
            "provider_email": alice.email,
            "provider_account_id": f"gaid-{uuid.uuid4().hex[:8]}",
            "credentials": {},
        }).execute().data[0]
        src = service_client.table("calendar_sources").insert({
            "account_id": acct["id"],
            "calendar_id": "primary",
            "calendar_name": "Primary",
            "is_enabled": True,
        }).execute().data[0]
        now = datetime.now(timezone.utc)
        service_client.table("busy_slots").insert({
            "user_id": alice.id,
            "calendar_source_id": src["id"],
            "provider_event_id": f"evt-{uuid.uuid4().hex[:8]}",
            "start_time_utc": now.isoformat(),
            "end_time_utc": (now + timedelta(hours=1)).isoformat(),
        }).execute()

        result = alice.db.table("busy_slots").select("*").eq("user_id", alice.id).execute()
        assert len(result.data) >= 1

    def test_authenticated_user_can_read_own_notifications(self, alice: IntegrationUser):
        service_client.table("notifications").insert({
            "user_id": alice.id,
            "notification_type": "event_deleted",
            "title": "Authed Read",
            "message": "x",
            "is_read": False,
            "action_taken": False,
        }).execute()
        result = alice.db.table("notifications").select("*").eq("user_id", alice.id).execute()
        assert len(result.data) >= 1
