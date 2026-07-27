"""Create-workflow + shared graph nodes (Package 5).

Every node is a pure function of ``AgentState`` returning a sparse partial
update. Only ``classify_and_extract`` touches the injected ``llm`` (via a node
factory that closes over it); everything else is deterministic Python —
including ``resolve_people`` and ``compose_reply``, which renders a
fact-complete template per outcome. Nodes set an internal ``route`` key naming
the next node so the graph's conditional edges are trivial ``state['route']``
lookups — routing is 100% deterministic and never LLM-driven.

The LLM is confined to a SINGLE call: intent classification + field extraction
(``classify_and_extract``), which also attributes emails to the people it lists
so no separate name↔email pairing round-trip is needed. It never words replies,
never selects a slot, and never decides control flow.
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
from agent_service import availability, booking, people, tracing
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


# The workflow channels persisted on the chat_threads row between turns. BOTH resets
# below derive their key list from this ONE definition so they cannot drift apart as
# channels are added — two hand-maintained lists is how `pending_people` came to be
# unhandled in `validate_intent`.
_WORKFLOW_CHANNELS = ('draft', 'participants', 'pending_people', 'candidate_slots',
                      'booking_mode')

# Everything derived from WHO is invited. `draft` is excluded: a scope reset rebuilds
# the draft in place, and its fact fields survive unless the scope is 'new_event'.
_PEOPLE_CHANNELS = tuple(c for c in _WORKFLOW_CHANNELS if c != 'draft')


def _clear_workflow_state() -> dict:
    """Reset all workflow channels to idle (used after success / cancel)."""
    out: dict = {channel: None for channel in _WORKFLOW_CHANNELS}
    out.update({'status': 'idle', 'workflow': None, 'card': None, 'buttons': []})
    return out


def _people_reset() -> dict:
    """Clear every channel derived from WHO is invited (``validate_intent`` scope reset).

    Unlike ``_clear_workflow_state``, which ends the workflow, the turn CONTINUES into
    ``resolve_people`` — so the list channels reset to ``[]`` rather than ``None``.
    ``candidate_slots`` and ``booking_mode`` are included because both are derived from
    the old roster: a ranking computed for people who are no longer invited is worse
    than no ranking at all.
    """
    return {c: (None if c == 'booking_mode' else []) for c in _PEOPLE_CHANNELS}


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


def _mention_key(mention: dict) -> str | None:
    """Identity for a mention: its casefolded name, else its normalized email."""
    name = (mention.get('name') or '').strip().casefold()
    if name:
        return name
    return (mention.get('email') or '').strip().casefold() or None


def _merge_mentions(prev: list, new: list) -> list:
    """Carry unconsumed prior mentions forward, appending this turn's new ones.

    The extraction prompt tells the model to list only people mentioned in THIS
    message ("the app already kept those"), so a follow-up turn returns no people at
    all — the prior mentions have to survive here or the names are lost. Safe because
    ``resolve_people`` empties ``draft['people']`` the moment it consumes them, so
    anything still in there is genuinely unresolved.

    Carried-forward entries come FIRST: mention order drives pending order, which
    drives ask order, which drives the positional pairing in
    ``_pair_emails_to_pending``. Prepending new mentions would silently scramble
    bulk-reply pairing.

    Deduped on ``_mention_key`` so a repeated name cannot eat the ``MAX_CHAT_PEOPLE``
    budget twice; on a collision the entry carrying an email wins, so a later "gil is
    gil@x.com" upgrades the bare name in place instead of duplicating it.
    """
    merged: list = []
    index: dict = {}
    for mention in list(prev) + list(new):
        key = _mention_key(mention)
        if key is None:
            continue
        if key not in index:
            index[key] = len(merged)
            merged.append(dict(mention))
            continue
        existing = merged[index[key]]
        for field in ('email', 'name'):
            if not existing.get(field) and mention.get(field):
                existing[field] = mention[field]
    return merged


def _join_names(names: list) -> str:
    """Human list join: 'Sarah', 'Sarah and John', 'Sarah, John, and Mike'."""
    names = [str(n) for n in names if n]
    if not names:
        return 'them'
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _all_emails(text) -> list[str]:
    """Every distinct email in free text, in first-seen order (bulk reply split)."""
    if not text:
        return []
    return list(dict.fromkeys(_EMAIL_RE.findall(text)))


def _pop_pending(pending: list, name) -> list:
    """Return ``pending`` without the first entry whose name matches (casefolded)."""
    if not name:
        return pending
    target = str(name).strip().casefold()
    out, dropped = [], False
    for entry in pending:
        if not dropped and (str(entry.get('name') or '')).strip().casefold() == target:
            dropped = True
            continue
        out.append(entry)
    return out


def _pair_emails_to_pending(emails: list[str], pending: list) -> tuple[list, list, list]:
    """Pair bulk-reply emails to the pending people awaiting an email.

    Returns ``(pairs, leftover_emails, remaining_pending)`` where ``pairs`` is a
    list of ``(pending_entry, email)``. A name-token hint wins first (an email
    whose local part contains a name token — ``sarah@…`` → "Sarah"); the rest are
    assigned positionally to the still-unmatched ``no_match`` people in order (the
    same order they were asked for). Ambiguous people are only matched by hint —
    otherwise they keep their pick-person path. Extra emails (more than names)
    fall through as ``leftover`` and are added as plain non-user invitees.
    """
    remaining = list(pending)
    pairs: list = []
    used: set = set()

    # Pass 1 — name-token hint against any pending person.
    for email in emails:
        local = email.split('@', 1)[0].casefold()
        for entry in remaining:
            tokens = [t for t in re.split(r'[^a-z0-9]+', (entry.get('name') or '').casefold()) if len(t) >= 2]
            if tokens and any(tok in local for tok in tokens):
                pairs.append((entry, email))
                remaining.remove(entry)
                used.add(email)
                break

    # Pass 2 — positional over the still-unmatched no_match people, in ask order.
    leftover = [e for e in emails if e not in used]
    no_match = [e for e in remaining if e.get('reason') != 'ambiguous']
    for entry, email in zip(no_match, leftover):
        pairs.append((entry, email))
        remaining.remove(entry)
        used.add(email)

    leftover = [e for e in emails if e not in used]
    return pairs, leftover, remaining


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
            history=state.get('history'),
        )
        extracted = None
        for _ in range(2):
            try:
                with tracing.span('llm.extract'):
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
    all-past windows, and hands off to ``resolve_people``.

    The extracted ``scope`` decides how much of the prior turn survives: a
    'revision' merges onto it (including unconsumed people mentions),
    'replaces_people' restarts the guest list but keeps the event facts, and
    'new_event' rebuilds from this turn alone. A brand-new thread (status
    idle/None) is treated exactly like 'new_event'.
    """
    extracted = state.get('extracted')
    if extracted is None or extracted.intent == 'other':
        return {'reply': {'kind': 'help', 'facts': {}}, 'route': 'compose_reply'}

    tz = state.get('user_timezone')
    fresh = state.get('status') in (None, 'idle')
    # Default to 'revision' on anything unexpected: the destructive scopes must be
    # actively chosen, so a missing or garbled value keeps state rather than wiping it.
    scope = getattr(extracted, 'scope', None) or 'revision'
    resets_facts = fresh or scope == 'new_event'
    resets_people = resets_facts or scope == 'replaces_people'

    # With prev empty, every _first() below collapses to "take the extracted value",
    # so 'new_event' needs no special handling of the individual fact fields.
    prev = {} if resets_facts else (state.get('draft') or {})
    prev_local = prev.get('local') or {}

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
    new_mentions = [{'name': m.name, 'email': m.email} for m in (extracted.people or [])]
    # Unconsumed mentions must survive a follow-up turn — the model is instructed not
    # to repeat people it already reported, so this merge is the only thing keeping
    # them alive when the user answers a question instead of restating the guest list.
    mentions = new_mentions if resets_people else _merge_mentions(
        prev.get('people') or [], new_mentions)

    base = {
        'title': title,
        'event_type': event_type,
        'location': location,
        'duration_minutes': duration,
        'local': local,
        'people': mentions,
    }

    # Announced by compose_reply so a discarded guest list is never silent.
    reset_note = {'scope_reset': scope} if (resets_people and not fresh) else {}

    def _stop(reply):
        out = {'draft': base, 'status': 'collecting', 'workflow': 'create_event',
               'reply': reply, 'route': 'compose_reply'}
        if resets_people:
            out.update(_people_reset())
        out.update(reset_note)
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
    if resets_people:
        out.update(_people_reset())
    out.update(reset_note)
    return out


