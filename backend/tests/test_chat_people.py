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


def _db_email_lookup(profile_or_none, captured_in=None):
    """A db whose profiles.in_(email_address, [...]) returns the matching row(s).

    Email resolution is now batched into one ``.in_()`` query. ``profile_or_none``
    is the single row a lookup should hit (or None for a miss); the fake returns
    it only for emails present in the queried list. If ``captured_in`` is given,
    the queried email list is appended to it.
    """
    db = MagicMock()
    profiles = MagicMock()

    def select(_cols):
        chain = MagicMock()

        def in_(col, values):
            if captured_in is not None:
                captured_in.append((col, list(values)))
            hit = profile_or_none
            rows = [hit] if (hit and hit["email_address"] in values) else []
            m = MagicMock()
            m.execute.return_value = MagicMock(data=rows)
            return m

        chain.in_.side_effect = in_
        return chain

    profiles.select.side_effect = select
    db.table.side_effect = lambda name: profiles if name == "profiles" else MagicMock()
    return db


def _peer_row(profile, user_id=None):
    """A co-participant row with its owner profile embedded (to-one)."""
    return {"user_id": user_id or profile["id"], "profiles": profile}


def _db_directory(directory_profiles, my_event_ids=("evt-1",), peer_rows=None,
                  email_profiles=(), captured_in=None):
    """A db that serves the co-participant directory query chain.

    - event_participants.select(event_id).eq(user_id).execute() → my_event_ids
    - event_participants.select(_PEER_COLUMNS).in_(event_id).execute()
        → peer rows with embedded ``profiles``
    - profiles.select(...).in_(email_address, [...]).execute() → ``email_profiles``
      whose address is in the queried list (the batched explicit-email lookup)
    - profiles.select(...).eq(id).maybe_single().execute() → by-id lookup
      (resolve_provided_user_id)
    """
    peer_rows = peer_rows if peer_rows is not None else [_peer_row(p) for p in directory_profiles]

    ep = MagicMock()
    ep.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"event_id": e} for e in my_event_ids]
    )
    ep.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=list(peer_rows)
    )

    by_id = {p["id"]: p for p in directory_profiles}
    email_by_addr = {p["email_address"]: p for p in email_profiles}
    profiles = MagicMock()

    def eq(col, val):
        m = MagicMock()
        m.maybe_single.return_value.execute.return_value = MagicMock(data=by_id.get(val))
        return m

    def in_(col, values):
        if captured_in is not None:
            captured_in.append((col, list(values)))
        m = MagicMock()
        m.execute.return_value = MagicMock(
            data=[email_by_addr[v] for v in values if v in email_by_addr]
        )
        return m

    profiles.select.return_value.eq.side_effect = eq
    profiles.select.return_value.in_.side_effect = in_

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
    db = _db_email_lookup(None, captured_in=captured)
    participants, _ = people.resolve_mentions(
        [{"email": "John.Doe@Gmail.com"}], coordinator_id="coord", db=db
    )
    # profiles lookup used the normalized (dots stripped, lowercased) address.
    assert ("email_address", ["johndoe@gmail.com"]) in captured
    assert participants[0]["email"] == "johndoe@gmail.com"


def test_has_calendar_false_when_no_accounts():
    db = _db_email_lookup(_profile(n_accounts=0))
    participants, _ = people.resolve_mentions(
        [{"email": "sarah@example.com"}], coordinator_id="coord", db=db
    )
    assert participants[0]["has_calendar"] is False
    assert participants[0]["in_system"] is True


def test_multiple_emails_resolved_in_one_query():
    """Several emailed invitees resolve via a single batched profiles lookup."""
    hit_a = _profile(user_id="u-a", full_name="Ann Lee", email="ann@example.com")
    hit_b = _profile(user_id="u-b", full_name="Ben Roy", email="ben@example.com")
    captured = []
    db = _db_directory([], email_profiles=[hit_a, hit_b], captured_in=captured)

    participants, pending = people.resolve_mentions(
        [{"email": "ann@example.com"}, {"email": "ben@example.com"},
         {"name": "Cara", "email": "cara@nowhere.com"}],
        coordinator_id="coord", db=db,
    )

    assert pending is None
    # Exactly one round-trip carrying all three emails (was one query per email).
    assert len(captured) == 1
    _, queried = captured[0]
    assert set(queried) == {"ann@example.com", "ben@example.com", "cara@nowhere.com"}
    # Two in-system hits + one non-user miss, order preserved.
    assert [(p["email"], p["in_system"]) for p in participants] == [
        ("ann@example.com", True),
        ("ben@example.com", True),
        ("cara@nowhere.com", False),
    ]


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


def test_directory_dedupes_peer_shared_across_events():
    """A peer who shares several events appears once (embed can return dupes)."""
    sarah = _profile(user_id="u-1", full_name="Sarah Chen")
    bob = _profile(user_id="u-2", full_name="Bob Jones")
    # Sarah co-participates on two of the coordinator's events → two peer rows.
    peer_rows = [_peer_row(sarah), _peer_row(bob), _peer_row(sarah),
                 {"user_id": "coord", "profiles": _profile(user_id="coord")}]
    db = _db_directory([sarah, bob], my_event_ids=("evt-1", "evt-2"), peer_rows=peer_rows)

    participants, pending = people.resolve_mentions(
        [{"name": "Sarah Chen"}], coordinator_id="coord", db=db,
    )
    assert pending is None
    assert participants[0]["user_id"] == "u-1"  # matched once, no ambiguity from the dupe


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
    # is an explicit-email miss (email_profiles empty) resolved independently.
    directory = [_profile(user_id="u-9", full_name="Bob Jones")]
    db = _db_directory(directory, email_profiles=[])

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


def test_email_pairing_llm_failure_degrades_instead_of_raising():
    """A raising pairing call must not abort the turn.

    chat_service has already persisted the user's message by the time the graph
    runs, so an exception escaping here would 500 the request and strand that
    message with no assistant reply. The name must instead fall through to the
    normal directory path (here: no match → the ask-email prompt).
    """

    class _RaisingLLM:
        def with_structured_output(self, schema):
            raise RuntimeError('Gemini unavailable')

    directory = [_profile(user_id="u-9", full_name="Bob Jones")]
    db = _db_directory(directory, email_profiles=[])

    participants, pending = people.resolve_mentions(
        [{"email": "sarah@example.com"}, {"name": "Sarah"}],
        coordinator_id="coord",
        message="invite sarah@example.com and Sarah",
        llm=_RaisingLLM(),
        db=db,
    )

    # Same outcome as an explicit "not the same person" verdict: unpaired, so the
    # email resolves on its own and the name goes to the directory (no match →
    # a normal pending ask). A crash here would have 500'd the turn instead.
    assert pending == {"name": "Sarah", "reason": "no_match"}
    assert any(p["email"] == "sarah@example.com" and not p["in_system"] for p in participants)


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
    """Only the first MAX_CHAT_PEOPLE mentions are processed (one batched query)."""
    captured = []
    db = _db_email_lookup(None, captured_in=captured)

    mentions = [{"email": f"user{i}@company.com"} for i in range(people.MAX_CHAT_PEOPLE + 2)]
    participants, _ = people.resolve_mentions(mentions, coordinator_id="coord", db=db)

    assert len(participants) == people.MAX_CHAT_PEOPLE
    # A single batched lookup carrying exactly the first MAX_CHAT_PEOPLE emails.
    assert len(captured) == 1
    _, queried_emails = captured[0]
    assert len(queried_emails) == people.MAX_CHAT_PEOPLE
