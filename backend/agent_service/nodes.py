"""Create-workflow + shared graph nodes (Package 5).

Every node is a pure function of ``AgentState`` returning a sparse partial
update. Only ``classify_and_extract``, ``resolve_people`` and ``compose_reply``
touch the injected ``llm`` (via node factories that close over it); everything
else is deterministic Python. Nodes set an internal ``route`` key naming the next
node so the graph's conditional edges are trivial ``state['route']`` lookups —
routing is 100% deterministic and never LLM-driven.

The LLM is confined to: (a) intent classification + field extraction
(``classify_and_extract``), (b) name↔email pairing (inside ``people`` via
``resolve_people``), and (c) reply wording (``compose_reply``). It never selects
a slot and never decides control flow.
"""

import logging
import re
from datetime import date, datetime, time, timezone

from app.models.chat import (
    ChatActionPayload,
    ChatButton,
    DraftCard,
    DraftCardParticipant,
    DraftCardSlot,
    EditChange,
)
from app.models.user import User
from agent_service import availability, booking, people
from agent_service import llm as llm_mod
from app.utils import dates

logger = logging.getLogger(__name__)

_EVENT_TYPES = {'meeting', 'social', 'birthday', 'other'}
_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')

# Code-level fallback for a window with no stated time-of-day (business hours).
_DEFAULT_START_TIME = '09:00'
_DEFAULT_END_TIME = '17:00'


# ─── Small shared helpers ─────────────────────────────────────────────────────

def _first(*vals):
    """Return the first non-empty value, else ``None`` (merge helper)."""
    for v in vals:
        if v not in (None, ''):
            return v
    return None


def _valid_event_type(value) -> str:
    """Clamp an extracted event_type to the allowed set (default 'meeting')."""
    return value if value in _EVENT_TYPES else 'meeting'


def _parse_time(value: str) -> time:
    """Parse an ``HH:MM`` local time string (tolerant of unpadded hours)."""
    return datetime.strptime(value.strip(), '%H:%M').time()


def _extract_email(text) -> str | None:
    """Regex the first email address out of free text, or ``None``."""
    if not text:
        return None
    match = _EMAIL_RE.search(text)
    return match.group(0) if match else None


def _user_from_state(state) -> User:
    """Reconstruct the request ``User`` for write paths (booking / edit)."""
    return User(
        id=state['user_id'],
        email_address=state.get('user_email') or '',
        full_name=state.get('user_full_name'),
        timezone=state.get('user_timezone'),
        token=state.get('user_token') or '',
    )


def _fmt(value, tz_name, fmt: str) -> str:
    """Format a UTC instant (datetime or ISO string) as local wall-clock text."""
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return dates.format_utc_in_tz(dt, tz_name, fmt)


def _format_window(draft: dict, tz_name) -> str:
    """Human window string for a create draft, or '' when incomplete."""
    e, l = draft.get('earliest_datetime_utc'), draft.get('latest_datetime_utc')
    if not e or not l:
        return ''
    return f"{_fmt(e, tz_name, '%a %b %d %H:%M')} to {_fmt(l, tz_name, '%a %b %d %H:%M')}"


def _format_slot(slot: dict, tz_name) -> str:
    """Human string for one candidate slot (fixed — never reinterpreted by LLM)."""
    return (
        f"{_fmt(slot['start_time_utc'], tz_name, '%a %b %d %H:%M')}"
        f"-{_fmt(slot['end_time_utc'], tz_name, '%H:%M')}"
    )


def _participant_cards(participants) -> list[DraftCardParticipant]:
    return [
        DraftCardParticipant(
            name=p.get('full_name'),
            email=p.get('email') or '',
            in_system=bool(p.get('in_system')),
            has_calendar=bool(p.get('has_calendar')),
            user_id=p.get('user_id'),
        )
        for p in (participants or [])
    ]


def _draft_card(draft: dict, participants, *, mode=None, slots=None) -> DraftCard:
    return DraftCard(
        mode=mode,
        title=draft.get('title') or 'Untitled',
        event_type=draft.get('event_type'),
        earliest_datetime_utc=draft.get('earliest_datetime_utc'),
        latest_datetime_utc=draft.get('latest_datetime_utc'),
        duration_minutes=draft.get('duration_minutes'),
        participants=_participant_cards(participants),
        slots=[DraftCardSlot(**s) for s in (slots or [])],
    )


