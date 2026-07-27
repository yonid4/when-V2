"""Package 5 — LangGraph agent-graph tests.

The model is INJECTED: every test builds the graph with ``build_graph(FakeLLM(...))``
so nothing hits the network. All service collaborators (``people`` /
``availability`` / ``booking`` / ``event_service``) are monkeypatched at their
agent-module import sites. The central invariant proven here: free text can NEVER
reach a write node — only a structured action dispatched by ``entry_router`` can.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.models.event import EventUpdate
from app.services import event_service
from agent_service import availability, booking, nodes, people
from agent_service.graph import build_graph, entry_router
from agent_service.llm import ExtractedTurn, build_extraction_prompt

REF = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)

WRITE_NODES = {'book_direct_node', 'create_in_app_node', 'apply_edit_node'}


# ─── FakeLLM ──────────────────────────────────────────────────────────────────

class _FakeStructured:
    """`.with_structured_output(schema).invoke(prompt)` → a canned instance.

    The prompt is handed back to the owning FakeLLM so tests can assert on what
    the extraction call was actually given.
    """

    def __init__(self, result, on_prompt):
        self._result = result
        self._on_prompt = on_prompt

    def invoke(self, prompt):
        self._on_prompt(prompt)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class FakeLLM:
    """Injected model. ``extracted`` is returned by the structured-output call.
    The graph never calls plain ``.invoke`` anymore (replies are deterministic
    templates); ``content`` / ``raise_reply`` exist to prove exactly that — a
    reply sourced from ``content`` or a crash on ``raise_reply`` would mean an
    LLM wording call snuck back in."""

    def __init__(self, *, extracted=None, content='Sure, here you go.', raise_reply=False):
        self._extracted = extracted
        self._content = content
        self._raise_reply = raise_reply
        # The prompt the extraction call last received.
        self.last_prompt: str | None = None

    def with_structured_output(self, schema):
        def _capture(prompt):
            self.last_prompt = prompt

        return _FakeStructured(self._extracted, _capture)

    def invoke(self, prompt):
        if self._raise_reply:
            raise RuntimeError('LLM down')
        return SimpleNamespace(content=self._content)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _base(**overrides) -> dict:
    state = {
        'user_id': 'u1',
        'user_token': 'tok',
        'user_email': 'alice@example.com',
        'user_full_name': 'Alice',
        'user_timezone': 'America/Los_Angeles',
        'reference_time_utc': REF,
        'user_message': None,
        'action': None,
        'status': 'idle',
        'workflow': None,
        'draft': None,
        'participants': None,
        'pending_people': None,
        'candidate_slots': None,
        'booking_mode': None,
    }
    state.update(overrides)
    return state


def _create_turn(**fields) -> ExtractedTurn:
    defaults = dict(
        intent='create_event', title='Lunch', event_type='social',
        start_date='2026-07-20', end_date='2026-07-20',
        start_time='12:00', end_time='14:00', duration_minutes=60,
    )
    defaults.update(fields)
    return ExtractedTurn(**defaults)


def _participant(**overrides) -> dict:
    p = {
        'user_id': 'u2', 'full_name': 'Bob', 'email': 'bob@example.com',
        'in_system': True, 'has_calendar': True, 'source': 'explicit_email',
    }
    p.update(overrides)
    return p


def _slot() -> dict:
    return {
        'start_time_utc': '2026-07-20T19:00:00+00:00',
        'end_time_utc': '2026-07-20T20:00:00+00:00',
        'conflict_count': 0, 'free_count': 2, 'total': 2, 'reasoning': '2/2 free',
    }


def _event_summary(**overrides) -> dict:
    s = {
        'uid': 'evt-A', 'name': 'Standup', 'status': 'planning',
        'earliest_datetime_utc': '2026-07-20T16:00:00+00:00',
        'latest_datetime_utc': '2026-07-20T23:00:00+00:00',
        'duration_minutes': 30, 'is_coordinator': True,
    }
    s.update(overrides)
    return s


# ─── create: people → choice / in-app confirmation ────────────────────────────

def test_all_in_system_linked_reaches_awaiting_choice(monkeypatch):
    """Everyone in-system + calendar-linked → the two-way booking choice."""
    monkeypatch.setattr(people, 'resolve_mentions', lambda mentions, **kw: ([_participant()], []))
    g = build_graph(FakeLLM(extracted=_create_turn(people=[{'name': 'Bob'}])))

    out = g.invoke(_base(user_message='lunch with bob'))

    assert out['status'] == 'awaiting_choice'
    assert len(out['buttons']) == 2
    types = {b['action']['type'] for b in out['buttons']}
    assert types == {'book_direct', 'use_in_app'}
    assert out['assistant_text']


def test_calendar_less_person_skips_to_in_app_confirmation(monkeypatch):
    """An in-system person without a connected calendar → straight to in-app."""
    monkeypatch.setattr(people, 'resolve_mentions',
                        lambda mentions, **kw: ([_participant(has_calendar=False)], []))
    g = build_graph(FakeLLM(extracted=_create_turn(people=[{'name': 'Bob'}])))

    out = g.invoke(_base(user_message='lunch with bob'))

    assert out['status'] == 'awaiting_confirmation'
    assert out['booking_mode'] == 'in_app'
    assert out['card']['mode'] == 'create_in_app'


def test_non_user_person_skips_to_in_app_confirmation(monkeypatch):
    """A non-user participant → in-app (invitation flow), never direct booking."""
    monkeypatch.setattr(people, 'resolve_mentions', lambda mentions, **kw: (
        [{'full_name': None, 'email': 'ext@example.com', 'in_system': False,
          'has_calendar': False, 'source': 'explicit_email'}], []))
    g = build_graph(FakeLLM(extracted=_create_turn(people=[{'email': 'ext@example.com'}])))

    out = g.invoke(_base(user_message='lunch with ext@example.com'))

    assert out['status'] == 'awaiting_confirmation'
    assert out['booking_mode'] == 'in_app'
    assert out['card']['mode'] == 'create_in_app'


# ─── create: book_direct → slots → confirmation ───────────────────────────────

def test_book_direct_computes_slots_and_confirmation(monkeypatch):
    """awaiting_choice + book_direct → ranked slots → direct confirmation card."""
    monkeypatch.setattr(availability, 'ensure_fresh_busy_slots', lambda *a, **k: [])
    monkeypatch.setattr(availability, 'rank_candidate_slots', lambda *a, **k: [_slot()])
    g = build_graph(FakeLLM())

    draft = {'title': 'Lunch', 'event_type': 'social',
             'earliest_datetime_utc': '2026-07-20T19:00:00+00:00',
             'latest_datetime_utc': '2026-07-20T21:00:00+00:00',
             'duration_minutes': 60, 'local': {}, 'people': []}
    out = g.invoke(_base(status='awaiting_choice', workflow='create_event',
                         draft=draft, participants=[_participant()],
                         action={'type': 'book_direct'}))

    assert out['status'] == 'awaiting_confirmation'
    assert out['booking_mode'] == 'direct'
    assert out['card']['mode'] == 'create_direct'
    assert len(out['card']['slots']) == 1
    assert {b['action']['type'] for b in out['buttons']} == {'confirm_draft', 'cancel'}


def test_no_slots_stays_at_choice_and_offers_in_app(monkeypatch):
    """No free slot in the window → stay awaiting_choice, offer in-app."""
    monkeypatch.setattr(availability, 'ensure_fresh_busy_slots', lambda *a, **k: [])
    monkeypatch.setattr(availability, 'rank_candidate_slots', lambda *a, **k: [])
    g = build_graph(FakeLLM())

    draft = {'title': 'Lunch', 'earliest_datetime_utc': '2026-07-20T19:00:00+00:00',
             'latest_datetime_utc': '2026-07-20T21:00:00+00:00', 'duration_minutes': 60}
    out = g.invoke(_base(status='awaiting_choice', workflow='create_event',
                         draft=draft, participants=[_participant()],
                         action={'type': 'book_direct'}))

    assert out['status'] == 'awaiting_choice'
    assert out['candidate_slots'] == []
    assert [b['action']['type'] for b in out['buttons']] == ['use_in_app']


# ─── confirm_draft dispatch by workflow / booking_mode ────────────────────────

def test_confirm_dispatches_to_book_direct(monkeypatch):
    """awaiting_confirmation + confirm_draft + booking_mode=direct → book_direct."""
    calls = {}

    def fake_book_direct(user, draft, participants, slot, ref):
        calls['slot'] = slot
        return {'event_uid': 'evt-booked'}

    monkeypatch.setattr(booking, 'book_direct', fake_book_direct)
    g = build_graph(FakeLLM())

    out = g.invoke(_base(status='awaiting_confirmation', workflow='create_event',
                         booking_mode='direct', draft={'title': 'Lunch'},
                         participants=[_participant()], candidate_slots=[_slot()],
                         action={'type': 'confirm_draft', 'slot_index': 0}))

    assert calls['slot'] == _slot()
    assert out['status'] == 'idle'
    assert out['result_event_uid'] == 'evt-booked'
    assert out['result_created'] is True  # new event → client navigates to it
    assert out['workflow'] is None and out['draft'] is None


def test_confirm_dispatches_to_create_in_app(monkeypatch):
    """awaiting_confirmation + confirm_draft + booking_mode=in_app → in-app create."""
    monkeypatch.setattr(booking, 'create_in_app_event',
                        lambda user, draft, participants: {'event_uid': 'evt-inapp'})
    g = build_graph(FakeLLM())

    out = g.invoke(_base(status='awaiting_confirmation', workflow='create_event',
                         booking_mode='in_app', draft={'title': 'Lunch'},
                         participants=[_participant(in_system=False)],
                         action={'type': 'confirm_draft'}))

    assert out['status'] == 'idle'
    assert out['result_event_uid'] == 'evt-inapp'
    assert out['result_created'] is True  # new event → client navigates to it


def test_book_direct_invalid_slot_index_errors(monkeypatch):
    """A slot_index outside the persisted candidates is rejected (no booking)."""
    called = {'n': 0}
    monkeypatch.setattr(booking, 'book_direct',
                        lambda *a, **k: called.__setitem__('n', called['n'] + 1))
    g = build_graph(FakeLLM())

    out = g.invoke(_base(status='awaiting_confirmation', workflow='create_event',
                         booking_mode='direct', draft={'title': 'Lunch'},
                         participants=[_participant()], candidate_slots=[_slot()],
                         action={'type': 'confirm_draft', 'slot_index': 5}))

    assert called['n'] == 0
    assert out['status'] == 'awaiting_confirmation'
    assert out['assistant_text']


# ─── cancel clears ────────────────────────────────────────────────────────────

def test_cancel_clears_workflow_state():
    g = build_graph(FakeLLM())
    out = g.invoke(_base(status='awaiting_confirmation', workflow='create_event',
                         booking_mode='direct', draft={'title': 'Lunch'},
                         participants=[_participant()], candidate_slots=[_slot()],
                         action={'type': 'cancel'}))

    assert out['status'] == 'idle'
    assert out['workflow'] is None
    assert out['draft'] is None
    assert out['participants'] is None
    assert out['candidate_slots'] is None
    assert out['assistant_text']


# ─── awaiting_email loop ──────────────────────────────────────────────────────

def test_awaiting_email_loop_ambiguous_then_pick(monkeypatch):
    """Ambiguous name → pick-person buttons; picking one resolves + advances."""
    pending = {
        'name': 'Sarah', 'reason': 'ambiguous',
        'options': [
            {'user_id': 's1', 'full_name': 'Sarah Chen', 'email': 'sc@example.com'},
            {'user_id': 's2', 'full_name': 'Sarah Lee', 'email': 'sl@example.com'},
        ],
    }

    def fake_resolve_mentions(mentions, **kw):
        if not mentions:
            return [], []
        return [], [pending]

    monkeypatch.setattr(people, 'resolve_mentions', fake_resolve_mentions)

    # Turn 1: ambiguous → awaiting_email with two pick_person buttons.
    g = build_graph(FakeLLM(extracted=_create_turn(people=[{'name': 'Sarah'}])))
    out1 = g.invoke(_base(user_message='lunch with sarah'))
    assert out1['status'] == 'awaiting_email'
    assert [b['action']['type'] for b in out1['buttons']] == ['pick_person', 'pick_person']

    # Turn 2: pick a person → resolve + loop → reaches the choice.
    monkeypatch.setattr(people, 'resolve_provided_user_id',
                        lambda uid, **kw: _participant(user_id=uid, full_name='Sarah Chen',
                                                       source='coparticipant'))
    out2 = g.invoke(_base(status='awaiting_email', workflow='create_event',
                          draft=out1['draft'], participants=out1['participants'],
                          pending_people=out1['pending_people'],
                          action={'type': 'pick_person', 'person_name': 'Sarah', 'user_id': 's1'}))
    assert out2['pending_people'] == []
    assert out2['status'] == 'awaiting_choice'
    assert any(p['user_id'] == 's1' for p in out2['participants'])


def test_awaiting_email_free_text_email_resolves(monkeypatch):
    """A bare email typed while awaiting_email routes to apply_email and resolves."""
    monkeypatch.setattr(people, 'resolve_provided_email',
                        lambda email, **kw: _participant(email=email, source='user_provided'))
    g = build_graph(FakeLLM())

    out = g.invoke(_base(status='awaiting_email', workflow='create_event',
                         draft={'title': 'Lunch', 'people': []},
                         participants=[],
                         pending_people=[{'name': 'Bob', 'reason': 'no_match'}],
                         user_message='his email is bob@example.com'))

    assert out['pending_people'] == []
    assert any(p['email'] == 'bob@example.com' for p in out['participants'])


def test_awaiting_email_bulk_reply_resolves_all(monkeypatch):
    """One free-text reply with many emails resolves every no-match name at once —
    name-hint pairs where it can, positional fills the rest, then it advances."""
    monkeypatch.setattr(people, 'resolve_provided_email',
                        lambda email, *, name=None, **kw: _participant(
                            user_id=None, full_name=name, email=email,
                            in_system=False, has_calendar=False, source='user_provided'))
    g = build_graph(FakeLLM())

    pending = [{'name': 'Sarah', 'reason': 'no_match'},
               {'name': 'John', 'reason': 'no_match'},
               {'name': 'Mike', 'reason': 'no_match'}]
    out = g.invoke(_base(status='awaiting_email', workflow='create_event',
                         draft={'title': 'Lunch', 'people': []}, participants=[],
                         pending_people=pending,
                         user_message='sarah@acme.com, mike@corp.com, and john@x.com'))

    assert out['pending_people'] == []
    # Name-hint pairs each email to its person despite the out-of-order list.
    by_email = {p['email']: p['full_name'] for p in out['participants']}
    assert by_email == {
        'sarah@acme.com': 'Sarah', 'mike@corp.com': 'Mike', 'john@x.com': 'John',
    }
    # Everyone resolved → the flow advances past awaiting_email.
    assert out['status'] != 'awaiting_email'


def test_awaiting_email_partial_bulk_reply_reasks(monkeypatch):
    """A reply that covers only some pending names resolves those and re-asks for
    the remainder (stays awaiting_email)."""
    monkeypatch.setattr(people, 'resolve_provided_email',
                        lambda email, *, name=None, **kw: _participant(
                            user_id=None, full_name=name, email=email,
                            in_system=False, has_calendar=False, source='user_provided'))
    g = build_graph(FakeLLM())

    pending = [{'name': 'Sarah', 'reason': 'no_match'},
               {'name': 'John', 'reason': 'no_match'}]
    out = g.invoke(_base(status='awaiting_email', workflow='create_event',
                         draft={'title': 'Lunch', 'people': []}, participants=[],
                         pending_people=pending,
                         user_message='sarah@acme.com'))

    assert out['status'] == 'awaiting_email'
    assert [p['name'] for p in out['pending_people']] == ['John']
    assert any(p['email'] == 'sarah@acme.com' for p in out['participants'])
    assert 'John' in out['assistant_text']


# ─── carrying people across turns + turn scope ────────────────────────────────

def _pend_everyone(mentions, **kw):
    """resolve_mentions stub: nobody is in the directory, so every name goes pending."""
    return [], [{'name': m['name'], 'reason': 'no_match'} for m in mentions if m.get('name')]


def test_named_people_survive_a_follow_up_turn(monkeypatch):
    """Names given before the date are still asked about after it (the reported bug).

    Turn 1 names three people but gives no date, so the turn stops to ask for one.
    Turn 2 supplies only the date — the model correctly reports NO people (it is told
    not to repeat them), and the three names must survive in the draft rather than
    being overwritten by that empty list.
    """
    monkeypatch.setattr(people, 'resolve_mentions', _pend_everyone)
    names = [{'name': 'shalom'}, {'name': 'gil'}, {'name': 'halon'}]

    # Turn 1 — people, no date.
    g1 = build_graph(FakeLLM(extracted=_create_turn(
        title='lunch', people=names, start_date=None, end_date=None)))
    out1 = g1.invoke(_base(user_message='create a lunch event with shalom, gil, and halon'))

    assert out1['status'] == 'collecting'
    assert [m['name'] for m in out1['draft']['people']] == ['shalom', 'gil', 'halon']

    # Turn 2 — date only; the extraction reports no people, exactly as instructed.
    g2 = build_graph(FakeLLM(extracted=_create_turn(title=None, people=[])))
    out2 = g2.invoke(_base(status='collecting', workflow='create_event',
                           draft=out1['draft'], participants=out1.get('participants'),
                           user_message='this week'))

    # It asks for their emails instead of offering to book an event for nobody.
    assert out2['status'] == 'awaiting_email'
    assert [p['name'] for p in out2['pending_people']] == ['shalom', 'gil', 'halon']
    assert all(n in out2['assistant_text'] for n in ('shalom', 'gil', 'halon'))


def test_no_participants_goes_to_in_app_not_the_booking_choice(monkeypatch):
    """A solo event skips the two-way choice — all([]) must not read as 'all bookable'."""
    monkeypatch.setattr(people, 'resolve_mentions', lambda mentions, **kw: ([], []))
    g = build_graph(FakeLLM(extracted=_create_turn(title='deep work', people=[])))

    out = g.invoke(_base(user_message='block 2 hours for deep work this week'))

    assert out['status'] == 'awaiting_confirmation'
    assert out['booking_mode'] == 'in_app'
    assert {b['action']['type'] for b in out['buttons']} == {'confirm_draft', 'cancel'}


def test_replaces_people_restarts_the_guest_list_but_keeps_the_event(monkeypatch):
    """scope='replaces_people' clears everyone and everything derived from them,
    while the event's own facts survive."""
    monkeypatch.setattr(people, 'resolve_mentions', _pend_everyone)
    g = build_graph(FakeLLM(extracted=_create_turn(
        title=None, scope='replaces_people', people=[{'name': 'gil'}])))

    out = g.invoke(_base(
        status='awaiting_email', workflow='create_event',
        draft={'title': 'lunch', 'people': [],
               'local': {'start_date': '2026-07-20', 'end_date': '2026-07-20',
                         'start_time': '12:00', 'end_time': '14:00'}},
        participants=[_participant()],
        pending_people=[{'name': 'zed', 'reason': 'no_match'}],
        candidate_slots=[_slot()], booking_mode='direct',
        user_message='actually just gil'))

    # The old roster and everything derived from it is gone...
    assert out['participants'] == []
    assert [p['name'] for p in out['pending_people']] == ['gil']
    assert out['candidate_slots'] == []
    assert out['booking_mode'] is None
    # ...but the event itself survives, and the discard is announced.
    assert out['draft']['title'] == 'lunch'
    assert out['assistant_text'].startswith('Starting the guest list over.')


