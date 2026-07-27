"""Sprint 6B/6C — Event finalization tests.

Tests the finalize router and finalize_service with mocked Supabase service_client
and a mocked calendar provider (via ``get_provider``).
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.config import settings

client = TestClient(app)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _auth_headers(user_id: str = "coordinator-uuid-1", email: str = "alice@example.com") -> dict:
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = jwt.encode(
        {"sub": user_id, "email": email, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def _current_user_profile(user_id: str = "coordinator-uuid-1") -> dict:
    return {"id": user_id, "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}


@contextmanager
def _patched_provider(event_id: str = "cal-evt-123", error: Exception | None = None, capture: dict | None = None):
    """Patch finalize_service.get_provider with a fake provider whose
    create_event optionally captures the EventPayload or raises ``error``."""
    prov = MagicMock()

    def _create(tokens, calendar_id, payload):
        if capture is not None:
            capture["payload"] = payload
            capture["calendar_id"] = calendar_id
            capture["tokens"] = tokens
        if error is not None:
            raise error
        return event_id

    prov.create_event.side_effect = _create
    with patch("app.services.finalize_service.get_provider", return_value=prov):
        yield prov


def _make_event_row(**overrides) -> dict:
    defaults = {
        "id": "event-db-id-1",
        "uid": "event-uid-1",
        "name": "Team Lunch",
        "coordinator_id": "coordinator-uuid-1",
        "status": "planning",
        "finalized_start_time_utc": None,
        "finalized_end_time_utc": None,
        "calendar_event_id": None,
    }
    return {**defaults, **overrides}


def _make_proposed_time_row(**overrides) -> dict:
    defaults = {
        "id": "pt-uuid-1",
        "event_id": "event-db-id-1",
        "start_time_utc": "2026-04-10T12:00:00+00:00",
        "end_time_utc": "2026-04-10T13:00:00+00:00",
    }
    return {**defaults, **overrides}


def _make_write_cal_row(provider: str = "google", **overrides) -> dict:
    """A write calendar source joined with its owning account (id, user_id,
    provider, credentials) — matching the single joined query finalize issues."""
    defaults = {
        "id": "cal-source-1",
        "calendar_id": "primary",
        "calendar_accounts": {
            "id": "cal-account-1",
            "user_id": "coordinator-uuid-1",
            "provider": provider,
            "credentials": {"access_token": "access-tok", "refresh_token": "refresh-tok"},
        },
    }
    return {**defaults, **overrides}


def _make_user_write_cal(user_id: str, calendar_id: str, account_id: str, provider: str = "google") -> dict:
    """A write calendar belonging to an arbitrary user (for multi-participant tests)."""
    return {
        "id": f"src-{account_id}",
        "calendar_id": calendar_id,
        "calendar_accounts": {
            "id": account_id,
            "user_id": user_id,
            "provider": provider,
            "credentials": {"access_token": "at", "refresh_token": "rt"},
        },
    }


def _make_finalize_db(
    event_row: dict,
    proposed_time_row: dict | None = None,
    participants: list[dict] | None = None,
    coordinator_participant: dict | None = None,
    write_cal_rows: list[dict] | None = None,
    updated_event: dict | None = None,
) -> MagicMock:
    """Build a db mock that routes table() calls for finalize_service."""
    participants = participants or []
    write_cal_rows = write_cal_rows or []
    updated_event = updated_event or {**event_row, "status": "confirmed", "calendar_event_id": "cal-evt-123"}

    _coordinator_participant = coordinator_participant or {
        "user_id": "coordinator-uuid-1",
        "profiles": {
            "email_address": "alice@example.com",
            "full_name": "Alice",
            "calendar_accounts": [],
        },
    }

    # Track how many times event_participants is queried so the second call
    # (coordinator lookup) returns the coordinator row.
    _ep_call_count = [0]

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
            # Serves all three conditional updates finalize issues — the claim
            # (.eq(id).eq(status='planning')), the rollback and the final write
            # (.eq(id).eq(status='confirmed')). Non-empty data = claim won.
            tbl.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[updated_event]
            )
        elif name == "proposed_times":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=proposed_time_row
            )
        elif name == "event_participants":
            _ep_call_count[0] += 1
            call_num = _ep_call_count[0]
            if call_num == 1:
                tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=participants
                )
                tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                    data=_coordinator_participant
                )
            else:
                tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                    data=_coordinator_participant
                )
                tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=participants
                )
        elif name == "calendar_sources":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=write_cal_rows
            )
        elif name == "calendar_accounts":
            # Only touched if the provider rotated tokens (tokens.dirty); the fake
            # provider never does, so this is a harmless default.
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "notifications":
            tbl.insert.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    db = MagicMock()
    db.table.side_effect = make_table
    return db


def _make_participant(user_id: str, email: str, google_email: str | None = None) -> dict:
    cal_accounts = []
    if google_email:
        cal_accounts = [{"provider": "google", "provider_email": google_email}]
    return {
        "user_id": user_id,
        "profiles": {
            "email_address": email,
            "full_name": user_id.split("-")[0].capitalize(),
            "calendar_accounts": cal_accounts,
        },
    }


# ─── _pick_attendee_email unit tests ─────────────────────────────────────────

from app.services.finalize_service import _pick_attendee_email


def test_pick_attendee_email_prefers_matching_provider_email():
    """Prefer the provider_email from the account matching the write provider."""
    participant = {
        "profiles": {
            "email_address": "bob@example.com",
            "full_name": "Bob",
            "calendar_accounts": [
                {"provider": "google", "provider_email": "bob@gmail.com"}
            ],
        }
    }
    assert _pick_attendee_email(participant, "google") == "bob@gmail.com"


def test_pick_attendee_email_falls_back_to_profile_email():
    """When no calendar_account exists, fall back to profile email."""
    participant = {
        "profiles": {
            "email_address": "carol@example.com",
            "full_name": "Carol",
            "calendar_accounts": [],
        }
    }
    assert _pick_attendee_email(participant, "google") == "carol@example.com"


def test_pick_attendee_email_no_calendar_accounts_key():
    """When calendar_accounts key is absent entirely, fall back to profile email."""
    participant = {
        "profiles": {
            "email_address": "dave@example.com",
            "full_name": "Dave",
        }
    }
    assert _pick_attendee_email(participant, "google") == "dave@example.com"


def test_pick_attendee_email_uses_other_provider_when_no_match():
    """If no account matches the write provider, use any other connected
    provider_email before falling back to the profile email."""
    participant = {
        "profiles": {
            "email_address": "eve@example.com",
            "full_name": "Eve",
            "calendar_accounts": [
                {"provider": "microsoft", "provider_email": "eve@outlook.com"}
            ],
        }
    }
    # Writing to a Google calendar, attendee only has an Outlook account.
    assert _pick_attendee_email(participant, "google") == "eve@outlook.com"


def test_pick_attendee_email_prefers_write_provider_over_others():
    """With multiple accounts, the one matching the write provider wins."""
    participant = {
        "profiles": {
            "email_address": "frank@example.com",
            "full_name": "Frank",
            "calendar_accounts": [
                {"provider": "google", "provider_email": "frank@gmail.com"},
                {"provider": "microsoft", "provider_email": "frank@outlook.com"},
            ],
        }
    }
    assert _pick_attendee_email(participant, "microsoft") == "frank@outlook.com"
    assert _pick_attendee_email(participant, "google") == "frank@gmail.com"


def test_pick_attendee_email_none_when_no_emails():
    """Returns None when both profile email and calendar accounts are absent."""
    participant = {"profiles": {}}
    assert _pick_attendee_email(participant, "google") is None


# ─── POST /api/events/{uid}/finalize ─────────────────────────────────────────

@patch("app.utils.notifications.service_client")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_success(mock_dep_svc, mock_svc_svc, mock_notif_svc):
    """Coordinator can finalize an event — returns confirmed event row."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        participants=[_make_participant("bob-uuid", "bob@example.com", "bob@gmail.com")],
        write_cal_rows=[_make_write_cal_row()],
    ).table.side_effect

    with _patched_provider() as prov:
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "Looking forward to it!",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    assert prov.create_event.called


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_404_event_not_found(mock_dep_svc, mock_svc_svc):
    """Returns 404 when event does not exist."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=None
            )
        return tbl

    mock_svc_svc.table.side_effect = make_table

    with _patched_provider():
        response = client.post(
            "/api/events/nonexistent-uid/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Event",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 404


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_403_not_coordinator(mock_dep_svc, mock_svc_svc):
    """Returns 403 when the caller is not the coordinator."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("other-user-uuid")
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1")

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
        return tbl

    mock_svc_svc.table.side_effect = make_table

    with _patched_provider():
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Event",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers("other-user-uuid"),
        )
    assert response.status_code == 403


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_409_already_confirmed(mock_dep_svc, mock_svc_svc):
    """Returns 409 if the event is already confirmed — no second calendar event
    is created and no duplicate notifications are inserted."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row(status="confirmed", calendar_event_id="cal-existing-123")
    notifications_inserted = []

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
        elif name == "notifications":
            def capture_insert(data):
                notifications_inserted.append(data)
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[])
                return chain
            tbl.insert.side_effect = capture_insert
        return tbl

    mock_svc_svc.table.side_effect = make_table

    with _patched_provider() as prov:
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "event_already_finalized"
    assert prov.create_event.call_count == 0
    assert notifications_inserted == []


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_409_when_claim_lost_to_concurrent_request(mock_dep_svc, mock_svc_svc):
    """H8 race: the event still reads as 'planning' (fast-path guard passes) but
    the atomic claim UPDATE ... eq(status='planning') matches zero rows because
    a concurrent finalize got there first — 409 event_already_finalized, and the
    provider is NEVER called, so no duplicate calendar event, no duplicate
    notifications, and no final write."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row()  # status='planning' → passes the fast-path guard
    proposed_time = _make_proposed_time_row()
    update_payloads: list[dict] = []
    notifications_inserted: list = []

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )

            def capture_update(payload):
                update_payloads.append(payload)
                chain = MagicMock()
                # Zero rows returned: another request already claimed the event.
                chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
                return chain

            tbl.update.side_effect = capture_update
        elif name == "proposed_times":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=proposed_time
            )
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
        elif name == "calendar_sources":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[_make_write_cal_row()]
            )
        elif name == "notifications":
            def capture_insert(data):
                notifications_inserted.append(data)
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[])
                return chain

            tbl.insert.side_effect = capture_insert
        return tbl

    mock_svc_svc.table.side_effect = make_table

    with _patched_provider() as prov:
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "event_already_finalized"
    assert prov.create_event.call_count == 0
    assert notifications_inserted == []
    # Only the claim attempt was issued — no rollback, no final write.
    assert update_payloads == [{"status": "confirmed"}]


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_422_no_write_calendar(mock_dep_svc, mock_svc_svc):
    """Returns 422 when coordinator has no write calendar configured."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        write_cal_rows=[],  # No write calendar
    ).table.side_effect

    with _patched_provider():
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "no_write_calendar"


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_502_calendar_api_error(mock_dep_svc, mock_svc_svc):
    """Returns 502 when the provider create_event fails — DB is NOT updated."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        write_cal_rows=[_make_write_cal_row()],
    ).table.side_effect

    with _patched_provider(error=Exception("Calendar API failed")):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 502
    assert response.json()["detail"] == "calendar_create_failed"


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_provider_failure_rolls_back_claim(mock_dep_svc, mock_svc_svc):
    """If the coordinator's calendar write fails AFTER the claim, the claim is
    rolled back (confirmed → planning, guarded on status='confirmed') so the
    event is not stuck 'confirmed' with no calendar event — and the original
    502 still surfaces."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row()
    proposed_time = _make_proposed_time_row()
    update_calls: list[dict] = []

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )

            def capture_update(payload):
                entry = {"payload": payload, "filters": []}
                update_calls.append(entry)
                chain = MagicMock()

                def record_eq(column, value):
                    entry["filters"].append((column, value))
                    return chain

                chain.eq.side_effect = record_eq
                chain.execute.return_value = MagicMock(data=[{**event_row, **payload}])
                return chain

            tbl.update.side_effect = capture_update
        elif name == "proposed_times":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=proposed_time
            )
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
        elif name == "calendar_sources":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[_make_write_cal_row()]
            )
        return tbl

    mock_svc_svc.table.side_effect = make_table

    with _patched_provider(error=Exception("Calendar API failed")):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 502
    assert response.json()["detail"] == "calendar_create_failed"
    # Exactly two updates: the optimistic claim, then the compensating rollback.
    assert [c["payload"] for c in update_calls] == [
        {"status": "confirmed"},
        {"status": "planning"},
    ]
    # The claim only fires while the event is still planning...
    assert ("status", "planning") in update_calls[0]["filters"]
    # ...and the rollback is guarded so a concurrent cancel is not clobbered.
    assert ("id", event_row["id"]) in update_calls[1]["filters"]
    assert ("status", "confirmed") in update_calls[1]["filters"]


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_422_write_calendar_not_writable(mock_dep_svc, mock_svc_svc):
    """A read-only write calendar is rejected with a clear error and no provider call."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    write_cal = _make_write_cal_row()
    write_cal["is_writable"] = False

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        write_cal_rows=[write_cal],
    ).table.side_effect

    with _patched_provider() as prov:
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "write_calendar_not_writable"
    assert not prov.create_event.called


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_422_credentials_expired(mock_dep_svc, mock_svc_svc):
    """A ProviderAuthError from create_event surfaces as 422 calendar_credentials_expired."""
    from app.providers.base import ProviderAuthError

    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        write_cal_rows=[_make_write_cal_row()],
    ).table.side_effect

    with _patched_provider(error=ProviderAuthError("invalid_grant")):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "calendar_credentials_expired"