def _dump(model) -> dict:
    """JSON-safe dict for jsonb persistence (aliases on, None dropped)."""
    return model.model_dump(mode='json', by_alias=True, exclude_none=True)


def _button(label: str, action: dict) -> dict:
    """A ChatButton echoing a ChatActionPayload-shaped action, JSON-safe."""
    return _dump(ChatButton(label=label, action=ChatActionPayload(**action)))


def _clear_workflow_state() -> dict:
    """Reset all workflow channels to idle (used after success / cancel)."""
    return {
        'status': 'idle',
        'workflow': None,
        'draft': None,
        'participants': None,
        'pending_person': None,
        'candidate_slots': None,
        'booking_mode': None,
        'card': None,
        'buttons': [],
    }


def _apply_edits(draft: dict, edits) -> dict:
    """Apply last-minute confirm-time edits (title/duration/location) to a draft."""
    if not edits:
        return draft
    for key in ('title', 'duration_minutes', 'location'):
        value = edits.get(key)
        if value is not None:
            draft[key] = value
    return draft


def _dedupe_participants(participants: list) -> list:
    """Drop duplicate participants by (user_id or email), preserving order."""
    seen: set = set()
    out: list = []
    for p in participants:
        key = p.get('user_id') or (p.get('email') or '').lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(p)
    return out


def _mentions_after(mentions: list, name) -> list:
    """Mentions following the first one whose name matches ``name`` (casefolded).

    Used by the awaiting-email loop: when ``resolve_mentions`` stops at a pending
    person, everything after that mention is still unprocessed and is stashed for
    the next round (the pending person itself is resolved by ``apply_email``).
    """
    if not name:
        return []
    target = str(name).casefold()
    for i, m in enumerate(mentions):
        if (str(m.get('name') or '')).strip().casefold() == target:
            return mentions[i + 1:]
    return []


# ─── classify_and_extract (LLM) ───────────────────────────────────────────────

def make_classify_and_extract(llm):
    """Factory: the single structured intent/field-extraction node.

    One structured-output call (retried once) → ``ExtractedTurn``. Routes to
    ``validate_edit`` for edit intent, ``validate_intent`` otherwise. On a hard
    LLM failure it degrades to a deterministic apology (never crashes the turn).
    """

    def classify_and_extract(state):
        tz = state.get('user_timezone')
        today = dates.local_today(state['reference_time_utc'], tz)
        prompt = llm_mod.build_extraction_prompt(
            user_message=state.get('user_message') or '',
            current_draft=state.get('draft'),
            participants=state.get('participants'),
            page_context=state.get('page_context'),
            workflow=state.get('workflow'),
            today_str=today.isoformat(),
            weekday=today.strftime('%A'),
            tz_name=tz,
        )
        extracted = None
        for _ in range(2):
            try:
                extracted = llm.with_structured_output(llm_mod.ExtractedTurn).invoke(prompt)
                break
            except Exception:
                logger.exception("chat agent extraction LLM call failed")
                extracted = None
        if extracted is None:
            return {
                'intent': 'error',
                'reply': {'kind': 'apology', 'facts': {}},
                'route': 'compose_reply',
            }
        route = 'validate_edit' if extracted.intent == 'edit_event' else 'validate_intent'
        return {'extracted': extracted, 'intent': extracted.intent, 'route': route}

    return classify_and_extract


# ─── validate_intent (deterministic, create) ─────────────────────────────────

def _need_info_question(missing: list[str]) -> str:
    return "To set this up I need " + ", ".join(missing) + "."


