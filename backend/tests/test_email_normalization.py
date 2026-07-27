"""Sprint 7 — normalize_email and invite normalization tests."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.config import settings
from app.utils.email import normalize_email

client = TestClient(app)


# ─── normalize_email unit tests ──────────────────────────────────────────────

def test_normalize_email_gmail_with_dots():
    """Gmail address with dots → dots stripped from local part."""
    assert normalize_email("john.doe@gmail.com") == "johndoe@gmail.com"


def test_normalize_email_gmail_multiple_dots():
    """Gmail address with multiple dots → all stripped."""
    assert normalize_email("j.o.h.n@gmail.com") == "john@gmail.com"


def test_normalize_email_gmail_no_dots():
    """Gmail address with no dots in local part → unchanged."""
    assert normalize_email("johndoe@gmail.com") == "johndoe@gmail.com"


def test_normalize_email_non_gmail():
    """Non-Gmail address → returned unchanged (dots preserved)."""
    assert normalize_email("john.doe@company.com") == "john.doe@company.com"


def test_normalize_email_non_gmail_other_domain():
    """Other domain address → returned unchanged."""
    assert normalize_email("j.o.h.n@outlook.com") == "j.o.h.n@outlook.com"


def test_normalize_email_mixed_case_gmail():
    """M11: mixed-case dotted Gmail → lowercased and dots stripped."""
    assert normalize_email("John.Smith@Gmail.com") == "johnsmith@gmail.com"


def test_normalize_email_mixed_case_non_gmail():
    """M11: mixed-case non-Gmail → lowercased, dots preserved."""
    assert normalize_email("JOHN.DOE@Company.COM") == "john.doe@company.com"


# ─── invite normalization integration tests ──────────────────────────────────

def _auth_headers(user_id: str = "user-uuid-1", email: str = "alice@example.com") -> dict:
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = jwt.encode(
        {"sub": user_id, "email": email, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def _current_user_profile() -> dict:
    return {"id": "user-uuid-1", "email_address": "alice@example.com", "full_name": "Alice", "avatar_url": None}


@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_invite_dotted_gmail_is_normalized(mock_dep_svc, mock_get_authed, mock_inv_svc):
    """POST .../invite with dotted Gmail → email is normalized before lookup/storage."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    # Track what email was passed to profiles lookup and invitation insert
    captured_profile_eq = []
    captured_insert_data = []

    invitee_profile = {"id": "invitee-uuid-1"}
    now = datetime.now(timezone.utc).isoformat()
    invite_row = {
        "id": "invite-uuid-1",
        "event_id": "event-db-id-1",
        "inviter_id": "user-uuid-1",
        "invitee_id": "invitee-uuid-1",
        "invitee_email": "johndoe@gmail.com",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }

    def make_db_table(table_name):
        tbl = MagicMock()
        if table_name == "events":
            event_row = {"id": "event-db-id-1", "coordinator_id": "user-uuid-1", "name": "Team Lunch"}
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
        elif table_name == "event_participants":
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
        return tbl

    db = MagicMock()
    db.table.side_effect = make_db_table
    mock_get_authed.return_value = db

    def make_svc_table(table_name):
        tbl = MagicMock()
        if table_name == "profiles":
            # Capture the eq value to verify normalization
            eq_mock = MagicMock()
            eq_mock.maybe_single.return_value.execute.return_value = MagicMock(data=invitee_profile)
            tbl.select.return_value.eq = lambda col, val: (captured_profile_eq.append(val), eq_mock)[1]
        elif table_name == "event_invitations":
            tbl.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            def capture_insert(data):
                captured_insert_data.append(data)
                m = MagicMock()
                m.execute.return_value = MagicMock(data=[invite_row])
                return m
            tbl.insert = capture_insert
        elif table_name == "notifications":
            tbl.insert.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    mock_inv_svc.table.side_effect = make_svc_table

    response = client.post(
        "/api/events/event-uid-1/invite",
        json={"email": "john.doe@gmail.com"},  # dotted Gmail input
        headers=_auth_headers(),
    )

    assert response.status_code == 201
    # The profiles lookup should have used the normalized email (no dots)
    assert "johndoe@gmail.com" in captured_profile_eq, (
        f"Expected normalized email in profiles lookup, got: {captured_profile_eq}"
    )
    # The invitation insert should store the normalized email
    assert captured_insert_data, "No insert was captured"
    assert captured_insert_data[0]["invitee_email"] == "johndoe@gmail.com", (
        f"Expected normalized email in insert, got: {captured_insert_data[0].get('invitee_email')}"
    )


@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_invite_non_gmail_preserved(mock_dep_svc, mock_get_authed, mock_inv_svc):
    """POST .../invite with non-Gmail dotted address → dots preserved."""
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=_current_user_profile())

    captured_profile_eq = []
    now = datetime.now(timezone.utc).isoformat()
    invite_row = {
        "id": "invite-uuid-1",
        "event_id": "event-db-id-1",
        "inviter_id": "user-uuid-1",
        "invitee_id": None,
        "invitee_email": "john.doe@company.com",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }

    def make_db_table(table_name):
        tbl = MagicMock()
        if table_name == "events":
            event_row = {"id": "event-db-id-1", "coordinator_id": "user-uuid-1", "name": "Team Lunch"}
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
        return tbl

    db = MagicMock()
    db.table.side_effect = make_db_table
    mock_get_authed.return_value = db

    def make_svc_table(table_name):
        tbl = MagicMock()
        if table_name == "profiles":
            eq_mock = MagicMock()
            eq_mock.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            tbl.select.return_value.eq = lambda col, val: (captured_profile_eq.append(val), eq_mock)[1]
        elif table_name == "event_invitations":
            tbl.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            tbl.insert.return_value.execute.return_value = MagicMock(data=[invite_row])
        return tbl

    mock_inv_svc.table.side_effect = make_svc_table

    response = client.post(
        "/api/events/event-uid-1/invite",
        json={"email": "john.doe@company.com"},
        headers=_auth_headers(),
    )

    assert response.status_code == 201
    # Dots should be preserved for non-Gmail
    assert "john.doe@company.com" in captured_profile_eq, (
        f"Expected preserved email in profiles lookup, got: {captured_profile_eq}"
    )