def test_new_event_rebuilds_the_draft_from_this_turn_only(monkeypatch):
    """scope='new_event' discards the prior draft's facts as well as its people."""
    monkeypatch.setattr(people, 'resolve_mentions', lambda mentions, **kw: ([], []))
    g = build_graph(FakeLLM(extracted=_create_turn(
        title='dentist', scope='new_event', people=[],
        start_date='2026-07-24', end_date='2026-07-24')))

    out = g.invoke(_base(
        status='collecting', workflow='create_event',
        draft={'title': 'lunch', 'people': [{'name': 'gil'}],
               'local': {'start_date': '2026-07-20', 'end_date': '2026-07-20',
                         'start_time': '12:00', 'end_time': '14:00'}},
        participants=[_participant()], pending_people=[{'name': 'zed', 'reason': 'no_match'}],
        user_message="forget that, new event — dentist friday"))

    assert out['draft']['title'] == 'dentist'
    assert out['draft']['local']['start_date'] == '2026-07-24'
    assert out['draft']['people'] == []
    assert out['participants'] == []
    assert out['pending_people'] == []
    assert out['assistant_text'].startswith('Starting a new event.')


def test_scope_defaults_to_revision_so_omitting_it_keeps_state():
    """An extraction that never mentions scope must not discard anything."""
    assert ExtractedTurn(intent='create_event').scope == 'revision'


