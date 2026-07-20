"""Edit-workflow nodes (Package 5).

Two deterministic nodes:

* ``validate_edit`` — gates an edit (must have a focused/pinned event that is a
  planning event the user coordinates), then builds a before/after ``changes``
  set from the extracted edit_* fields and hands off to ``prepare_confirmation``.
  The target event is PINNED at classification time (its summary is stored on the
  draft); later navigation does not rebind it.
* ``apply_edit_node`` — applies the confirmed change set via
  ``event_service.update_event`` (coordinator re-checked by the service; a window
  change auto-flags ``proposals_needs_regeneration`` there).

No LLM here — the extracted fields arrive in ``state['extracted']``.
"""

from datetime import date, datetime

from fastapi import HTTPException

from app.models.chat import EditChange
from app.models.event import EventUpdate
from app.services import event_service
from agent_service.nodes import _fmt, _parse_time, _user_from_state
from app.utils import dates


def _local_parts(iso: str, tz_name) -> tuple[str, str]:
    """Local (date, time) strings for a UTC ISO instant (conversion via dates)."""
    dt = datetime.fromisoformat(iso)
    return (
        dates.format_utc_in_tz(dt, tz_name, '%Y-%m-%d'),
        dates.format_utc_in_tz(dt, tz_name, '%H:%M'),
    )


def _add_change(changes: dict, display: list, field: str, label: str,
                from_raw, to_raw, from_disp, to_disp) -> None:
    changes[field] = {'from': from_raw, 'to': to_raw}
    display.append(_dump_change(field, label, from_disp, to_disp))


def _dump_change(field: str, label: str, from_disp, to_disp) -> dict:
    model = EditChange(field=field, label=label, **{'from': from_disp}, to=to_disp)
    return model.model_dump(mode='json', by_alias=True, exclude_none=True)


def _build_edit_changes(summary: dict, extracted, tz_name) -> tuple[dict, list]:
    """Turn extracted edit_* fields into (raw change map, display change list).

    ``changes`` holds the raw values fed to ``EventUpdate`` (window fields as UTC
    ISO strings); ``display`` holds the human before/after rows for the card. The
    ``summary`` (page context or pinned) supplies the "before" values; description/
    location/video-link have no "before" in the summary, so they render as "—".
    """
    changes: dict = {}
    display: list = []

    if extracted.edit_name:
        _add_change(changes, display, 'name', 'Name',
                    summary.get('name'), extracted.edit_name,
                    summary.get('name'), extracted.edit_name)
    if extracted.edit_description:
        _add_change(changes, display, 'description', 'Description',
                    None, extracted.edit_description, None, extracted.edit_description)
    if extracted.edit_location:
        _add_change(changes, display, 'location', 'Location',
                    None, extracted.edit_location, None, extracted.edit_location)
    if extracted.edit_video_call_link:
        _add_change(changes, display, 'video_call_link', 'Video link',
                    None, extracted.edit_video_call_link, None, extracted.edit_video_call_link)
    if extracted.edit_duration_minutes:
        new_d = max(15, min(480, int(extracted.edit_duration_minutes)))
        old_d = summary.get('duration_minutes')
        _add_change(changes, display, 'duration_minutes', 'Duration',
                    old_d, new_d, f"{old_d} min", f"{new_d} min")

    # Window: convert against the event's existing local dates when only a time
    # (or only a date) is provided.
    start_changed = bool(extracted.edit_start_date or extracted.edit_start_time)
    end_changed = bool(extracted.edit_end_date or extracted.edit_end_time)
    if start_changed or end_changed:
        old_e_iso = summary.get('earliest_datetime_utc')
        old_l_iso = summary.get('latest_datetime_utc')
        e_date, e_time = _local_parts(old_e_iso, tz_name)
        l_date, l_time = _local_parts(old_l_iso, tz_name)

        new_s_date = extracted.edit_start_date or e_date
        new_s_time = extracted.edit_start_time or e_time
        new_e_date = extracted.edit_end_date or l_date
        new_e_time = extracted.edit_end_time or l_time

        new_earliest, new_latest = dates.local_window_to_utc(
            date.fromisoformat(new_s_date), date.fromisoformat(new_e_date),
            _parse_time(new_s_time), _parse_time(new_e_time), tz_name,
        )
        if start_changed:
            _add_change(changes, display, 'earliest_datetime_utc', 'Start',
                        old_e_iso, new_earliest.isoformat(),
                        _fmt(old_e_iso, tz_name, '%a %b %d %H:%M'),
                        _fmt(new_earliest, tz_name, '%a %b %d %H:%M'))
        if end_changed:
            _add_change(changes, display, 'latest_datetime_utc', 'End',
                        old_l_iso, new_latest.isoformat(),
                        _fmt(old_l_iso, tz_name, '%a %b %d %H:%M'),
                        _fmt(new_latest, tz_name, '%a %b %d %H:%M'))

    return changes, display