# ─── resolve_people (deterministic + LLM pairing) ─────────────────────────────

def resolve_people(state):
    """Resolve draft mentions to participants (fully deterministic — no LLM).

    Processes ALL mentions in ``draft['people']`` in one pass, appending
    cleanly-resolved participants to any already accumulated. Every ambiguous /
    unknown bare name is collected into ``pending_people`` → ``ask_email`` (a
    single bulk prompt for all of them); the mentions are fully consumed, so the
    awaiting-email loop is driven by ``pending_people``, not by re-reading
    mentions. All resolved → ``prepare_choice``. Name↔email pairing already
    happened in the extraction call, so mentions arrive with emails attached where
    they belong.
    """
    draft = dict(state.get('draft') or {})
    mentions = list(draft.get('people') or [])
    existing = list(state.get('participants') or [])

    new_parts, pending = people.resolve_mentions(
        mentions,
        coordinator_id=state['user_id'],
    )
    participants = _dedupe_participants(existing + new_parts)
    draft['people'] = []  # every mention consumed this pass

    if pending:
        return {
            'draft': draft,
            'participants': participants,
            'pending_people': pending,
            'status': 'awaiting_email',
            'route': 'ask_email',
        }

    return {
        'draft': draft,
        'participants': participants,
        'pending_people': [],
        'route': 'prepare_choice',
    }