# ─── Sprint 6C: attendee / field tests ───────────────────────────────────────

@patch("app.utils.notifications.service_client")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_excluded_user_ids_removed_from_attendees(mock_dep_svc, mock_svc_svc, mock_notif_svc):
    """Participants listed in excluded_user_ids are not added as attendees."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        participants=[
            _make_participant("bob-uuid", "bob@example.com"),
            _make_participant("carol-uuid", "carol@example.com"),
        ],
        write_cal_rows=[_make_write_cal_row()],
    ).table.side_effect

    capture: dict = {}
    with _patched_provider(capture=capture):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": ["carol-uuid"],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    emails = capture["payload"].attendee_emails
    assert "bob@example.com" in emails
    assert "carol@example.com" not in emails


@patch("app.utils.notifications.service_client")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_extra_emails_added_to_attendees(mock_dep_svc, mock_svc_svc, mock_notif_svc):
    """Emails in extra_emails are appended to the attendees list."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        participants=[_make_participant("bob-uuid", "bob@example.com")],
        write_cal_rows=[_make_write_cal_row()],
    ).table.side_effect

    capture: dict = {}
    with _patched_provider(capture=capture):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": ["external@partner.com"],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    emails = capture["payload"].attendee_emails
    assert "bob@example.com" in emails
    assert "external@partner.com" in emails


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_location_in_payload(mock_dep_svc, mock_svc_svc):
    """location field appears on the EventPayload."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        write_cal_rows=[_make_write_cal_row()],
    ).table.side_effect

    capture: dict = {}
    with _patched_provider(capture=capture):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "123 Main St",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    assert capture["payload"].location == "123 Main St"


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_video_call_link_in_description(mock_dep_svc, mock_svc_svc):
    """video_call_link appears in description as 'Video call: {link}'."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        write_cal_rows=[_make_write_cal_row()],
    ).table.side_effect

    capture: dict = {}
    with _patched_provider(capture=capture):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "https://meet.example.com/abc",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    assert capture["payload"].description == "Video call: https://meet.example.com/abc"


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_note_and_video_call_link_combined(mock_dep_svc, mock_svc_svc):
    """note + video_call_link produces '{note}\n\nVideo call: {link}' description."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        write_cal_rows=[_make_write_cal_row()],
    ).table.side_effect

    capture: dict = {}
    with _patched_provider(capture=capture):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "See you there!",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "https://meet.example.com/xyz",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    assert capture["payload"].description == "See you there!\n\nVideo call: https://meet.example.com/xyz"


@patch("app.utils.notifications.service_client")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_microsoft_write_calendar_prefers_outlook_email(mock_dep_svc, mock_svc_svc, mock_notif_svc):
    """Cross-provider: a Microsoft write calendar with a participant who has both
    Google and Microsoft accounts invites the Outlook email; the event is created
    via the Microsoft provider."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    bob = {
        "user_id": "bob-uuid",
        "profiles": {
            "email_address": "bob@example.com",
            "full_name": "Bob",
            "calendar_accounts": [
                {"provider": "google", "provider_email": "bob@gmail.com"},
                {"provider": "microsoft", "provider_email": "bob@outlook.com"},
            ],
        },
    }

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        participants=[bob],
        write_cal_rows=[_make_write_cal_row(provider="microsoft")],
    ).table.side_effect

    capture: dict = {}
    with _patched_provider(capture=capture):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    emails = capture["payload"].attendee_emails
    assert "bob@outlook.com" in emails
    assert "bob@gmail.com" not in emails


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_name_differs_updates_event_name(mock_dep_svc, mock_svc_svc):
    """When name differs from event.name, the update payload includes name."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row(name="Team Lunch")
    proposed_time = _make_proposed_time_row()
    write_cal = _make_write_cal_row()

    captured_update = {}

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )

            def capture_update(payload):
                captured_update.update(payload)
                m = MagicMock()
                # Both the claim and the final write chain two .eq() filters.
                m.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{**event_row, "status": "confirmed", "name": payload.get("name", event_row["name"])}]
                )
                return m

            tbl.update.side_effect = capture_update
        elif name == "proposed_times":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=proposed_time
            )
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={
                    "user_id": "coordinator-uuid-1",
                    "profiles": {"email_address": "alice@example.com", "full_name": "Alice", "calendar_accounts": []},
                }
            )
        elif name == "calendar_sources":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[write_cal])
        elif name == "notifications":
            tbl.insert.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    mock_svc_svc.table.side_effect = make_table

    with _patched_provider(event_id="cal-1"):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Renamed Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    assert captured_update.get("name") == "Renamed Lunch"
    assert captured_update.get("calendar_event_id") == "cal-1"
    # The final write stamps finalized_at (audit L1: it was never populated).
    assert captured_update.get("finalized_at") is not None


# ─── Direct-write to participants' own calendars (cross-provider) ─────────────

@patch("app.utils.notifications.service_client")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_writes_to_participant_with_write_calendar_directly(mock_dep_svc, mock_svc_svc, mock_notif_svc):
    """A participant who has their own write calendar gets the event written
    directly onto it (no attendees), and is NOT an email attendee on the
    coordinator's copy. Coordinator=Google, participant=Outlook."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    coord_cal = _make_user_write_cal("coordinator-uuid-1", "coord-cal", "coord-acct", "google")
    bob_cal = _make_user_write_cal("bob-uuid", "bob-cal", "bob-acct", "microsoft")

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        participants=[_make_participant("bob-uuid", "bob@example.com", "bob@gmail.com")],
        write_cal_rows=[coord_cal, bob_cal],
    ).table.side_effect

    with _patched_provider() as prov:
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    by_cal = {c.args[1]: c.args[2] for c in prov.create_event.call_args_list}
    assert set(by_cal) == {"coord-cal", "bob-cal"}
    # Bob got a direct write with no attendees, and is NOT emailed on the coord copy.
    assert by_cal["bob-cal"].attendee_emails == []
    assert by_cal["coord-cal"].attendee_emails == []


