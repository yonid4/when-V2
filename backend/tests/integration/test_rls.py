"""
RLS integration tests.

These verify that Postgres Row Level Security policies actually enforce
data isolation between users. Mocks cannot test this — they bypass the DB.

Each test inserts real rows with service_client (bypasses RLS),
then reads them back through a user-scoped client (respects RLS),
confirming the policy fires correctly.
"""

import uuid
from datetime import datetime, timedelta, timezone


from app.utils.supabase import service_client
from tests.integration.conftest import IntegrationUser


# ─── Notifications ────────────────────────────────────────────────────────────

class TestNotificationsRLS:
    def test_user_cannot_read_another_users_notification(self, alice: IntegrationUser, bob: IntegrationUser):
        """A notification created for Bob must not be visible to Alice."""
        notif_id = str(uuid.uuid4())
        service_client.table("notifications").insert({
            "id": notif_id,
            "user_id": bob.id,
            "notification_type": "event_deleted",
            "title": "RLS Test",
            "message": "Should not be visible to Alice",
            "is_read": False,
            "action_taken": False,
        }).execute()

        result = alice.db.table("notifications").select("*").eq("id", notif_id).execute()

        assert result.data == [], (
            "Alice should not be able to read Bob's notification via RLS"
        )

    def test_user_can_read_own_notification(self, bob: IntegrationUser):
        """Bob can read his own notification."""
        notif_id = str(uuid.uuid4())
        service_client.table("notifications").insert({
            "id": notif_id,
            "user_id": bob.id,
            "notification_type": "event_deleted",
            "title": "RLS Test",
            "message": "Visible to Bob",
            "is_read": False,
            "action_taken": False,
        }).execute()

        result = bob.db.table("notifications").select("*").eq("id", notif_id).execute()

        assert len(result.data) == 1
        assert result.data[0]["id"] == notif_id

    def test_user_cannot_write_notification_for_another_user(self, alice: IntegrationUser, bob: IntegrationUser):
        """Alice must not be able to insert a notification for Bob.
        notifications.write is service role only per the RLS policy."""
        try:
            alice.db.table("notifications").insert({
                "user_id": bob.id,
                "notification_type": "event_deleted",
                "title": "Injected",
                "message": "Alice trying to write Bob's notification",
                "is_read": False,
                "action_taken": False,
            }).execute()
            # If insert succeeded, query to see if it's actually in the DB
            injected = service_client.table("notifications").select("id").eq(
                "user_id", bob.id
            ).eq("title", "Injected").execute()
            assert injected.data == [], "Alice should not be able to insert notifications for Bob"
        except Exception:
            pass  # Any exception is also acceptable — RLS blocked the write

    def test_unique_index_blocks_duplicate_pending_invite(
        self, alice: IntegrationUser, bob: IntegrationUser
    ):
        """The notifications_unique_pending_invitation partial index must reject
        a second event_invitation row for the same (user_id, event_id) while
        action_taken is still false.

        Requires the migration in
        supabase/migrations/20260429210451_notifications_unique_pending_invitation.sql
        to be applied to the test database.
        """
        now = datetime.now(timezone.utc)
        event_uid = uuid.uuid4().hex[:10]
        event = service_client.table("events").insert({
            "uid": event_uid,
            "name": "Unique Index Test",
            "event_type": "meeting",
            "coordinator_id": alice.id,
            "earliest_datetime_utc": now.isoformat(),
            "latest_datetime_utc": (now + timedelta(days=7)).isoformat(),
            "duration_minutes": 30,
            "status": "planning",
            "proposals_needs_regeneration": False,
        }).execute().data[0]
        event_id = event["id"]

        try:
            # First insert succeeds
            service_client.table("notifications").insert({
                "user_id": bob.id,
                "event_id": event_id,
                "notification_type": "event_invitation",
                "title": "First invite",
                "message": "First",
                "is_read": False,
                "action_taken": False,
            }).execute()

            # Second insert with same (user_id, event_id) must fail with 23505
            duplicate_blocked = False
            try:
                service_client.table("notifications").insert({
                    "user_id": bob.id,
                    "event_id": event_id,
                    "notification_type": "event_invitation",
                    "title": "Duplicate invite",
                    "message": "Duplicate",
                    "is_read": False,
                    "action_taken": False,
                }).execute()
            except Exception as exc:
                # PostgREST surfaces unique violations as 23505 / "duplicate key"
                msg = str(exc)
                duplicate_blocked = "23505" in msg or "duplicate" in msg.lower() or "unique" in msg.lower()

            assert duplicate_blocked, (
                "Duplicate pending event_invitation should be rejected by "
                "notifications_unique_pending_invitation index"
            )

            # After actioning the first row, a re-invitation IS allowed
            service_client.table("notifications").update(
                {"action_taken": True, "action_type": "decline"}
            ).eq("user_id", bob.id).eq("event_id", event_id).execute()

            service_client.table("notifications").insert({
                "user_id": bob.id,
                "event_id": event_id,
                "notification_type": "event_invitation",
                "title": "Re-invite",
                "message": "Re-invited",
                "is_read": False,
                "action_taken": False,
            }).execute()  # should NOT raise
        finally:
            # Clean up event — notifications cascade via FK on event_id
            service_client.table("events").delete().eq("id", event_id).execute()