def test_merge_keeps_mention_order_and_prefers_the_one_with_an_email():
    """A later email upgrades the bare name in place; order is carried-forward first."""
    merged = nodes._merge_mentions(
        [{'name': 'shalom', 'email': None}, {'name': 'gil', 'email': None}],
        [{'name': 'Gil', 'email': 'gil@x.com'}, {'name': 'halon', 'email': None}],
    )
    assert [m['name'] for m in merged] == ['shalom', 'gil', 'halon']
    assert merged[1]['email'] == 'gil@x.com'


def test_unresolved_mentions_reach_the_extraction_prompt(monkeypatch):
    """Names the app is still holding are shown to the model, so a late email can be
    attributed to the right person."""
    monkeypatch.setattr(people, 'resolve_mentions', _pend_everyone)
    llm = FakeLLM(extracted=_create_turn(title=None, people=[]))
    g = build_graph(llm)

    g.invoke(_base(status='collecting', workflow='create_event',
                   draft={'title': 'lunch', 'people': [{'name': 'shalom'}, {'name': 'gil'}]},
                   user_message='this week'))

    prompt = llm.last_prompt or ''
    assert 'People mentioned but not yet resolved' in prompt
    assert 'shalom' in prompt and 'gil' in prompt


def test_both_resets_derive_from_one_channel_list():
    """The full clear and the scope reset must never drift apart."""
    assert set(nodes._WORKFLOW_CHANNELS) <= set(nodes._clear_workflow_state())
    assert set(nodes._people_reset()) == set(nodes._WORKFLOW_CHANNELS) - {'draft'}