def validate_intent(state):
    """Deterministic create validation + draft construction.

    'other' intent → help text. Missing title/date → a question (status
    'collecting', partial draft kept so revisions merge). Otherwise builds the UTC
    window via ``local_window_to_utc``, clamps duration to 15-480, rejects
    all-past windows, and hands off to ``resolve_people``. Participants are reset
    only when a brand-new event starts (status idle/None); revisions preserve
    already-resolved people.
    """
    extracted = state.get('extracted')
    if extracted is None or extracted.intent == 'other':
        return {'reply': {'kind': 'help', 'facts': {}}, 'route': 'compose_reply'}

    tz = state.get('user_timezone')
    prev = state.get('draft') or {}
    prev_local = prev.get('local') or {}
    fresh = state.get('status') in (None, 'idle')

    title = _first(extracted.title, prev.get('title'))
    event_type = _valid_event_type(_first(extracted.event_type, prev.get('event_type')))
    location = _first(extracted.location, prev.get('location'))
    duration = extracted.duration_minutes or prev.get('duration_minutes') or 60
    duration = max(15, min(480, int(duration)))
    local = {
        'start_date': _first(extracted.start_date, prev_local.get('start_date')),
        'end_date': _first(extracted.end_date, prev_local.get('end_date')),
        'start_time': _first(extracted.start_time, prev_local.get('start_time'), _DEFAULT_START_TIME),
        'end_time': _first(extracted.end_time, prev_local.get('end_time'), _DEFAULT_END_TIME),
    }
    mentions = [{'name': m.name, 'email': m.email} for m in (extracted.people or [])]

    base = {
        'title': title,
        'event_type': event_type,
        'location': location,
        'duration_minutes': duration,
        'local': local,
        'people': mentions,
    }

    def _stop(reply):
        out = {'draft': base, 'status': 'collecting', 'workflow': 'create_event',
               'reply': reply, 'route': 'compose_reply'}
        if fresh:
            out['participants'] = []
        return out

    missing = []
    if not title:
        missing.append('a title')
    if not local['start_date']:
        missing.append('a date or window')
    if missing:
        return _stop({'kind': 'need_info', 'facts': {'question': _need_info_question(missing)}})

    if not local['end_date']:
        local['end_date'] = local['start_date']
    try:
        start_d = date.fromisoformat(local['start_date'])
        end_d = date.fromisoformat(local['end_date'])
        start_t = _parse_time(local['start_time'])
        end_t = _parse_time(local['end_time'])
    except (ValueError, TypeError):
        return _stop({'kind': 'need_info',
                      'facts': {'question': 'When should this happen? A date and rough time works.'}})

    earliest, latest = dates.local_window_to_utc(start_d, end_d, start_t, end_t, tz)
    ref = state['reference_time_utc']
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    if latest <= ref:
        return _stop({'kind': 'invalid_window', 'facts': {}})

    draft = {
        'title': title,
        'event_type': event_type,
        'earliest_datetime_utc': earliest.isoformat(),
        'latest_datetime_utc': latest.isoformat(),
        'duration_minutes': duration,
        'location': location,
        'local': local,
        'people': mentions,
    }
    out = {'draft': draft, 'workflow': 'create_event', 'route': 'resolve_people'}
    if fresh:
        out['participants'] = []
    return out


# ─── resolve_people (deterministic + LLM pairing) ─────────────────────────────

def make_resolve_people(llm):
    """Factory: resolve draft mentions to participants (LLM used only for pairing).

    Reads the not-yet-processed mentions from ``draft['people']`` and appends
    cleanly-resolved participants to any already accumulated. The FIRST ambiguous
    / unknown bare name becomes ``pending_person`` → ``ask_email``; the mentions
    after it are stashed back into ``draft['people']`` for the next round. All
    resolved → ``prepare_choice``.
    """

    def resolve_people(state):
        draft = dict(state.get('draft') or {})
        mentions = list(draft.get('people') or [])
        existing = list(state.get('participants') or [])

        new_parts, pending = people.resolve_mentions(
            mentions,
            coordinator_id=state['user_id'],
            message=state.get('user_message') or '',
            llm=llm,
        )
        participants = _dedupe_participants(existing + new_parts)

        if pending:
            draft['people'] = _mentions_after(mentions, pending.get('name'))
            return {
                'draft': draft,
                'participants': participants,
                'pending_person': pending,
                'status': 'awaiting_email',
                'route': 'ask_email',
            }

        draft['people'] = []
        return {
            'draft': draft,
            'participants': participants,
            'pending_person': None,
            'route': 'prepare_choice',
        }

    return resolve_people


# ─── ask_email / apply_email (deterministic) ─────────────────────────────────

def ask_email(state):
    """Surface the pending person: pick-person buttons if ambiguous, else ask
    for their email. Terminal for the turn (status stays 'awaiting_email')."""
    pending = state.get('pending_person') or {}
    name = pending.get('name') or 'that person'
    buttons: list = []
    if pending.get('reason') == 'ambiguous':
        for opt in pending.get('options') or []:
            label = opt.get('full_name') or opt.get('email') or 'This one'
            buttons.append(_button(label, {
                'type': 'pick_person', 'person_name': name, 'user_id': opt.get('user_id'),
            }))
        facts = {'name': name, 'mode': 'ambiguous'}
    else:
        facts = {'name': name, 'mode': 'no_match'}
    return {
        'status': 'awaiting_email',
        'card': None,
        'buttons': buttons,
        'reply': {'kind': 'ask_email', 'facts': facts},
        'route': 'compose_reply',
    }


