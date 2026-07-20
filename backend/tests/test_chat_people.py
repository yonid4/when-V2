"""Chat agent — people resolution tests (agent/people.py).

Covers explicit-email hit/miss, normalize_email (gmail dots), has_calendar
flag, unique first-token / ambiguous / no-match directory matching, the
EmailPairing LLM pairing via a FakeLLM, the awaiting-email helpers, and the
MAX_CHAT_PEOPLE cap. Supabase is mocked per-table; no network is touched.
"""

from unittest.mock import MagicMock

from agent_service import people
from agent_service.llm import EmailPairing


# ─── FakeLLM ──────────────────────────────────────────────────────────────────

class _FakeStructured:
    def __init__(self, result, calls):
        self._result = result
        self._calls = calls

    def invoke(self, prompt):
        self._calls.append(prompt)
        return self._result


class FakeLLM:
    """Implements `.with_structured_output(schema).invoke(prompt)` → EmailPairing."""

    def __init__(self, same_person: bool):
        self._same = same_person
        self.schemas: list = []
        self.prompts: list = []

    def with_structured_output(self, schema):
        self.schemas.append(schema)
        return _FakeStructured(EmailPairing(same_person=self._same), self.prompts)


# ─── DB fakes ─────────────────────────────────────────────────────────────────

def _profile(user_id="u-1", full_name="Sarah Chen", email="sarah@example.com", n_accounts=1):
    return {
        "id": user_id,
        "full_name": full_name,
        "email_address": email,
        "calendar_accounts": [{"id": f"acct-{i}"} for i in range(n_accounts)],
    }


def _db_email_lookup(profile_or_none, captured_eq=None):
    """A db whose profiles.eq(email_address).maybe_single() returns the given row.

    If ``captured_eq`` is provided, the (column, value) pair is appended to it.
    """
    db = MagicMock()
    profiles = MagicMock()

    def select(_cols):
        chain = MagicMock()

        def eq(col, val):
            if captured_eq is not None:
                captured_eq.append((col, val))
            m = MagicMock()
            m.maybe_single.return_value.execute.return_value = MagicMock(data=profile_or_none)
            return m

        chain.eq.side_effect = eq
        return chain

    profiles.select.side_effect = select
    db.table.side_effect = lambda name: profiles if name == "profiles" else MagicMock()
    return db


def _db_directory(directory_profiles, my_event_ids=("evt-1",), peer_ids=None):
    """A db that serves the co-participant directory query chain.

    - event_participants.select(event_id).eq(user_id).execute() → my_event_ids
    - event_participants.select(user_id).in_(event_id).execute() → peer_ids
    - profiles.select(...).in_(id).execute() → directory_profiles
    - profiles.select(...).eq(id).maybe_single().execute() → by-id lookup
    """
    peer_ids = peer_ids if peer_ids is not None else [p["id"] for p in directory_profiles]

    ep = MagicMock()
    ep.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"event_id": e} for e in my_event_ids]
    )
    ep.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"user_id": pid} for pid in peer_ids]
    )

    by_id = {p["id"]: p for p in directory_profiles}
    profiles = MagicMock()
    profiles.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=list(directory_profiles)
    )

    def eq(col, val):
        m = MagicMock()
        m.maybe_single.return_value.execute.return_value = MagicMock(data=by_id.get(val))
        return m

    profiles.select.return_value.eq.side_effect = eq

    tables = {"event_participants": ep, "profiles": profiles}
    db = MagicMock()
    db.table.side_effect = lambda name: tables.get(name, MagicMock())
    return db


# ─── Explicit email ───────────────────────────────────────────────────────────

def test_explicit_email_hit_in_system():
    db = _db_email_lookup(_profile(user_id="u-9", full_name="Sarah Chen", n_accounts=2))
    participants, pending = people.resolve_mentions(
        [{"email": "sarah@example.com"}], coordinator_id="coord", db=db
    )
    assert pending is None
    assert participants == [{
        "user_id": "u-9",
        "full_name": "Sarah Chen",
        "email": "sarah@example.com",
        "in_system": True,
        "has_calendar": True,
        "source": "explicit_email",
    }]