# ─── edit workflow ────────────────────────────────────────────────────────────

def test_edit_with_page_context_builds_before_after(monkeypatch):
    """Page context + a rename → edit confirmation with a before/after change."""
    g = build_graph(FakeLLM(extracted=ExtractedTurn(intent='edit_event', edit_name='Team Sync')))

    out = g.invoke(_base(user_message='rename this event to Team Sync',
                         page_context=_event_summary()))

    assert out['workflow'] == 'edit_event'
    assert out['status'] == 'awaiting_confirmation'
    assert out['card']['mode'] == 'edit'
    changes = out['card']['changes']
    assert len(changes) == 1
    assert changes[0]['field'] == 'name'
    assert changes[0]['from'] == 'Standup'
    assert changes[0]['to'] == 'Team Sync'
    # Raw change map (for EventUpdate) is pinned on the draft.
    assert out['draft']['changes']['name']['to'] == 'Team Sync'


def test_edit_without_context_asks_to_open_event():
    # raise_reply → the deterministic template (asserted below) shows through.
    g = build_graph(FakeLLM(extracted=ExtractedTurn(intent='edit_event', edit_name='X'), raise_reply=True))
    out = g.invoke(_base(user_message='rename the event'))

    assert out['status'] == 'idle'
    assert out['workflow'] is None
    assert 'open the event' in out['assistant_text'].lower()