def apply_email(state):
    """Resolve the email/user_id the coordinator supplied for the pending person,
    append the participant, then loop back to ``resolve_people`` for the rest.

    Accepts a ``provide_email`` / ``pick_person`` action or an email regexed from
    free text. If nothing resolves, re-asks (stays 'awaiting_email')."""
    action = state.get('action') or {}
    atype = action.get('type')
    pending = state.get('pending_person') or {}
    name = pending.get('name')
    participants = list(state.get('participants') or [])

    resolved = None
    if atype == 'pick_person' and action.get('user_id'):
        resolved = people.resolve_provided_user_id(action['user_id'])
    elif atype == 'provide_email' and action.get('email'):
        resolved = people.resolve_provided_email(action['email'], name=name)
    else:
        email = _extract_email(state.get('user_message'))
        if email:
            resolved = people.resolve_provided_email(email, name=name)

    if resolved is None:
        return {
            'status': 'awaiting_email',
            'reply': {'kind': 'resolve_failed', 'facts': {'name': name or 'that person'}},
            'route': 'compose_reply',
        }

    participants = _dedupe_participants(participants + [resolved])
    return {'participants': participants, 'pending_person': None, 'route': 'resolve_people'}


# ─── prepare_choice (deterministic) ───────────────────────────────────────────

def prepare_choice(state):
    """Offer the booking choice only when every participant is in-system AND has a
    connected calendar; otherwise skip straight to the in-app confirmation."""
    participants = state.get('participants') or []
    draft = state.get('draft') or {}
    all_bookable = all(p.get('in_system') and p.get('has_calendar') for p in participants)

    if all_bookable:
        card = _dump(_draft_card(draft, participants))
        buttons = [
            _button('Book from calendars', {'type': 'book_direct'}),
            _button('Use When scheduling', {'type': 'use_in_app'}),
        ]
        facts = {'title': draft.get('title') or 'your event',
                 'window': _format_window(draft, state.get('user_timezone'))}
        return {
            'status': 'awaiting_choice',
            'card': card,
            'buttons': buttons,
            'reply': {'kind': 'choice', 'facts': facts},
            'route': 'compose_reply',
        }

    return {'booking_mode': 'in_app', 'route': 'prepare_confirmation'}


# ─── compute_slots (deterministic) ────────────────────────────────────────────

def compute_slots(state):
    """Freshen busy slots, then rank candidate times deterministically. No slots →
    stay at the choice and offer in-app; otherwise → direct confirmation."""
    draft = state.get('draft') or {}
    participants = state.get('participants') or []
    ref = state['reference_time_utc']

    user_ids = [state['user_id']]
    for p in participants:
        uid = p.get('user_id')
        if p.get('in_system') and uid and uid != state['user_id']:
            user_ids.append(uid)
    user_ids = list(dict.fromkeys(user_ids))

    earliest = draft.get('earliest_datetime_utc')
    latest = draft.get('latest_datetime_utc')
    duration = draft.get('duration_minutes') or 60

    try:
        availability.ensure_fresh_busy_slots(user_ids, earliest, latest, reference_time_utc=ref)
    except Exception:
        pass

    slots = availability.rank_candidate_slots(
        user_ids, earliest, latest, duration, reference_time_utc=ref, limit=3,
    )

    if not slots:
        return {
            'status': 'awaiting_choice',
            'candidate_slots': [],
            'card': None,
            'buttons': [_button('Use When scheduling', {'type': 'use_in_app'})],
            'reply': {'kind': 'no_slots', 'facts': {'title': draft.get('title') or 'your event'}},
            'route': 'compose_reply',
        }

    return {'candidate_slots': slots, 'booking_mode': 'direct', 'route': 'prepare_confirmation'}


# ─── prepare_confirmation (deterministic) ─────────────────────────────────────