def validate_edit(state):
    """Gate + build the edit draft, or reply with the reason it can't proceed."""
    tz = state.get('user_timezone')
    extracted = state.get('extracted')
    draft = dict(state.get('draft') or {})

    # Pinned event wins over page context (navigation doesn't rebind).
    pinned = (
        state.get('workflow') == 'edit_event'
        and draft.get('event_uid')
        and draft.get('event_summary')
    )
    if pinned:
        summary = draft['event_summary']
    elif state.get('page_context'):
        summary = state['page_context']
    else:
        return {'reply': {'kind': 'edit_no_context', 'facts': {}}, 'route': 'compose_reply'}

    event_name = summary.get('name') or 'the event'

    if summary.get('status') != 'planning':
        return {'reply': {'kind': 'edit_not_planning', 'facts': {'event_name': event_name}},
                'route': 'compose_reply'}
    if not summary.get('is_coordinator'):
        return {'reply': {'kind': 'edit_not_coordinator', 'facts': {'event_name': event_name}},
                'route': 'compose_reply'}

    changes, display = _build_edit_changes(summary, extracted, tz)

    pinned_draft = {
        'event_uid': summary.get('uid'),
        'event_name': event_name,
        'event_summary': summary,
        'changes': changes,
        'display_changes': display,
    }

    if not changes:
        # Pin the event and ask what to change; the uid survives navigation.
        return {
            'draft': pinned_draft,
            'workflow': 'edit_event',
            'status': 'collecting',
            'reply': {'kind': 'edit_need_change', 'facts': {'event_name': event_name}},
            'route': 'compose_reply',
        }

    return {'draft': pinned_draft, 'workflow': 'edit_event', 'route': 'prepare_confirmation'}


def apply_edit_node(state):
    """Apply the confirmed change set via ``event_service.update_event``.

    Success → idle + ``result_event_uid``. 403 (not coordinator) / 404 (missing)
    surface as an error the reply explains."""
    draft = state.get('draft') or {}
    changes = draft.get('changes') or {}
    to_values = {field: ch['to'] for field, ch in changes.items()}
    user = _user_from_state(state)

    try:
        event_service.update_event(draft['event_uid'], EventUpdate(**to_values), user)
    except HTTPException as exc:
        if exc.status_code == 403:
            code, message = 'edit_forbidden', "Only the coordinator can edit this event."
        elif exc.status_code == 404:
            code, message = 'event_not_found', "I couldn't find that event anymore."
        else:
            code, message = 'edit_failed', "Something went wrong updating the event. Want to try again?"
        return {
            'status': 'awaiting_confirmation',
            'error_code': code,
            'reply': {'kind': 'error', 'facts': {'message': message}},
            'route': 'compose_reply',
        }

    from agent_service.nodes import _clear_workflow_state

    out = _clear_workflow_state()
    out.update({
        'result_event_uid': draft['event_uid'],
        'reply': {'kind': 'edited', 'facts': {'event_name': draft.get('event_name') or 'the event'}},
        'route': 'compose_reply',
    })
    return out
