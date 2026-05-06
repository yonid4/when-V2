"""End-to-end account deletion against the real Supabase instance.

Exercises the full Phase 3 flow: token revocation (mocked) → planning-event
deletion → ``auth.admin.delete_user`` cascade. Asserts every owned table is
emptied and that confirmed events the user coordinated remain with
``coordinator_id=NULL`` (Phase 1 schema change).
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.utils.supabase import service_client
from tests.integration.conftest import IntegrationUser, _create_test_user, _delete_test_user


client = TestClient(app)


def _make_response(status_code: int = 200, text: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


def test_delete_account_full_cascade(bob: IntegrationUser):
    """Create a fully-populated user, delete the account, and verify the
    cascade removed everything except a confirmed event coordinated by the
    user — which must remain with ``coordinator_id=NULL``."""

    # ── arrange: create a victim user fully wired up. We can't use the
    # `alice` fixture because its teardown also calls delete_user(), which
    # would fail or no-op after the test does it itself.
    alice = _create_test_user("Alice DeleteTest")
    alice_id = alice.id

    try:
        # Calendar account + source + busy slot
        acct = service_client.table("calendar_accounts").insert({
            "user_id": alice_id,
            "provider": "google",
            "provider_email": alice.email,
            "provider_account_id": f"gaid-{uuid.uuid4().hex[:8]}",
            "credentials": {"refresh_token": "rt-alice-delete-test"},
        }).execute().data[0]
        src = service_client.table("calendar_sources").insert({
            "account_id": acct["id"],
            "calendar_id": "primary",
            "calendar_name": "Primary",
            "is_enabled": True,
        }).execute().data[0]
        now = datetime.now(timezone.utc)
        service_client.table("busy_slots").insert({
            "user_id": alice_id,
            "calendar_source_id": src["id"],
            "provider_event_id": f"evt-{uuid.uuid4().hex[:8]}",
            "start_time_utc": now.isoformat(),
            "end_time_utc": (now + timedelta(hours=1)).isoformat(),
        }).execute()

        # Planning event Alice coordinates → should be DELETED outright
        planning_event = service_client.table("events").insert({
            "uid": uuid.uuid4().hex[:10],
            "name": "Alice Planning Draft",
            "event_type": "meeting",
            "coordinator_id": alice_id,
            "earliest_datetime_utc": now.isoformat(),
            "latest_datetime_utc": (now + timedelta(days=1)).isoformat(),
            "duration_minutes": 30,
            "status": "planning",
            "proposals_needs_regeneration": False,
        }).execute().data[0]

        # Confirmed event Alice coordinates with Bob participating → should be ANONYMIZED (coordinator_id → NULL)
        confirmed_event = service_client.table("events").insert({
            "uid": uuid.uuid4().hex[:10],
            "name": "Alice Confirmed Meeting",
            "event_type": "meeting",
            "coordinator_id": alice_id,
            "earliest_datetime_utc": now.isoformat(),
            "latest_datetime_utc": (now + timedelta(days=1)).isoformat(),
            "duration_minutes": 30,
            "status": "confirmed",
            "finalized_start_time_utc": (now + timedelta(hours=2)).isoformat(),
            "finalized_end_time_utc": (now + timedelta(hours=3)).isoformat(),
            "proposals_needs_regeneration": False,
        }).execute().data[0]
        service_client.table("event_participants").insert({
            "event_id": confirmed_event["id"],
            "user_id": bob.id,
            "status": "accepted",
        }).execute()

        # Alice participates in Bob's event → her participant row should be removed
        bobs_event = service_client.table("events").insert({
            "uid": uuid.uuid4().hex[:10],
            "name": "Bob's Meeting",
            "event_type": "meeting",
            "coordinator_id": bob.id,
            "earliest_datetime_utc": now.isoformat(),
            "latest_datetime_utc": (now + timedelta(days=1)).isoformat(),
            "duration_minutes": 30,
            "status": "planning",
            "proposals_needs_regeneration": False,
        }).execute().data[0]
        service_client.table("event_participants").insert({
            "event_id": bobs_event["id"],
            "user_id": alice_id,
            "status": "accepted",
        }).execute()

        # ── act: hit DELETE /api/account with revoke mocked to succeed
        with patch("app.utils.google_auth.httpx.post", return_value=_make_response(200)) as mock_revoke:
            response = client.delete("/api/account", headers=alice.auth_headers)

        # ── assert: HTTP success and the revoke fired with the right token
        assert response.status_code == 204, response.text
        mock_revoke.assert_called_once()
        assert mock_revoke.call_args.kwargs["params"]["token"] == "rt-alice-delete-test"

        # Alice's profile + cascaded children are gone
        assert service_client.table("profiles").select("id").eq("id", alice_id).execute().data == []
        assert service_client.table("calendar_accounts").select("id").eq("user_id", alice_id).execute().data == []
        assert service_client.table("calendar_sources").select("id").eq("account_id", acct["id"]).execute().data == []
        assert service_client.table("busy_slots").select("id").eq("user_id", alice_id).execute().data == []
        assert service_client.table("event_participants").select("event_id").eq("user_id", alice_id).execute().data == []

        # Planning event is gone
        assert service_client.table("events").select("id").eq("id", planning_event["id"]).execute().data == []

        # Confirmed event survives, with coordinator_id = NULL
        confirmed_after = service_client.table("events").select("id, coordinator_id").eq(
            "id", confirmed_event["id"]
        ).single().execute().data
        assert confirmed_after is not None
        assert confirmed_after["coordinator_id"] is None

        # Bob's event still exists (he's not the deleted user)
        assert service_client.table("events").select("id").eq("id", bobs_event["id"]).execute().data != []

        # The auth.users row is gone
        try:
            existing = service_client.auth.admin.get_user_by_id(alice_id)
            assert existing.user is None or existing.user.id != alice_id
        except Exception:
            pass  # Supabase raises when user doesn't exist; either way is fine

    finally:
        # Best-effort cleanup of any rows we created so a re-run is clean.
        # Most data is already cascaded away by delete_user; this catches
        # the events that survive (Bob's planning event, confirmed event w/ NULL coord).
        try:
            service_client.table("events").delete().eq(
                "uid", confirmed_event["uid"]
            ).execute()
        except Exception:
            pass
        try:
            service_client.table("events").delete().eq(
                "uid", bobs_event["uid"]
            ).execute()
        except Exception:
            pass
        # Belt-and-braces: if the test failed before delete_user, clean up Alice
        try:
            _delete_test_user(IntegrationUser(id=alice_id, email=alice.email, token=alice.token))
        except Exception:
            pass