def prepare_confirmation(state):
    """Build the confirmation card + Confirm/Cancel buttons for the active mode
    (edit / create-direct / create-in-app) and move to 'awaiting_confirmation'.

    The direct Confirm button carries no slot itself — the client attaches the
    radio-selected ``slot_index`` when the coordinator taps it."""
    tz = state.get('user_timezone')
    workflow = state.get('workflow')
    booking_mode = state.get('booking_mode')
    draft = state.get('draft') or {}

    if workflow == 'edit_event':
        display = draft.get('display_changes') or []
        card = _dump(DraftCard(
            mode='edit',
            title=draft.get('event_name') or 'Event',
            event_uid=draft.get('event_uid'),
            changes=[EditChange(field=c['field'], label=c['label'],
                                **{'from': c.get('from')}, to=c.get('to')) for c in display],
        ))
        reply = {'kind': 'confirm_edit',
                 'facts': {'event_name': draft.get('event_name') or 'the event',
                           'changes': [_change_str(c) for c in display]}}
    elif booking_mode == 'direct':
        slots = state.get('candidate_slots') or []
        card = _dump(_draft_card(draft, state.get('participants'), mode='create_direct', slots=slots))
        reply = {'kind': 'confirm_create_direct',
                 'facts': {'title': draft.get('title') or 'your event',
                           'slots': [_format_slot(s, tz) for s in slots]}}
    else:
        booking_mode = 'in_app'
        card = _dump(_draft_card(draft, state.get('participants'), mode='create_in_app'))
        reply = {'kind': 'confirm_create_in_app',
                 'facts': {'title': draft.get('title') or 'your event',
                           'window': _format_window(draft, tz),
                           'participant_count': len(state.get('participants') or [])}}

    out = {
        'status': 'awaiting_confirmation',
        'card': card,
        'buttons': [
            _button('Confirm', {'type': 'confirm_draft'}),
            _button('Cancel', {'type': 'cancel'}),
        ],
        'reply': reply,
        'route': 'compose_reply',
    }
    if booking_mode:
        out['booking_mode'] = booking_mode
    return out


def _change_str(c: dict) -> str:
    return f"{c.get('label')}: {c.get('from') or '—'} to {c.get('to')}"


# ─── book_direct_node / create_in_app_node (deterministic write paths) ────────

def book_direct_node(state):
    """Validate the client-chosen slot against persisted candidates, apply any
    confirm-time edits, then finalize via ``booking.book_direct``.

    Success → idle + result. Finalize failure keeps 'awaiting_confirmation' with
    an error (the planning event survives for UI recovery). Create failure →
    error."""
    action = state.get('action') or {}
    slots = state.get('candidate_slots') or []
    idx = action.get('slot_index')
    idx = 0 if idx is None else int(idx)
    if not slots or idx < 0 or idx >= len(slots):
        return {
            'status': 'awaiting_confirmation',
            'error_code': 'invalid_slot',
            'reply': {'kind': 'error',
                      'facts': {'message': "That time isn't available anymore — pick one of the offered times."}},
            'route': 'compose_reply',
        }

    slot = slots[idx]
    draft = _apply_edits(dict(state.get('draft') or {}), action.get('edits'))
    user = _user_from_state(state)
    result = booking.book_direct(user, draft, state.get('participants') or [], slot, state['reference_time_utc'])
    uid = result.get('event_uid')
    err = result.get('error_code')

    if err and uid:
        return {
            'status': 'awaiting_confirmation',
            'error_code': err,
            'result_event_uid': uid,
            'reply': {'kind': 'error',
                      'facts': {'message': "I created the event but couldn't finalize the calendar invites — you can finish it from the event page.",
                                'event_uid': uid}},
            'route': 'compose_reply',
        }
    if err:
        return {
            'status': 'awaiting_confirmation',
            'error_code': err,
            'reply': {'kind': 'error', 'facts': {'message': 'Something went wrong creating the event. Want to try again?'}},
            'route': 'compose_reply',
        }

    out = _clear_workflow_state()
    out.update({
        'result_event_uid': uid,
        'reply': {'kind': 'booked',
                  'facts': {'title': draft.get('title') or 'your event',
                            'slot': _format_slot(slot, state.get('user_timezone'))}},
        'route': 'compose_reply',
    })
    return out


def create_in_app_node(state):
    """Create the planning event + invite participants via ``booking``. Success →
    idle + result; create failure → error."""
    draft = _apply_edits(dict(state.get('draft') or {}), (state.get('action') or {}).get('edits'))
    user = _user_from_state(state)
    result = booking.create_in_app_event(user, draft, state.get('participants') or [])
    uid = result.get('event_uid')
    err = result.get('error_code')

    if err:
        return {
            'status': 'awaiting_confirmation',
            'error_code': err,
            'reply': {'kind': 'error', 'facts': {'message': 'Something went wrong creating the event. Want to try again?'}},
            'route': 'compose_reply',
        }

    out = _clear_workflow_state()
    out.update({
        'result_event_uid': uid,
        'reply': {'kind': 'created_in_app', 'facts': {'title': draft.get('title') or 'your event'}},
        'route': 'compose_reply',
    })
    return out