def test_edit_confirmed_event_is_rejected():
    """A non-planning (confirmed) event can't be edited here yet."""
    g = build_graph(FakeLLM(extracted=ExtractedTurn(intent='edit_event', edit_name='X'), raise_reply=True))
    out = g.invoke(_base(user_message='rename this event',
                         page_context=_event_summary(status='confirmed')))

    assert out['status'] != 'awaiting_confirmation'
    assert 'confirmed' in out['assistant_text'].lower()


def test_edit_non_coordinator_is_rejected():
    g = build_graph(FakeLLM(extracted=ExtractedTurn(intent='edit_event', edit_name='X'), raise_reply=True))
    out = g.invoke(_base(user_message='rename this event',
                         page_context=_event_summary(is_coordinator=False)))

    assert 'coordinator' in out['assistant_text'].lower()


def test_edit_confirm_calls_update_event_with_exact_payload(monkeypatch):
    """confirm_draft on an edit → update_event(uid, EventUpdate(...)) exactly."""
    captured = {}

    def fake_update(uid, data, current_user):
        captured['uid'] = uid
        captured['data'] = data
        return SimpleNamespace(uid=uid)

    monkeypatch.setattr(event_service, 'update_event', fake_update)

    # Build the edit draft, then confirm it.
    g = build_graph(FakeLLM(extracted=ExtractedTurn(intent='edit_event', edit_name='Team Sync')))
    built = g.invoke(_base(user_message='rename to Team Sync', page_context=_event_summary()))

    out = g.invoke(_base(status='awaiting_confirmation', workflow='edit_event',
                         draft=built['draft'], action={'type': 'confirm_draft'}))

    assert captured['uid'] == 'evt-A'
    assert isinstance(captured['data'], EventUpdate)
    assert captured['data'].model_dump(exclude_none=True) == {'name': 'Team Sync'}
    assert out['status'] == 'idle'
    assert out['result_event_uid'] == 'evt-A'
    assert not out.get('result_created')  # an edit is not a new event → no navigation


