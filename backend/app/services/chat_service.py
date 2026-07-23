"""Chat plumbing service (Package 2).

All chat-table access goes through the authenticated user client so RLS
(`user_id = auth.uid()`) scopes every read/write to the owner — a foreign or
missing thread is simply invisible and surfaces as a 404. The LangGraph graph
is stateless: every turn rehydrates workflow state from the thread row, advances
it, and writes the new state back.
"""

from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.models.chat import (
    ChatActionPayload,
    ChatMessageResponse,
    ChatPageContext,
    ChatThreadResponse,
    ChatTurnRequest,
    ChatTurnResponse,
)
from app.models.user import User
from app.services import event_service
from agent_service import graph, tracing
from app.utils.supabase import get_authed_client

_TITLE_MAX = 60


# ─── Row → response mappers ──────────────────────────────────────────────────

def _row_to_thread_response(row: dict) -> ChatThreadResponse:
    return ChatThreadResponse(
        id=row['id'],
        title=row.get('title'),
        status=row['status'],
        workflow=row.get('workflow'),
        last_event_uid=row.get('last_event_uid'),
        created_at=row['created_at'],
        updated_at=row['updated_at'],
    )


def _row_to_message_response(row: dict) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=row['id'],
        thread_id=row['thread_id'],
        role=row['role'],
        content=row['content'],
        payload=row.get('payload'),
        created_at=row['created_at'],
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _action_label(action: ChatActionPayload) -> str:
    """Deterministic user-message label for an action turn (the button text)."""
    if action.type == 'confirm_draft':
        return 'Confirm'
    if action.type == 'cancel':
        return 'Cancel'
    if action.type == 'book_direct':
        return 'Book from calendars'
    if action.type == 'use_in_app':
        return 'Use When scheduling'
    if action.type == 'provide_email':
        return action.email or ''
    if action.type == 'pick_person':
        return action.person_name or action.user_id or ''
    return action.type


def _truncate_title(text: str) -> str:
    text = (text or '').strip()
    return text[:_TITLE_MAX]


def _verify_page_context(context: ChatPageContext | None, current_user: User) -> dict | None:
    """Return a compact, access-verified event summary, or None.

    The client-supplied context is never trusted: access is re-checked via the
    authed event service. A 403/404 (no access) silently drops the context.
    """
    if context is None or not context.event_uid:
        return None
    try:
        event = event_service.get_event_by_uid(context.event_uid, current_user)
    except HTTPException:
        return None
    return {
        'uid': event.uid,
        'name': event.name,
        'status': event.status,
        'earliest_datetime_utc': event.earliest_datetime_utc.isoformat(),
        'latest_datetime_utc': event.latest_datetime_utc.isoformat(),
        'duration_minutes': event.duration_minutes,
        'is_coordinator': event.coordinator_id == current_user.id,
    }


# ─── Thread CRUD ─────────────────────────────────────────────────────────────

def create_thread(current_user: User) -> ChatThreadResponse:
    db = get_authed_client(current_user.token)
    result = (
        db.table('chat_threads')
        .insert({'user_id': current_user.id, 'status': 'idle'})
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail='Failed to create thread')
    return _row_to_thread_response(result.data[0])


def list_threads(current_user: User) -> list[ChatThreadResponse]:
    db = get_authed_client(current_user.token)
    result = (
        db.table('chat_threads')
        .select('*')
        .order('updated_at', desc=True)
        .execute()
    )
    return [_row_to_thread_response(row) for row in (result.data or [])]


def get_thread_messages(thread_id: str, current_user: User) -> list[ChatMessageResponse]:
    db = get_authed_client(current_user.token)
    result = (
        db.table('chat_messages')
        .select('*')
        .eq('thread_id', thread_id)
        .order('created_at')
        .execute()
    )
    return [_row_to_message_response(row) for row in (result.data or [])]


def delete_thread(thread_id: str, current_user: User) -> None:
    db = get_authed_client(current_user.token)
    result = (
        db.table('chat_threads')
        .select('id')
        .eq('id', thread_id)
        .maybe_single()
        .execute()
    )
    if result is None or not result.data:
        raise HTTPException(status_code=404, detail='Thread not found')
    # chat_messages rows cascade via the FK ON DELETE CASCADE.
    db.table('chat_threads').delete().eq('id', thread_id).execute()


# ─── One agent turn ──────────────────────────────────────────────────────────