@patch("app.utils.notifications.service_client")
@patch("app.services.finalize_service.mark_account_needs_reauth")
@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_finalize_participant_write_failure_does_not_abort(mock_dep_svc, mock_svc_svc, mock_mark, mock_notif_svc):
    """If writing to a participant's calendar fails (expired token), finalize
    still succeeds and the participant's account is flagged needs_reauth."""
    from app.providers.base import ProviderAuthError

    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    coord_cal = _make_user_write_cal("coordinator-uuid-1", "coord-cal", "coord-acct", "google")
    bob_cal = _make_user_write_cal("bob-uuid", "bob-cal", "bob-acct", "microsoft")

    mock_svc_svc.table.side_effect = _make_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        participants=[_make_participant("bob-uuid", "bob@example.com")],
        write_cal_rows=[coord_cal, bob_cal],
    ).table.side_effect

    prov = MagicMock()

    def _create(tokens, calendar_id, payload):
        if calendar_id == "bob-cal":
            raise ProviderAuthError("expired")
        return "coord-evt"

    prov.create_event.side_effect = _create

    with patch("app.services.finalize_service.get_provider", return_value=prov):
        response = client.post(
            "/api/events/event-uid-1/finalize",
            json={
                "proposed_time_id": "pt-uuid-1",
                "name": "Team Lunch",
                "note": "",
                "excluded_user_ids": [],
                "extra_emails": [],
                "location": "",
                "video_call_link": "",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 200
    mock_mark.assert_called_once_with("bob-acct")


# ─── CAS credentials persistence (M6) ────────────────────────────────────────

@patch("app.services.finalize_service.get_provider")
def test_create_event_applies_cas_filter_on_rotated_credentials(mock_get_provider):
    """M6: when create_event rotates credentials (Microsoft rotates its refresh
    token on every refresh), the persist is a compare-and-swap keyed on the
    ORIGINAL refresh token — so a concurrently rotated token is never clobbered."""
    from app.providers.base import EventPayload
    from app.services.finalize_service import _create_event_on_write_calendar

    write_cal_row = {
        "id": "src-1",
        "calendar_id": "primary",
        "calendar_accounts": {
            "id": "acct-1",
            "user_id": "u1",
            "provider": "microsoft",
            "credentials": {"access_token": "old", "refresh_token": "r1"},
        },
    }

    prov = MagicMock()

    def _create(tokens, calendar_id, payload):
        tokens.update({"access_token": "new", "refresh_token": "r2"})
        return "evt-1"

    prov.create_event.side_effect = _create
    mock_get_provider.return_value = prov

    update_calls = []

    def capture_update(payload):
        entry = {"payload": payload, "eq_calls": []}
        update_calls.append(entry)
        chain = MagicMock()

        def record_eq(column, value):
            entry["eq_calls"].append((column, value))
            return chain

        chain.eq.side_effect = record_eq
        chain.execute.return_value = MagicMock(data=[])
        return chain

    db = MagicMock()
    db.table.return_value.update.side_effect = capture_update

    payload = EventPayload(
        summary="s",
        description="",
        start_utc="2026-01-01T00:00:00+00:00",
        end_utc="2026-01-01T01:00:00+00:00",
    )

    result = _create_event_on_write_calendar(db, write_cal_row, payload)

    assert result == "evt-1"
    cred_calls = [c for c in update_calls if "credentials" in c["payload"]]
    assert len(cred_calls) == 1
    assert ("id", "acct-1") in cred_calls[0]["eq_calls"]
    assert ("credentials->>refresh_token", "r1") in cred_calls[0]["eq_calls"]
    assert cred_calls[0]["payload"]["credentials"]["refresh_token"] == "r2"


# ─── GET /api/events/{uid}/finalize/status ────────────────────────────────────

@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_get_finalize_status_coordinator(mock_dep_svc, mock_router_svc):
    """Coordinator can fetch finalize status."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )

    event_row = _make_event_row(
        status="confirmed",
        finalized_start_time_utc="2026-04-10T12:00:00+00:00",
        finalized_end_time_utc="2026-04-10T13:00:00+00:00",
        calendar_event_id="cal-123",
    )

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.get(
        "/api/events/event-uid-1/finalize/status",
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmed"
    assert data["finalized_start_time_utc"] == "2026-04-10T12:00:00+00:00"
    assert data["calendar_event_id"] == "cal-123"


@patch("app.services.finalize_service.service_client")
@patch("app.dependencies.service_client")
def test_get_finalize_status_403_outsider(mock_dep_svc, mock_router_svc):
    """Non-participant gets 403 on finalize/status."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile("outsider-uuid")
    )

    event_row = _make_event_row(coordinator_id="coordinator-uuid-1")

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
        elif name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=None
            )
        return tbl

    mock_router_svc.table.side_effect = make_table

    response = client.get(
        "/api/events/event-uid-1/finalize/status",
        headers=_auth_headers("outsider-uuid"),
    )
    assert response.status_code == 403