# ─── ask_email / apply_email (deterministic) ─────────────────────────────────

def ask_email(state):
    """Surface every pending person in ONE bulk prompt: pick-person buttons for
    each ambiguous name, plus a single text ask listing the names we need emails
    for. Terminal for the turn (status stays 'awaiting_email')."""
    pending = state.get('pending_people') or []
    ambiguous = [p for p in pending if p.get('reason') == 'ambiguous']
    no_match = [p for p in pending if p.get('reason') != 'ambiguous']

    buttons: list = []
    for entry in ambiguous:
        name = entry.get('name') or 'that person'
        for opt in entry.get('options') or []:
            label = opt.get('full_name') or opt.get('email') or 'This one'
            buttons.append(_button(label, {
                'type': 'pick_person', 'person_name': name, 'user_id': opt.get('user_id'),
            }))

    facts = {
        'no_match_names': [p.get('name') or 'that person' for p in no_match],
        'ambiguous_names': [p.get('name') or 'that person' for p in ambiguous],
    }
    return {
        'status': 'awaiting_email',
        'card': None,
        'buttons': buttons,
        'reply': {'kind': 'ask_email', 'facts': facts},
        'route': 'compose_reply',
    }


def apply_email(state):
    """Resolve as many pending people as one reply supplies, then continue.

    Handles three inputs against ``pending_people``: a ``pick_person`` tap (one
    ambiguous name), a ``provide_email`` action, or a free-text reply carrying one
    OR MANY emails — split and paired to the pending names (``_pair_emails_to_pending``).
    Resolved people are removed from ``pending_people``; if any remain we loop back
    to ``ask_email`` for the rest, else we advance to ``prepare_choice``. If a reply
    resolves nobody, we re-ask (stays 'awaiting_email')."""
    action = state.get('action') or {}
    atype = action.get('type')
    pending = list(state.get('pending_people') or [])
    participants = list(state.get('participants') or [])
    resolved: list = []

    if atype == 'pick_person' and action.get('user_id'):
        picked = people.resolve_provided_user_id(action['user_id'])
        if picked:
            resolved.append(picked)
            pending = _pop_pending(pending, action.get('person_name'))
    elif atype == 'provide_email' and action.get('email'):
        name = action.get('person_name')
        resolved.append(people.resolve_provided_email(action['email'], name=name))
        # Named → drop that entry; unnamed → the first person still needing an email.
        pending = _pop_pending(pending, name) if name else _pop_pending(
            pending, next((p.get('name') for p in pending if p.get('reason') != 'ambiguous'), None))
    else:
        emails = _all_emails(state.get('user_message'))
        pairs, leftover, pending = _pair_emails_to_pending(emails, pending)
        for entry, email in pairs:
            resolved.append(people.resolve_provided_email(email, name=entry.get('name')))
        for email in leftover:  # extra emails beyond the names we asked for
            resolved.append(people.resolve_provided_email(email, name=None))

    participants = _dedupe_participants(participants + resolved)

    if not resolved:
        names = [p.get('name') for p in pending if p.get('reason') != 'ambiguous']
        return {
            'status': 'awaiting_email',
            'reply': {'kind': 'resolve_failed', 'facts': {'name': _join_names(names)}},
            'route': 'compose_reply',
        }

    if pending:
        # Still missing some — re-ask for whoever is left.
        return {
            'participants': participants,
            'pending_people': pending,
            'status': 'awaiting_email',
            'route': 'ask_email',
        }

    return {'participants': participants, 'pending_people': [], 'route': 'prepare_choice'}