def test_explicit_email_miss_not_in_system():
    db = _db_email_lookup(None)
    participants, pending = people.resolve_mentions(
        [{"name": "Bob", "email": "bob@company.com"}], coordinator_id="coord", db=db
    )
    assert pending is None
    assert participants == [{
        "full_name": "Bob",
        "email": "bob@company.com",
        "in_system": False,
        "has_calendar": False,
        "source": "explicit_email",
    }]
    assert "user_id" not in participants[0]


def test_explicit_email_normalizes_gmail_dots():
    captured = []
    db = _db_email_lookup(None, captured_eq=captured)
    participants, _ = people.resolve_mentions(
        [{"email": "John.Doe@Gmail.com"}], coordinator_id="coord", db=db
    )
    # profiles lookup used the normalized (dots stripped, lowercased) address.
    assert ("email_address", "johndoe@gmail.com") in captured
    assert participants[0]["email"] == "johndoe@gmail.com"


def test_has_calendar_false_when_no_accounts():
    db = _db_email_lookup(_profile(n_accounts=0))
    participants, _ = people.resolve_mentions(
        [{"email": "sarah@example.com"}], coordinator_id="coord", db=db
    )
    assert participants[0]["has_calendar"] is False
    assert participants[0]["in_system"] is True


# ─── Directory (bare name) ────────────────────────────────────────────────────

def test_bare_name_exact_full_name_match():
    directory = [_profile(user_id="u-1", full_name="Sarah Chen"),
                 _profile(user_id="u-2", full_name="Bob Jones")]
    db = _db_directory(directory)
    participants, pending = people.resolve_mentions(
        [{"name": "Sarah Chen"}], coordinator_id="coord", db=db
    )
    assert pending is None
    assert participants[0]["user_id"] == "u-1"
    assert participants[0]["source"] == "coparticipant"


def test_bare_name_unique_first_token_match():
    directory = [_profile(user_id="u-1", full_name="Sarah Chen"),
                 _profile(user_id="u-2", full_name="Bob Jones")]
    db = _db_directory(directory)
    participants, pending = people.resolve_mentions(
        [{"name": "Sarah"}], coordinator_id="coord", db=db
    )
    assert pending is None
    assert participants[0]["user_id"] == "u-1"


def test_bare_name_ambiguous_pending():
    directory = [_profile(user_id="u-1", full_name="Sarah Chen"),
                 _profile(user_id="u-2", full_name="Sarah Kim")]
    db = _db_directory(directory)
    participants, pending = people.resolve_mentions(
        [{"name": "Sarah"}], coordinator_id="coord", db=db
    )
    assert participants == []
    assert pending["name"] == "Sarah"
    assert pending["reason"] == "ambiguous"
    assert {o["user_id"] for o in pending["options"]} == {"u-1", "u-2"}
    assert pending["options"][0].keys() == {"user_id", "full_name", "email"}


def test_bare_name_no_match_pending():
    directory = [_profile(user_id="u-1", full_name="Bob Jones")]
    db = _db_directory(directory)
    participants, pending = people.resolve_mentions(
        [{"name": "Zoltan"}], coordinator_id="coord", db=db
    )
    assert participants == []
    assert pending == {"name": "Zoltan", "reason": "no_match"}


def test_case_insensitive_full_name_match():
    directory = [_profile(user_id="u-1", full_name="Sarah Chen")]
    db = _db_directory(directory)
    participants, pending = people.resolve_mentions(
        [{"name": "sarah chen"}], coordinator_id="coord", db=db
    )
    assert pending is None
    assert participants[0]["user_id"] == "u-1"


# ─── LLM pairing (EmailPairing) ───────────────────────────────────────────────