# ─── pending_attendee_user_ids (chat "book direct" path) ──────────────────────

from app.models.user import User
from app.services.finalize_service import finalize_event


def _coord_user() -> User:
    return User(
        id="coordinator-uuid-1",
        email_address="alice@example.com",
        full_name="Alice",
        token="tok",
    )


def _make_pending_finalize_db(
    event_row: dict,
    proposed_time_row: dict,
    accepted: list[dict],
    pending: list[dict],
    write_cal_rows: list[dict],
) -> MagicMock:
    """db mock supporting both the accepted fetch (.eq(event_id).eq(status)) and
    the pending fetch (.eq(event_id).in_(user_id).neq(status))."""
    updated_event = {**event_row, "status": "confirmed", "calendar_event_id": "cal-evt-123"}

    def make_table(name):
        tbl = MagicMock()
        if name == "events":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=event_row
            )
            tbl.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[updated_event]
            )
        elif name == "proposed_times":
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=proposed_time_row
            )
        elif name == "event_participants":
            # accepted fetch
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=accepted
            )
            # pending fetch (.in_().neq())
            tbl.select.return_value.eq.return_value.in_.return_value.neq.return_value.execute.return_value = MagicMock(
                data=pending
            )
        elif name == "calendar_sources":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=write_cal_rows
            )
        elif name == "calendar_accounts":
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    db = MagicMock()
    db.table.side_effect = make_table
    return db


