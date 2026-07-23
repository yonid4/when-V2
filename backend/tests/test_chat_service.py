"""Package 2 — Chat plumbing tests.

Covers thread CRUD endpoints, the agent-turn endpoint (with a patched
FakeGraph), run_turn persistence + state rehydration, foreign-thread 404,
page-context access verification, request validation, and the chat-disabled
503 gate. Supabase is mocked entirely — nothing hits the network.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from pydantic import ValidationError

from app.config import settings
from app.main import app
from app.models.chat import ChatActionPayload, ChatPageContext, ChatTurnRequest
from app.models.user import User
from app.services import chat_service

client = TestClient(app)

REF_TIME = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)


# ─── Fixtures / helpers ──────────────────────────────────────────────────────

def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-1",
        "email_address": "alice@example.com",
        "full_name": "Alice",
        "avatar_url": None,
        "timezone": "America/Los_Angeles",
        "token": "fake-jwt-token",
    }
    return User(**{**defaults, **overrides})


def _auth_headers(user_id: str = "user-1", email: str = "alice@example.com") -> dict:
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = jwt.encode(
        {"sub": user_id, "email": email, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


def _current_user_profile(user_id: str = "user-1") -> dict:
    return {
        "id": user_id,
        "email_address": "alice@example.com",
        "full_name": "Alice",
        "avatar_url": None,
        "timezone": "America/Los_Angeles",
    }


def _make_thread_row(**overrides) -> dict:
    defaults = {
        "id": "thread-1",
        "user_id": "user-1",
        "title": None,
        "status": "idle",
        "workflow": None,
        "draft": None,
        "participants": None,
        "pending_people": None,
        "candidate_slots": None,
        "booking_mode": None,
        "last_event_uid": None,
        "created_at": "2026-07-17T11:00:00+00:00",
        "updated_at": "2026-07-17T11:00:00+00:00",
    }
    return {**defaults, **overrides}


def _make_message_row(**overrides) -> dict:
    defaults = {
        "id": "msg-1",
        "thread_id": "thread-1",
        "role": "user",
        "content": "hello",
        "payload": None,
        "created_at": "2026-07-17T11:05:00+00:00",
    }
    return {**defaults, **overrides}


def _graph_output(**overrides) -> dict:
    defaults = {
        "assistant_text": "Sure — let's schedule that.",
        "card": {"mode": "create_direct", "title": "Lunch"},
        "buttons": [{"label": "Confirm", "action": {"type": "confirm_draft"}}],
        "status": "collecting",
        "workflow": "create_event",
        "draft": {"title": "Lunch"},
        "participants": [],
        "pending_people": None,
        "candidate_slots": None,
        "booking_mode": "direct",
        "result_event_uid": None,
    }
    return {**defaults, **overrides}


class _FakeGraph:
    """Stand-in compiled graph returning a fixed output; records the input state."""

    def __init__(self, output: dict):
        self._output = output
        self.last_state: dict | None = None

    def invoke(self, state: dict) -> dict:
        self.last_state = state
        return dict(self._output)


def _make_chain() -> MagicMock:
    """Chainable mock — every query builder returns itself; execute is terminal."""
    chain = MagicMock()
    for m in ("eq", "neq", "in_", "single", "maybe_single", "order"):
        getattr(chain, m).return_value = chain
    return chain


def _mock_db() -> MagicMock:
    """Mock Supabase client: same table name → same (cached) table mock; each
    operation gets its own chain so select/insert/update/delete don't collide."""
    db = MagicMock()
    tables: dict[str, MagicMock] = {}

    def _get_table(name):
        if name not in tables:
            table = MagicMock()
            for op in ("select", "insert", "update", "delete"):
                getattr(table, op).return_value = _make_chain()
            tables[name] = table
        return tables[name]

    db.table = MagicMock(side_effect=_get_table)
    return db