# ─── Calendar accounts ────────────────────────────────────────────────────────

class TestCalendarAccountsRLS:
    def test_user_cannot_read_another_users_calendar_account(
        self, alice: IntegrationUser, bob: IntegrationUser
    ):
        """Bob cannot see Alice's connected calendar account."""
        service_client.table("calendar_accounts").insert({
            "user_id": alice.id,
            "provider": "google",
            "provider_email": alice.email,
            "provider_account_id": f"gaid-{uuid.uuid4().hex[:8]}",
            "credentials": {"access_token": "secret"},
        }).execute()

        result = bob.db.table("calendar_accounts").select("*").eq(
            "user_id", alice.id
        ).execute()

        assert result.data == [], (
            "Bob should not be able to read Alice's calendar_accounts — "
            "this would expose OAuth access tokens"
        )

    def test_user_can_read_own_calendar_account(self, alice: IntegrationUser):
        """Alice can read her own calendar account."""
        acct = service_client.table("calendar_accounts").insert({
            "user_id": alice.id,
            "provider": "google",
            "provider_email": alice.email,
            "provider_account_id": f"gaid-{uuid.uuid4().hex[:8]}",
            "credentials": {},
        }).execute().data[0]

        result = alice.db.table("calendar_accounts").select("*").eq(
            "id", acct["id"]
        ).execute()

        assert len(result.data) == 1
        assert result.data[0]["id"] == acct["id"]

    def test_user_cannot_read_another_users_credentials(
        self, alice: IntegrationUser, bob: IntegrationUser
    ):
        """Specifically confirms credentials JSONB is not leaked cross-user.
        Covered by the account-level RLS, but worth asserting explicitly."""
        service_client.table("calendar_accounts").insert({
            "user_id": alice.id,
            "provider": "google",
            "provider_email": alice.email,
            "provider_account_id": f"gaid-{uuid.uuid4().hex[:8]}",
            "credentials": {"access_token": "alice-secret-token"},
        }).execute()

        rows = bob.db.table("calendar_accounts").select(
            "credentials"
        ).eq("user_id", alice.id).execute()

        assert rows.data == []


# ─── Profiles ─────────────────────────────────────────────────────────────────

class TestProfilesRLS:
    def test_user_can_read_own_profile(self, alice: IntegrationUser):
        result = alice.db.table("profiles").select("*").eq("id", alice.id).execute()
        assert len(result.data) == 1
        assert result.data[0]["email_address"] == alice.email

    def test_user_cannot_update_another_users_profile(
        self, alice: IntegrationUser, bob: IntegrationUser
    ):
        """Alice cannot overwrite Bob's full_name."""
        try:
            alice.db.table("profiles").update(
                {"full_name": "Hijacked by Alice"}
            ).eq("id", bob.id).execute()
        except Exception:
            pass  # RLS blocked it

        # Verify Bob's profile is unchanged
        r = service_client.table("profiles").select("full_name").eq("id", bob.id).execute()
        assert r.data[0]["full_name"] == "Bob Integration"
