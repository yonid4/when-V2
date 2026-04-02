from datetime import datetime, timezone
from fastapi import HTTPException

from app.models.event import EventCreate, EventUpdate, EventResponse, ParticipantResponse
from app.models.user import User
from app.utils.supabase import get_authed_client, service_client
from app.utils.uid import generate_uid


def _row_to_event_response(row: dict, participants: list[dict]) -> EventResponse:
    participant_models = [
        ParticipantResponse(
            event_id=p['event_id'],
            user_id=p['user_id'],
            status=p['status'],
            rsvp_status=p.get('rsvp_status'),
            can_invite=p['can_invite'],
            joined_at=p['joined_at'],
            full_name=p.get('full_name'),
            avatar_url=p.get('avatar_url'),
            email_address=p.get('email_address'),
        )
        for p in participants
    ]
    return EventResponse(
        id=row['id'],
        uid=row['uid'],
        name=row['name'],
        description=row.get('description'),
        event_type=row['event_type'],
        coordinator_id=row['coordinator_id'],
        earliest_datetime_utc=row['earliest_datetime_utc'],
        latest_datetime_utc=row['latest_datetime_utc'],
        duration_minutes=row['duration_minutes'],
        status=row['status'],
        location=row.get('location'),
        video_call_link=row.get('video_call_link'),
        finalized_start_time_utc=row.get('finalized_start_time_utc'),
        finalized_end_time_utc=row.get('finalized_end_time_utc'),
        google_calendar_event_id=row.get('google_calendar_event_id'),
        proposals_needs_regeneration=row['proposals_needs_regeneration'],
        proposals_last_generated_at=row.get('proposals_last_generated_at'),
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        finalized_at=row.get('finalized_at'),
        participants=participant_models,
    )


def _fetch_participants(event_id: str, db) -> list[dict]:
    result = (
        db.table('event_participants')
        .select('event_id, user_id, status, rsvp_status, can_invite, joined_at, profiles(full_name, avatar_url, email_address)')
        .eq('event_id', event_id)
        .execute()
    )
    rows = []
    for p in (result.data or []):
        profile = p.pop('profiles') or {}
        rows.append({**p, **profile})
    return rows


def create_event(data: EventCreate, current_user: User) -> EventResponse:
    db = get_authed_client(current_user.token)
    uid = generate_uid()
    now = datetime.now(timezone.utc).isoformat()

    event_data = {
        'uid': uid,
        'name': data.name,
        'description': data.description,
        'event_type': data.event_type,
        'coordinator_id': current_user.id,
        'earliest_datetime_utc': data.earliest_datetime_utc.isoformat(),
        'latest_datetime_utc': data.latest_datetime_utc.isoformat(),
        'duration_minutes': data.duration_minutes,
        'status': 'planning',
        'location': data.location,
        'video_call_link': data.video_call_link,
        'proposals_needs_regeneration': False,
    }

    result = db.table('events').insert(event_data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail='Failed to create event')

    event_row = result.data[0]
    event_id = event_row['id']

    participant_data = {
        'event_id': event_id,
        'user_id': current_user.id,
        'status': 'accepted',
        'rsvp_status': 'going',
        'can_invite': True,
        'joined_at': now,
    }
    db.table('event_participants').insert(participant_data).execute()

    participants = _fetch_participants(event_id, db)
    return _row_to_event_response(event_row, participants)


def get_events_for_user(current_user: User) -> list[EventResponse]:
    db = get_authed_client(current_user.token)

    # Events where user is coordinator
    coordinator_result = (
        db.table('events')
        .select('*')
        .eq('coordinator_id', current_user.id)
        .execute()
    )

    # Events where user is participant (but not coordinator to avoid duplicates)
    participant_result = (
        db.table('event_participants')
        .select('event_id')
        .eq('user_id', current_user.id)
        .execute()
    )
    participant_event_ids = [
        p['event_id'] for p in (participant_result.data or [])
    ]

    # Fetch participant events that aren't already in coordinator list
    coordinator_ids = {e['id'] for e in (coordinator_result.data or [])}
    other_ids = [eid for eid in participant_event_ids if eid not in coordinator_ids]

    all_events = list(coordinator_result.data or [])

    if other_ids:
        other_result = (
            db.table('events')
            .select('*')
            .in_('id', other_ids)
            .execute()
        )
        all_events.extend(other_result.data or [])

    responses = []
    for event_row in all_events:
        participants = _fetch_participants(event_row['id'], db)
        responses.append(_row_to_event_response(event_row, participants))

    return responses


def get_event_by_uid(uid: str, current_user: User) -> EventResponse:
    db = get_authed_client(current_user.token)

    result = (
        db.table('events')
        .select('*')
        .eq('uid', uid)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail='Event not found')

    event_row = result.data
    event_id = event_row['id']

    participants = _fetch_participants(event_id, db)

    # Check access: must be coordinator or participant
    user_ids = {p['user_id'] for p in participants}
    if event_row['coordinator_id'] != current_user.id and current_user.id not in user_ids:
        raise HTTPException(status_code=403, detail='Access denied')

    return _row_to_event_response(event_row, participants)


def update_event(uid: str, data: EventUpdate, current_user: User) -> EventResponse:
    db = get_authed_client(current_user.token)

    result = (
        db.table('events')
        .select('*')
        .eq('uid', uid)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail='Event not found')

    event_row = result.data
    if event_row['coordinator_id'] != current_user.id:
        raise HTTPException(status_code=403, detail='Only the coordinator can update this event')

    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        participants = _fetch_participants(event_row['id'], db)
        return _row_to_event_response(event_row, participants)

    # Serialize datetime fields
    for field in ('earliest_datetime_utc', 'latest_datetime_utc'):
        if field in update_data and isinstance(update_data[field], datetime):
            update_data[field] = update_data[field].isoformat()

    # Mark proposals for regeneration if time window changes
    window_changed = 'earliest_datetime_utc' in update_data or 'latest_datetime_utc' in update_data
    if window_changed:
        update_data['proposals_needs_regeneration'] = True

    updated = (
        db.table('events')
        .update(update_data)
        .eq('id', event_row['id'])
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=500, detail='Failed to update event')

    participants = _fetch_participants(event_row['id'], db)
    return _row_to_event_response(updated.data[0], participants)


def delete_event(uid: str, current_user: User) -> None:
    db = get_authed_client(current_user.token)

    result = (
        db.table('events')
        .select('id, coordinator_id, name')
        .eq('uid', uid)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail='Event not found')

    event_row = result.data
    event_id = event_row['id']

    if event_row['coordinator_id'] != current_user.id:
        raise HTTPException(status_code=403, detail='Only the coordinator can delete this event')

    # Fetch all participants to notify
    participants_result = (
        db.table('event_participants')
        .select('user_id')
        .eq('event_id', event_id)
        .neq('user_id', current_user.id)
        .execute()
    )

    # Insert event_deleted notifications for all other participants
    notifications = [
        {
            'user_id': p['user_id'],
            'event_id': None,
            'notification_type': 'event_deleted',
            'title': 'Event cancelled',
            'message': f'"{event_row["name"]}" has been cancelled by the coordinator.',
            'is_read': False,
            'action_taken': False,
        }
        for p in (participants_result.data or [])
    ]

    if notifications:
        service_client.table('notifications').insert(notifications).execute()

    db.table('events').delete().eq('id', event_id).execute()