def run_turn(
    thread_id: str,
    request: ChatTurnRequest,
    reference_time_utc: datetime,
    current_user: User,
) -> ChatTurnResponse:
    """Run one agent turn, wrapped in a latency trace.

    The trace is diagnostic only — it wraps the whole turn (thread read, graph
    invocation, message + state writes) so a slow turn reports which phase spent
    the time, and emits one structured line on the way out even if the turn
    raises. See ``agent_service/tracing.py``.
    """
    with tracing.turn_trace(thread=thread_id, user=current_user.id):
        return _run_turn(thread_id, request, reference_time_utc, current_user)


def _run_turn(
    thread_id: str,
    request: ChatTurnRequest,
    reference_time_utc: datetime,
    current_user: User,
) -> ChatTurnResponse:
    if not (settings.gemini_api_key or '').strip():
        raise HTTPException(status_code=503, detail='chat_disabled')

    db = get_authed_client(current_user.token)

    # Fetch the thread — RLS hides foreign threads, so a missing row is a 404.
    with tracing.span('db.fetch_thread'):
        thread_result = (
            db.table('chat_threads')
            .select('*')
            .eq('id', thread_id)
            .maybe_single()
            .execute()
        )
    if thread_result is None or not thread_result.data:
        raise HTTPException(status_code=404, detail='Thread not found')
    thread_row = thread_result.data

    # Re-verify the client-supplied page context (dropped silently on no access).
    with tracing.span('db.verify_page_context'):
        page_context = _verify_page_context(request.context, current_user)

    # Persist the user turn (action turns carry a deterministic button label).
    if request.action is not None:
        user_content = _action_label(request.action)
        action_payload = request.action.model_dump(exclude_none=True)
    else:
        user_content = request.message or ''
        action_payload = None

    with tracing.span('db.insert_user_message'):
        user_msg_row = (
            db.table('chat_messages')
            .insert({
                'thread_id': thread_id,
                'role': 'user',
                'content': user_content,
                'payload': action_payload,
            })
            .execute()
        ).data[0]

    # Build the turn state (per-turn injected + rehydrated thread state) and run
    # the stateless graph. reference_time_utc is injected so the graph stays
    # deterministic and never reads the wall clock.
    state = {
        # per-turn injected
        'user_id': current_user.id,
        'user_token': current_user.token,
        'user_email': current_user.email_address,
        'user_full_name': current_user.full_name,
        'user_timezone': request.timezone,
        'reference_time_utc': reference_time_utc,
        'user_message': request.message,
        'action': action_payload,
        'page_context': page_context,
        # rehydrated thread state
        'status': thread_row.get('status'),
        'workflow': thread_row.get('workflow'),
        'draft': thread_row.get('draft'),
        'participants': thread_row.get('participants'),
        'pending_people': thread_row.get('pending_people'),
        'candidate_slots': thread_row.get('candidate_slots'),
        'booking_mode': thread_row.get('booking_mode'),
    }
    compiled = graph.get_compiled_graph()
    with tracing.span('graph.invoke'):
        output = compiled.invoke(state)

    # Persist the assistant turn — payload is the single card+buttons encoding.
    assistant_content = output.get('assistant_text') or ''
    assistant_payload = {
        'card': output.get('card'),
        'buttons': output.get('buttons') or [],
    }
    with tracing.span('db.insert_assistant_message'):
        assistant_msg_row = (
            db.table('chat_messages')
            .insert({
                'thread_id': thread_id,
                'role': 'assistant',
                'content': assistant_content,
                'payload': assistant_payload,
            })
            .execute()
        ).data[0]

    # Write the advanced thread state back.
    result_event_uid = output.get('result_event_uid')
    thread_update = {
        'status': output.get('status'),
        'workflow': output.get('workflow'),
        'draft': output.get('draft'),
        'participants': output.get('participants'),
        'pending_people': output.get('pending_people'),
        'candidate_slots': output.get('candidate_slots'),
        'booking_mode': output.get('booking_mode'),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    if result_event_uid:
        thread_update['last_event_uid'] = result_event_uid
    if not thread_row.get('title'):
        thread_update['title'] = _truncate_title(user_content)

    with tracing.span('db.update_thread'):
        updated = (
            db.table('chat_threads')
            .update(thread_update)
            .eq('id', thread_id)
            .execute()
        )
    thread_final_row = updated.data[0] if updated.data else {**thread_row, **thread_update}

    return ChatTurnResponse(
        thread=_row_to_thread_response(thread_final_row),
        messages=[
            _row_to_message_response(user_msg_row),
            _row_to_message_response(assistant_msg_row),
        ],
        event_uid=result_event_uid,
        # Only set when this turn created a brand-new event (in-app or direct
        # book), never on an edit — the client opens the new event page.
        created_event_uid=result_event_uid if output.get('result_created') else None,
    )