def test_edit_navigation_keeps_pinned_uid(monkeypatch):
    """An edit pinned on event A survives navigating to event B mid-flow."""
    # Turn 1: focus event A, no concrete change yet → pin A, ask what to change.
    g1 = build_graph(FakeLLM(extracted=ExtractedTurn(intent='edit_event')))
    turn1 = g1.invoke(_base(user_message='edit this event', page_context=_event_summary(uid='evt-A')))
    assert turn1['workflow'] == 'edit_event'
    assert turn1['draft']['event_uid'] == 'evt-A'

    # Turn 2: user is now viewing event B, but the pinned A must win.
    g2 = build_graph(FakeLLM(extracted=ExtractedTurn(intent='edit_event', edit_name='Renamed')))
    turn2 = g2.invoke(_base(status='collecting', workflow='edit_event',
                            draft=turn1['draft'], user_message='rename to Renamed',
                            page_context=_event_summary(uid='evt-B', name='Other')))

    assert turn2['draft']['event_uid'] == 'evt-A'
    assert turn2['card']['event_uid'] == 'evt-A'


# ─── compose_reply: deterministic templates, no LLM ───────────────────────────

def test_compose_reply_uses_deterministic_template():
    """Replies come from the outcome templates — never from LLM wording."""
    g = build_graph(FakeLLM(extracted=ExtractedTurn(intent='other'), content='Polished reply!'))
    out = g.invoke(_base(user_message='what can you do'))
    assert 'schedule' in out['assistant_text'].lower()
    assert out['assistant_text'] != 'Polished reply!'