@patch("app.services.finalize_service.create_notifications")
@patch("app.services.finalize_service.get_provider")
def test_finalize_pending_attendees_emailed_and_notified(mock_get_provider, mock_create_notif):
    """Pending users are added as email attendees on the coordinator's copy, are
    NEVER written onto their own calendar (even though one has a write calendar),
    and receive an event_finalized notification."""
    calls: list = []

    def _create(tokens, calendar_id, payload):
        calls.append((calendar_id, payload))
        return "cal-evt-123"

    prov = MagicMock()
    prov.create_event.side_effect = _create
    mock_get_provider.return_value = prov

    coord_cal = _make_user_write_cal("coordinator-uuid-1", "coord-cal", "coord-acct", "google")
    # The pending user HAS a write calendar — proving they are still not direct-written.
    pending_cal = _make_user_write_cal("pending-uuid", "pending-cal", "pending-acct", "microsoft")

    db = _make_pending_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        accepted=[],
        pending=[_make_participant("pending-uuid", "pending@example.com")],
        write_cal_rows=[coord_cal, pending_cal],
    )

    result = finalize_event(
        "event-uid-1",
        "pt-uuid-1",
        "Team Lunch",
        _coord_user(),
        db=db,
        pending_attendee_user_ids=["pending-uuid"],
    )

    assert result["status"] == "confirmed"
    # Exactly one calendar write — the coordinator copy. The pending user's own
    # calendar is never touched.
    assert len(calls) == 1
    cal_id, payload = calls[0]
    assert cal_id == "coord-cal"
    assert "pending@example.com" in payload.attendee_emails
    assert all(c[0] != "pending-cal" for c in calls)

    # Notifications include the pending user, all typed event_finalized.
    notif_rows = mock_create_notif.call_args[0][0]
    notif_user_ids = [r["user_id"] for r in notif_rows]
    assert "pending-uuid" in notif_user_ids
    assert all(r["notification_type"] == "event_finalized" for r in notif_rows)


