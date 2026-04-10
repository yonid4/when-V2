from fastapi import HTTPException

from app.models.participant import ParticipantResponse
from app.models.user import User
from app.utils.supabase import get_authed_client, service_client


def _fetch_event(uid: str, db) -> dict:
    result = db.table('events').select('id, coordinator_id').eq('uid', uid).maybe_single().execute()
    if not result or not result.data:
        raise HTTPException(status_code=404, detail='Event not found')
    return result.data


def _fetch_participants_raw(event_id: str, db) -> list[dict]:
    ep_result = (
        db.table('event_participants')
        .select('event_id, user_id, status, rsvp_status, can_invite, joined_at')
        .eq('event_id', event_id)
        .execute()
    )
    participants = ep_result.data or []
    if not participants:
        return []

    user_ids = [p['user_id'] for p in participants]
    profile_result = (
        service_client.table('profiles')
        .select('id, full_name, avatar_url, email_address')
        .in_('id', user_ids)
        .execute()
    )
    profile_map = {p['id']: p for p in (profile_result.data or [])}

    rows = []
    for p in participants:
        profile = profile_map.get(p['user_id'], {})
        row = {
            **p,
            'full_name': profile.get('full_name'),
            'avatar_url': profile.get('avatar_url'),
            'email_address': profile.get('email_address'),
        }
        rows.append(row)
    return rows


def _require_member(participants: list[dict], user_id: str) -> None:
    ids = {p['user_id'] for p in participants}
    if user_id not in ids:
        raise HTTPException(status_code=403, detail='Access denied')


def _rows_to_response(rows: list[dict]) -> list[ParticipantResponse]:
    return [ParticipantResponse(**r) for r in rows]


def get_participants(uid: str, current_user: User) -> list[ParticipantResponse]:
    db = get_authed_client(current_user.token)
    event = _fetch_event(uid, db)
    participants = _fetch_participants_raw(event['id'], db)
    _require_member(participants, current_user.id)
    return _rows_to_response(participants)


def update_rsvp(uid: str, target_user_id: str, current_user: User, rsvp_status: str) -> ParticipantResponse:
    if target_user_id != current_user.id:
        raise HTTPException(status_code=403, detail='You can only update your own RSVP')

    db = get_authed_client(current_user.token)
    event = _fetch_event(uid, db)

    result = (
        db.table('event_participants')
        .update({'rsvp_status': rsvp_status})
        .eq('event_id', event['id'])
        .eq('user_id', target_user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail='Participant not found')

    participants = _fetch_participants_raw(event['id'], db)
    row = next((p for p in participants if p['user_id'] == target_user_id), None)
    if not row:
        raise HTTPException(status_code=404, detail='Participant not found')
    return ParticipantResponse(**row)


def update_permissions(uid: str, target_user_id: str, current_user: User, can_invite: bool) -> ParticipantResponse:
    db = get_authed_client(current_user.token)
    event = _fetch_event(uid, db)

    if event['coordinator_id'] != current_user.id:
        raise HTTPException(status_code=403, detail='Only the coordinator can update permissions')

    result = (
        db.table('event_participants')
        .update({'can_invite': can_invite})
        .eq('event_id', event['id'])
        .eq('user_id', target_user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail='Participant not found')

    participants = _fetch_participants_raw(event['id'], db)
    row = next((p for p in participants if p['user_id'] == target_user_id), None)
    if not row:
        raise HTTPException(status_code=404, detail='Participant not found')
    return ParticipantResponse(**row)


def remove_participant(uid: str, target_user_id: str, current_user: User) -> None:
    db = get_authed_client(current_user.token)
    event = _fetch_event(uid, db)

    is_coordinator = event['coordinator_id'] == current_user.id
    is_self = target_user_id == current_user.id

    if not is_coordinator and not is_self:
        raise HTTPException(status_code=403, detail='You are not allowed to remove this participant')

    result = (
        db.table('event_participants')
        .delete()
        .eq('event_id', event['id'])
        .eq('user_id', target_user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail='Participant not found')