def test_email_pairing_true_attaches_email(monkeypatch):
    """Bare name + loose email, FakeLLM says same person → resolved via email."""
    llm = FakeLLM(same_person=True)
    db = _db_email_lookup(_profile(user_id="u-5", full_name="Sarah Chen"))
    participants, pending = people.resolve_mentions(
        [{"name": "Sarah"}, {"email": "sarah@example.com"}],
        coordinator_id="coord",
        message="invite Sarah, her email is sarah@example.com",
        llm=llm,
        db=db,
    )
    assert pending is None
    # Only one participant (the email mention was consumed into the name).
    assert len(participants) == 1
    assert participants[0]["user_id"] == "u-5"
    assert participants[0]["source"] == "explicit_email"
    assert llm.schemas == [EmailPairing]


def test_email_pairing_false_keeps_them_separate():
    """FakeLLM says NOT same person → name goes to directory, email stands alone."""
    llm = FakeLLM(same_person=False)
    # Directory has no 'Sarah' → name yields a no_match pending; the loose email
    # is resolved independently (as an explicit-email miss) before that.
    directory = [_profile(user_id="u-9", full_name="Bob Jones")]

    ep = MagicMock()
    ep.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"event_id": "evt-1"}]
    )
    ep.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"user_id": "u-9"}]
    )
    profiles = MagicMock()
    # email lookup (eq) → miss; directory (in_) → Bob only
    profiles.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
    profiles.select.return_value.in_.return_value.execute.return_value = MagicMock(data=list(directory))
    tables = {"event_participants": ep, "profiles": profiles}
    db = MagicMock()
    db.table.side_effect = lambda name: tables.get(name, MagicMock())

    participants, pending = people.resolve_mentions(
        [{"email": "sarah@example.com"}, {"name": "Sarah"}],
        coordinator_id="coord",
        message="invite sarah@example.com and Sarah",
        llm=llm,
        db=db,
    )
    # The email mention resolved as an explicit-email miss (not paired).
    assert any(p["email"] == "sarah@example.com" and not p["in_system"] for p in participants)
    # The bare name found no directory match.
    assert pending == {"name": "Sarah", "reason": "no_match"}


# ─── awaiting-email helpers ───────────────────────────────────────────────────

def test_resolve_provided_email_hit():
    db = _db_email_lookup(_profile(user_id="u-3"))
    item = people.resolve_provided_email("sarah@example.com", db=db)
    assert item["user_id"] == "u-3"
    assert item["in_system"] is True
    assert item["source"] == "user_provided"


def test_resolve_provided_email_miss():
    db = _db_email_lookup(None)
    item = people.resolve_provided_email("nobody@company.com", name="Nobody", db=db)
    assert item == {
        "full_name": "Nobody",
        "email": "nobody@company.com",
        "in_system": False,
        "has_calendar": False,
        "source": "user_provided",
    }


def test_resolve_provided_user_id():
    directory = [_profile(user_id="u-7", full_name="Sarah Chen")]
    db = _db_directory(directory)
    item = people.resolve_provided_user_id("u-7", db=db)
    assert item["user_id"] == "u-7"
    assert item["source"] == "coparticipant"


def test_resolve_provided_user_id_missing_returns_none():
    db = _db_directory([_profile(user_id="u-7")])
    assert people.resolve_provided_user_id("does-not-exist", db=db) is None


# ─── Cap ──────────────────────────────────────────────────────────────────────

def test_cap_max_people():
    """Only the first MAX_CHAT_PEOPLE mentions are processed."""
    seen_emails = []

    profiles = MagicMock()

    def select(_cols):
        chain = MagicMock()

        def eq(col, val):
            seen_emails.append(val)
            m = MagicMock()
            m.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            return m

        chain.eq.side_effect = eq
        return chain

    profiles.select.side_effect = select
    db = MagicMock()
    db.table.side_effect = lambda name: profiles if name == "profiles" else MagicMock()

    mentions = [{"email": f"user{i}@company.com"} for i in range(people.MAX_CHAT_PEOPLE + 2)]
    participants, _ = people.resolve_mentions(mentions, coordinator_id="coord", db=db)

    assert len(participants) == people.MAX_CHAT_PEOPLE
    assert len(seen_emails) == people.MAX_CHAT_PEOPLE