def test_compose_reply_never_calls_the_llm():
    """compose_reply makes no plain ``.invoke`` call (raise_reply would crash it)."""
    g = build_graph(FakeLLM(extracted=ExtractedTurn(intent='other'), raise_reply=True))
    out = g.invoke(_base(user_message='what is the weather'))
    assert 'schedule' in out['assistant_text'].lower()


def test_classify_failure_degrades_to_apology():
    """A hard structured-output failure yields a deterministic apology, no crash."""
    g = build_graph(FakeLLM(extracted=RuntimeError('bad json')))
    out = g.invoke(_base(user_message='schedule something'))
    assert out['status'] == 'idle'
    assert out['assistant_text']


# ─── Conversation history in the extraction prompt ────────────────────────────

HISTORY = [
    {'role': 'user', 'content': 'Dinner with Sarah'},
    {'role': 'assistant', 'content': 'When should this happen?'},
]


def test_history_reaches_the_extraction_prompt():
    """Prior turns are in the prompt, oldest-first, with the latest message last."""
    llm = FakeLLM(extracted=_create_turn())
    g = build_graph(llm)
    g.invoke(_base(status='collecting', workflow='create_event',
                   user_message='next Tuesday', history=HISTORY))

    prompt = llm.last_prompt or ''
    assert 'Dinner with Sarah' in prompt
    assert 'When should this happen?' in prompt
    assert prompt.index('Dinner with Sarah') < prompt.index('When should this happen?')
    # The message being classified is the last thing the model reads.
    assert prompt.endswith("Latest user message: 'next Tuesday'")
    # The rule that keeps a terse follow-up on the same intent.
    assert 'IN THE CONTEXT of the conversation' in prompt