# ─── cancel_node (deterministic) ──────────────────────────────────────────────

def cancel_node(state):
    """Clear all workflow state and return to idle."""
    out = _clear_workflow_state()
    out.update({'reply': {'kind': 'cancelled', 'facts': {}}, 'route': 'compose_reply'})
    return out


# ─── compose_reply (LLM, terminal for every branch) ───────────────────────────

def make_compose_reply(llm):
    """Factory: the single terminal reply node.

    Builds a deterministic ``baseline`` from the structured ``reply`` facts, then
    asks the LLM to improve only the WORDING (retried once). Any failure/empty
    output falls back to ``baseline`` verbatim — ``assistant_text`` is therefore
    always present and correct even during an LLM outage."""

    def compose_reply(state):
        reply = state.get('reply') or {'kind': 'help', 'facts': {}}
        baseline = _fallback_text(reply)
        prompt = llm_mod.build_reply_prompt(reply, baseline)
        text = None
        for _ in range(2):
            try:
                resp = llm.invoke(prompt)
                content = getattr(resp, 'content', None)
                if content and str(content).strip():
                    text = str(content).strip()
                    break
            except Exception:
                logger.exception("chat agent reply LLM call failed")
                continue
        return {'assistant_text': text or baseline}

    return compose_reply


def _fallback_text(reply: dict) -> str:
    """Deterministic reply template per outcome (LLM-outage fallback)."""
    kind = reply.get('kind', 'help')
    f = reply.get('facts') or {}

    if kind == 'help':
        return ("I can help you schedule an event — tell me what to plan, who's "
                "involved, and a rough time window.")
    if kind == 'need_info':
        return f.get('question') or "Tell me a bit more and I'll set it up."
    if kind == 'invalid_window':
        return "That time window is entirely in the past — give me a future window and I'll find times."
    if kind == 'ask_email':
        name = f.get('name', 'that person')
        if f.get('mode') == 'ambiguous':
            return f"There are a few people named {name}. Which one did you mean?"
        return f"I couldn't find {name} in your contacts. What's their email address?"
    if kind == 'resolve_failed':
        return f"I couldn't resolve {f.get('name', 'that person')}. Please share their email address."
    if kind == 'choice':
        return (f"{f.get('title', 'Your event')} is ready. Want me to book the best time from "
                "everyone's calendars, or set it up in When for people to weigh in?")
    if kind == 'no_slots':
        return (f"I couldn't find a time where everyone's free for {f.get('title', 'your event')}. "
                "Want to set it up in When so people can pick?")
    if kind == 'confirm_create_direct':
        slots = f.get('slots') or []
        listed = "; ".join(slots) if slots else "the times below"
        return f"Best times for {f.get('title', 'your event')}: {listed}. Pick one and confirm."
    if kind == 'confirm_create_in_app':
        return f"I'll set up {f.get('title', 'your event')} in When and invite everyone. Confirm to create it."
    if kind == 'confirm_edit':
        changes = f.get('changes') or []
        listed = "; ".join(changes) if changes else "the changes below"
        return f"Here's what I'll change for {f.get('event_name', 'the event')}: {listed}. Confirm to apply."
    if kind == 'booked':
        return f"Booked {f.get('title', 'your event')} for {f.get('slot', 'the chosen time')}."
    if kind == 'created_in_app':
        return f"Created {f.get('title', 'your event')} in When and invited everyone."
    if kind == 'edited':
        return f"Updated {f.get('event_name', 'the event')}."
    if kind == 'cancelled':
        return "Okay, I've cancelled that."
    if kind == 'edit_no_context':
        return "Open the event you want to edit, then tell me what to change."
    if kind == 'edit_not_planning':
        return f"{f.get('event_name', 'That event')} is already confirmed, so it can't be edited here yet."
    if kind == 'edit_not_coordinator':
        return f"Only the coordinator can edit {f.get('event_name', 'that event')}."
    if kind == 'edit_need_change':
        return f"What would you like to change about {f.get('event_name', 'that event')}?"
    if kind == 'error':
        return f.get('message') or "Something went wrong. Please try again."
    if kind == 'apology':
        return "Sorry, I had trouble understanding that. Could you rephrase?"
    return "Okay."