# ─── prepare_choice (deterministic) ───────────────────────────────────────────

def prepare_choice(state):
    """Offer the booking choice only when there IS a roster and every participant is
    in-system AND has a connected calendar; otherwise skip straight to the in-app
    confirmation."""
    participants = state.get('participants') or []
    draft = state.get('draft') or {}

    # An empty roster is a solo event: there are no other calendars to reconcile, so
    # the two-way choice is meaningless. Checked EXPLICITLY because all([]) is True —
    # left to the `all()` below, no participants would take the most confident path
    # of all and offer to book a meeting for nobody.
    if not participants:
        return {'booking_mode': 'in_app', 'route': 'prepare_confirmation'}

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

    # Traced separately: the sync is a blocking call out to the calendar
    # providers, the ranking is pure local computation — when a turn is slow it
    # matters which of the two actually spent the time.
    try:
        with tracing.span('busy_sync'):
            availability.ensure_fresh_busy_slots(user_ids, earliest, latest, reference_time_utc=ref)
    except Exception:
        logger.exception("chat agent busy-slot freshness sync failed; ranking on existing data")

    with tracing.span('rank_slots'):
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
        'result_created': True,
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
        'result_created': True,
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


# ─── compose_reply (deterministic, terminal for every branch) ─────────────────

# Lead sentence announcing a scope reset. Read here rather than threaded through each
# branch's reply facts, so every downstream outcome (ask_email, choice, need_info…)
# announces the discard without any of them having to know about it.
_RESET_LEADS = {
    'replaces_people': "Starting the guest list over.",
    'new_event': "Starting a new event.",
}


def compose_reply(state):
    """The single terminal reply node: render the deterministic template for the
    structured ``reply`` facts. No LLM — every outcome has a fact-complete
    template in ``_reply_text``, so replies are instant and never drift.

    A turn whose scope discarded state leads with a sentence saying so: silently
    dropping a guest list the coordinator spent turns resolving is the exact failure
    this workflow is meant to avoid."""
    reply = state.get('reply') or {'kind': 'help', 'facts': {}}
    text = _reply_text(reply)
    lead = _RESET_LEADS.get(state.get('scope_reset') or '')
    return {'assistant_text': f"{lead} {text}" if lead else text}


def _reply_text(reply: dict) -> str:
    """Deterministic reply template per outcome."""
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
        no_match = f.get('no_match_names') or []
        ambiguous = f.get('ambiguous_names') or []
        parts: list[str] = []
        if no_match:
            verb = 'their emails' if len(no_match) > 1 else 'their email'
            hint = ' You can send them all in one message.' if len(no_match) > 1 else ''
            parts.append(f"I couldn't find {_join_names(no_match)} in your contacts — "
                         f"what's {verb}?{hint}")
        if ambiguous:
            lead = 'Also, a' if no_match else 'A'
            parts.append(f"{lead} few people match {_join_names(ambiguous)} — "
                         "tap the right one below.")
        return ' '.join(parts) or "Who did you mean?"
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