def test_no_history_omits_the_conversation_block():
    """A first message carries no conversation block (nothing to reference)."""
    llm = FakeLLM(extracted=_create_turn())
    g = build_graph(llm)
    g.invoke(_base(user_message='lunch on Friday', history=[]))

    prompt = llm.last_prompt or ''
    assert 'Conversation so far' not in prompt
    assert prompt.endswith("Latest user message: 'lunch on Friday'")


def test_history_is_labelled_by_role():
    """Roles are explicit so the model can tell its own questions from the user's."""
    prompt = build_extraction_prompt(
        user_message='next Tuesday', current_draft=None, participants=None,
        page_context=None, workflow='create_event', today_str='2026-07-18',
        weekday='Saturday', tz_name='America/Los_Angeles', history=HISTORY,
    )
    assert "user: 'Dinner with Sarah'" in prompt
    assert "assistant: 'When should this happen?'" in prompt


# ─── Entry-router table: free text NEVER reaches a write node ──────────────────

ROUTER_CASES = [
    # (status, workflow, action, message, booking_mode, expected)
    ('idle', None, None, 'schedule lunch', None, 'classify_and_extract'),
    ('collecting', 'create_event', None, 'next tuesday', None, 'classify_and_extract'),
    ('awaiting_choice', 'create_event', None, 'make it 90 minutes', None, 'classify_and_extract'),
    ('awaiting_confirmation', 'create_event', None, 'change the title', 'direct', 'classify_and_extract'),
    ('awaiting_confirmation', 'edit_event', None, 'actually rename it', None, 'classify_and_extract'),
    ('awaiting_email', 'create_event', None, 'not an email at all', None, 'classify_and_extract'),
    ('awaiting_email', 'create_event', None, 'reach him at bob@example.com', None, 'apply_email'),
    ('awaiting_email', 'create_event', {'type': 'provide_email', 'email': 'x@y.com'}, None, None, 'apply_email'),
    ('awaiting_email', 'create_event', {'type': 'pick_person', 'user_id': 'u2'}, None, None, 'apply_email'),
    ('awaiting_choice', 'create_event', {'type': 'book_direct'}, None, None, 'compute_slots'),
    ('awaiting_choice', 'create_event', {'type': 'use_in_app'}, None, None, 'prepare_confirmation'),
    ('awaiting_confirmation', 'create_event', {'type': 'confirm_draft'}, None, 'direct', 'book_direct_node'),
    ('awaiting_confirmation', 'create_event', {'type': 'confirm_draft'}, None, 'in_app', 'create_in_app_node'),
    ('awaiting_confirmation', 'edit_event', {'type': 'confirm_draft'}, None, None, 'apply_edit_node'),
    ('awaiting_confirmation', 'create_event', {'type': 'cancel'}, None, 'direct', 'cancel_node'),
    ('idle', None, {'type': 'cancel'}, None, None, 'cancel_node'),
    # A stray confirm outside a waiting state is treated as free text, not a write.
    ('idle', None, {'type': 'confirm_draft'}, None, None, 'classify_and_extract'),
    ('collecting', 'create_event', {'type': 'book_direct'}, None, None, 'classify_and_extract'),
]


@pytest.mark.parametrize('status,workflow,action,message,booking_mode,expected', ROUTER_CASES)
def test_entry_router_dispatch(status, workflow, action, message, booking_mode, expected):
    state = _base(status=status, workflow=workflow, action=action,
                  user_message=message, booking_mode=booking_mode)
    assert entry_router(state) == expected


def test_entry_router_free_text_never_reaches_write_nodes():
    """Exhaustive guard: no action-less (free-text) turn ever routes to a write."""
    for status, workflow, action, message, booking_mode, expected in ROUTER_CASES:
        if action is None:
            assert expected not in WRITE_NODES
    # And every write-node destination in the table required a structured action.
    for status, workflow, action, message, booking_mode, expected in ROUTER_CASES:
        if expected in WRITE_NODES:
            assert action is not None and action.get('type') == 'confirm_draft'