def _wire_turn_db(
    db: MagicMock,
    thread_row: dict,
    user_msg_row: dict,
    assistant_msg_row: dict,
    updated_thread_row: dict,
) -> None:
    """Configure a mock db for a full run_turn (fetch → 2 inserts → update)."""
    threads = db.table("chat_threads")
    threads.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=thread_row
    )
    threads.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[updated_thread_row]
    )

    messages = db.table("chat_messages")
    # Two inserts on the same table mock — sequential results via side_effect.
    messages.insert.return_value.execute.side_effect = [
        MagicMock(data=[user_msg_row]),
        MagicMock(data=[assistant_msg_row]),
    ]


# ─── run_turn — persistence + state rehydration ──────────────────────────────

def test_run_turn_persists_messages_and_thread_state(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    user = _make_user()
    db = _mock_db()

    thread_row = _make_thread_row(title=None, status="idle")
    user_msg_row = _make_message_row(id="u1", role="user", content="Schedule lunch")
    assistant_msg_row = _make_message_row(
        id="a1", role="assistant", content="Sure — let's schedule that.",
        payload={"card": {"mode": "create_direct", "title": "Lunch"}, "buttons": []},
    )
    updated_thread_row = _make_thread_row(
        title="Schedule lunch", status="collecting", workflow="create_event",
        draft={"title": "Lunch"}, booking_mode="direct",
    )
    _wire_turn_db(db, thread_row, user_msg_row, assistant_msg_row, updated_thread_row)

    fake_graph = _FakeGraph(_graph_output())
    with patch("app.services.chat_service.get_authed_client", return_value=db), \
         patch("agent_service.graph.get_compiled_graph", return_value=fake_graph):
        req = ChatTurnRequest(message="Schedule lunch", timezone="Asia/Jerusalem")
        result = chat_service.run_turn("thread-1", req, REF_TIME, user)

    # Two message rows inserted: user then assistant.
    insert_calls = db.table("chat_messages").insert.call_args_list
    assert len(insert_calls) == 2
    user_insert = insert_calls[0][0][0]
    assistant_insert = insert_calls[1][0][0]
    assert user_insert["role"] == "user"
    assert user_insert["content"] == "Schedule lunch"
    assert user_insert["payload"] is None
    assert assistant_insert["role"] == "assistant"
    assert assistant_insert["content"] == "Sure — let's schedule that."
    assert assistant_insert["payload"]["card"] == {"mode": "create_direct", "title": "Lunch"}
    assert assistant_insert["payload"]["buttons"] == [
        {"label": "Confirm", "action": {"type": "confirm_draft"}}
    ]

    # Thread columns advanced from the graph output (incl. workflow) + title set.
    update_payload = db.table("chat_threads").update.call_args[0][0]
    assert update_payload["status"] == "collecting"
    assert update_payload["workflow"] == "create_event"
    assert update_payload["draft"] == {"title": "Lunch"}
    assert update_payload["booking_mode"] == "direct"
    assert update_payload["title"] == "Schedule lunch"
    assert "updated_at" in update_payload

    # Response is a ChatTurnResponse carrying both new messages.
    assert len(result.messages) == 2
    assert result.messages[0].role == "user"
    assert result.messages[1].role == "assistant"
    assert result.thread.workflow == "create_event"
    assert result.thread.status == "collecting"
    assert result.event_uid is None

    # Rehydrated thread state was injected into the graph. The timezone comes
    # from the request (browser), not the profile ("America/Los_Angeles").
    assert fake_graph.last_state["status"] == "idle"
    assert fake_graph.last_state["reference_time_utc"] == REF_TIME
    assert fake_graph.last_state["user_timezone"] == "Asia/Jerusalem"


def test_run_turn_sets_last_event_uid_and_response_event_uid(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    user = _make_user()
    db = _mock_db()

    thread_row = _make_thread_row(title="Existing")
    updated = _make_thread_row(title="Existing", last_event_uid="abc123def456")
    _wire_turn_db(
        db, thread_row,
        _make_message_row(id="u1"),
        _make_message_row(id="a1", role="assistant"),
        updated,
    )

    output = _graph_output(result_event_uid="abc123def456")
    with patch("app.services.chat_service.get_authed_client", return_value=db), \
         patch("agent_service.graph.get_compiled_graph", return_value=_FakeGraph(output)):
        req = ChatTurnRequest(message="confirm it")
        result = chat_service.run_turn("thread-1", req, REF_TIME, user)

    update_payload = db.table("chat_threads").update.call_args[0][0]
    assert update_payload["last_event_uid"] == "abc123def456"
    # Title already present → not overwritten on a later turn.
    assert "title" not in update_payload
    assert result.event_uid == "abc123def456"
    # result_created absent (e.g. an edit) → no navigation signal to the client.
    assert result.created_event_uid is None


def test_run_turn_created_event_sets_created_event_uid(monkeypatch):
    """A turn that creates a brand-new event surfaces created_event_uid for nav."""
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    user = _make_user()
    db = _mock_db()

    thread_row = _make_thread_row(title="Existing")
    _wire_turn_db(
        db, thread_row,
        _make_message_row(id="u1"),
        _make_message_row(id="a1", role="assistant"),
        _make_thread_row(title="Existing", last_event_uid="newuid987"),
    )

    output = _graph_output(result_event_uid="newuid987", result_created=True)
    with patch("app.services.chat_service.get_authed_client", return_value=db), \
         patch("agent_service.graph.get_compiled_graph", return_value=_FakeGraph(output)):
        req = ChatTurnRequest(action=ChatActionPayload(type="confirm_draft"))
        result = chat_service.run_turn("thread-1", req, REF_TIME, user)

    assert result.event_uid == "newuid987"
    assert result.created_event_uid == "newuid987"


def test_run_turn_action_turn_uses_deterministic_label(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    user = _make_user()
    db = _mock_db()

    thread_row = _make_thread_row(title=None)
    _wire_turn_db(
        db, thread_row,
        _make_message_row(id="u1", content="Confirm"),
        _make_message_row(id="a1", role="assistant"),
        _make_thread_row(title="Confirm"),
    )

    with patch("app.services.chat_service.get_authed_client", return_value=db), \
         patch("agent_service.graph.get_compiled_graph", return_value=_FakeGraph(_graph_output())):
        req = ChatTurnRequest(action=ChatActionPayload(type="confirm_draft"))
        chat_service.run_turn("thread-1", req, REF_TIME, user)

    user_insert = db.table("chat_messages").insert.call_args_list[0][0][0]
    assert user_insert["content"] == "Confirm"
    assert user_insert["payload"] == {"type": "confirm_draft"}


# ─── run_turn — 404 foreign thread ───────────────────────────────────────────

def test_run_turn_404_foreign_thread(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    user = _make_user()
    db = _mock_db()
    db.table("chat_threads").select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=None
    )

    with patch("app.services.chat_service.get_authed_client", return_value=db):
        req = ChatTurnRequest(message="hi")
        with pytest.raises(HTTPException) as exc:
            chat_service.run_turn("foreign-thread", req, REF_TIME, user)
    assert exc.value.status_code == 404


# ─── run_turn — page-context access verification ─────────────────────────────

def test_run_turn_drops_inaccessible_event_context(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    user = _make_user()
    db = _mock_db()
    fake_graph = _FakeGraph(_graph_output())
    _wire_turn_db(
        db, _make_thread_row(),
        _make_message_row(id="u1"),
        _make_message_row(id="a1", role="assistant"),
        _make_thread_row(),
    )

    with patch("app.services.chat_service.get_authed_client", return_value=db), \
         patch("agent_service.graph.get_compiled_graph", return_value=fake_graph), \
         patch(
             "app.services.chat_service.event_service.get_event_by_uid",
             side_effect=HTTPException(status_code=404, detail="Event not found"),
         ):
        req = ChatTurnRequest(
            message="what about this event?",
            context=ChatPageContext(page="event", event_uid="foreign-uid"),
        )
        chat_service.run_turn("thread-1", req, REF_TIME, user)

    # Inaccessible event_uid → page_context silently dropped to None.
    assert fake_graph.last_state["page_context"] is None


def test_run_turn_passes_verified_event_summary(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    user = _make_user()
    db = _mock_db()
    fake_graph = _FakeGraph(_graph_output())
    _wire_turn_db(
        db, _make_thread_row(),
        _make_message_row(id="u1"),
        _make_message_row(id="a1", role="assistant"),
        _make_thread_row(),
    )

    event_stub = SimpleNamespace(
        uid="evt-uid",
        name="Team Lunch",
        status="planning",
        earliest_datetime_utc=datetime(2026, 7, 20, 16, tzinfo=timezone.utc),
        latest_datetime_utc=datetime(2026, 7, 20, 23, tzinfo=timezone.utc),
        duration_minutes=60,
        coordinator_id="user-1",
    )

    with patch("app.services.chat_service.get_authed_client", return_value=db), \
         patch("agent_service.graph.get_compiled_graph", return_value=fake_graph), \
         patch("app.services.chat_service.event_service.get_event_by_uid", return_value=event_stub):
        req = ChatTurnRequest(
            message="edit it",
            context=ChatPageContext(page="event", event_uid="evt-uid"),
        )
        chat_service.run_turn("thread-1", req, REF_TIME, user)

    summary = fake_graph.last_state["page_context"]
    assert summary == {
        "uid": "evt-uid",
        "name": "Team Lunch",
        "status": "planning",
        "earliest_datetime_utc": "2026-07-20T16:00:00+00:00",
        "latest_datetime_utc": "2026-07-20T23:00:00+00:00",
        "duration_minutes": 60,
        "is_coordinator": True,
    }


# ─── run_turn — chat-disabled 503 gate ───────────────────────────────────────

def test_run_turn_503_when_key_blank(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    user = _make_user()
    req = ChatTurnRequest(message="hi")
    with pytest.raises(HTTPException) as exc:
        chat_service.run_turn("thread-1", req, REF_TIME, user)
    assert exc.value.status_code == 503
    assert exc.value.detail == "chat_disabled"


# ─── ChatTurnRequest validation ──────────────────────────────────────────────

def test_turn_request_rejects_both_message_and_action():
    with pytest.raises(ValidationError):
        ChatTurnRequest(message="hi", action=ChatActionPayload(type="confirm_draft"))


def test_turn_request_rejects_neither():
    with pytest.raises(ValidationError):
        ChatTurnRequest()


def test_turn_request_rejects_overlong_message():
    with pytest.raises(ValidationError):
        ChatTurnRequest(message="x" * 2001)


def test_turn_request_accepts_message_only():
    req = ChatTurnRequest(message="hi")
    assert req.message == "hi"
    assert req.action is None


def test_turn_request_accepts_action_only():
    req = ChatTurnRequest(action=ChatActionPayload(type="cancel"))
    assert req.action.type == "cancel"
    assert req.message is None


# ─── Thread CRUD endpoints (router + service via TestClient) ─────────────────

@patch("app.services.chat_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_create_thread_endpoint(mock_dep_svc, mock_get_client):
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    db = _mock_db()
    mock_get_client.return_value = db
    db.table("chat_threads").insert.return_value.execute.return_value = MagicMock(
        data=[_make_thread_row()]
    )

    resp = client.post("/api/chat/threads", headers=_auth_headers())
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "thread-1"
    assert body["status"] == "idle"


@patch("app.services.chat_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_list_threads_endpoint_ordered(mock_dep_svc, mock_get_client):
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    db = _mock_db()
    mock_get_client.return_value = db
    rows = [_make_thread_row(id="t-new"), _make_thread_row(id="t-old")]
    db.table("chat_threads").select.return_value.order.return_value.execute.return_value = MagicMock(
        data=rows
    )

    resp = client.get("/api/chat/threads", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert [t["id"] for t in body] == ["t-new", "t-old"]
    # Ordered updated_at desc.
    assert db.table("chat_threads").select.return_value.order.call_args == call(
        "updated_at", desc=True
    )


@patch("app.services.chat_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_get_messages_endpoint_ordered_asc(mock_dep_svc, mock_get_client):
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    db = _mock_db()
    mock_get_client.return_value = db
    rows = [
        _make_message_row(id="m1", role="user", content="hi"),
        _make_message_row(id="m2", role="assistant", content="hello"),
    ]
    db.table("chat_messages").select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
        data=rows
    )

    resp = client.get("/api/chat/threads/thread-1/messages", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert [m["id"] for m in body] == ["m1", "m2"]
    # created_at ascending (default order direction).
    assert db.table("chat_messages").select.return_value.eq.return_value.order.call_args == call(
        "created_at"
    )


@patch("app.services.chat_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_delete_thread_endpoint(mock_dep_svc, mock_get_client):
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    db = _mock_db()
    mock_get_client.return_value = db
    db.table("chat_threads").select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={"id": "thread-1"}
    )
    db.table("chat_threads").delete.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )

    resp = client.delete("/api/chat/threads/thread-1", headers=_auth_headers())
    assert resp.status_code == 204
    db.table("chat_threads").delete.return_value.eq.assert_called_once_with("id", "thread-1")


@patch("app.services.chat_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_delete_thread_endpoint_404_foreign(mock_dep_svc, mock_get_client):
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    db = _mock_db()
    mock_get_client.return_value = db
    db.table("chat_threads").select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=None
    )

    resp = client.delete("/api/chat/threads/foreign", headers=_auth_headers())
    assert resp.status_code == 404


# ─── Turn endpoint — happy path + validation + 503 (router) ──────────────────

@patch("app.services.chat_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_turn_endpoint_happy_path(mock_dep_svc, mock_get_client, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    db = _mock_db()
    mock_get_client.return_value = db
    _wire_turn_db(
        db,
        _make_thread_row(title=None),
        _make_message_row(id="u1", role="user", content="Schedule lunch"),
        _make_message_row(
            id="a1", role="assistant", content="Sure — let's schedule that.",
            payload={"card": {"mode": "create_direct", "title": "Lunch"}, "buttons": []},
        ),
        _make_thread_row(title="Schedule lunch", status="collecting", workflow="create_event"),
    )

    with patch("agent_service.graph.get_compiled_graph", return_value=_FakeGraph(_graph_output())):
        resp = client.post(
            "/api/chat/threads/thread-1/turn",
            headers=_auth_headers(),
            json={"message": "Schedule lunch"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["role"] == "assistant"
    assert body["thread"]["workflow"] == "create_event"
    assert body["thread"]["status"] == "collecting"


@patch("app.dependencies.service_client")
def test_turn_endpoint_422_on_empty_body(mock_dep_svc, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    # Neither message nor action → model_validator fails → 422.
    resp = client.post(
        "/api/chat/threads/thread-1/turn",
        headers=_auth_headers(),
        json={},
    )
    assert resp.status_code == 422


@patch("app.dependencies.service_client")
def test_turn_endpoint_503_when_chat_disabled(mock_dep_svc, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    mock_dep_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=_current_user_profile()
    )
    with patch("app.services.chat_service.get_authed_client", return_value=_mock_db()):
        resp = client.post(
            "/api/chat/threads/thread-1/turn",
            headers=_auth_headers(),
            json={"message": "hi"},
        )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "chat_disabled"