@patch("app.services.finalize_service.create_notifications")
@patch("app.services.finalize_service.get_provider")
def test_finalize_pending_none_skips_pending(mock_get_provider, mock_create_notif):
    """pending_attendee_user_ids=None → the pending fetch is skipped entirely: a
    would-be pending email never lands in the attendees and no pending
    notification is created (regression-identical behavior)."""
    calls: list = []

    def _create(tokens, calendar_id, payload):
        calls.append((calendar_id, payload))
        return "cal-evt-123"

    prov = MagicMock()
    prov.create_event.side_effect = _create
    mock_get_provider.return_value = prov

    coord_cal = _make_user_write_cal("coordinator-uuid-1", "coord-cal", "coord-acct", "google")

    db = _make_pending_finalize_db(
        event_row=_make_event_row(),
        proposed_time_row=_make_proposed_time_row(),
        accepted=[_make_participant("bob-uuid", "bob@example.com")],
        # Configured but must NEVER be read when pending is None.
        pending=[_make_participant("pending-uuid", "shouldnotappear@example.com")],
        write_cal_rows=[coord_cal],
    )

    finalize_event(
        "event-uid-1",
        "pt-uuid-1",
        "Team Lunch",
        _coord_user(),
        db=db,
        pending_attendee_user_ids=None,
    )

    assert len(calls) == 1
    _, payload = calls[0]
    assert "bob@example.com" in payload.attendee_emails
    assert "shouldnotappear@example.com" not in payload.attendee_emails

    notif_rows = mock_create_notif.call_args[0][0]
    notif_user_ids = [r["user_id"] for r in notif_rows]
    assert notif_user_ids == ["bob-uuid"]
    assert "pending-uuid" not in notif_user_ids
