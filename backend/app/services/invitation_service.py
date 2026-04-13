
from fastapi import HTTPException

from app.models.invitation import InvitationResponse
from app.models.user import User
from app.services.event_service import fetch_event_by_uid
from app.utils.email import normalize_email
from app.utils.supabase import get_authed_client, service_client


def _row_to_response(row: dict) -> InvitationResponse:
    return InvitationResponse(
        id=row['id'],
        event_id=row['event_id'],
        inviter_id=row['inviter_id'],
        invitee_id=row.get('invitee_id'),
        invitee_email=row['invitee_email'],
        status=row['status'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
    )


def invite_by_email(uid: str, current_user: User, email: str) -> InvitationResponse:
    email = normalize_email(email)
    db = get_authed_client(current_user.token)
    event = fetch_event_by_uid(uid, db)
    event_id = event['id']
    event_name = event['name']

    # Check inviter has permission (coordinator or can_invite participant)
    is_coordinator = event['coordinator_id'] == current_user.id
    if not is_coordinator:
        perm_result = (
            db.table('event_participants')
            .select('can_invite')
            .eq('event_id', event_id)
            .eq('user_id', current_user.id)
            .maybe_single()
            .execute()
        )
        if not perm_result or not perm_result.data:
            raise HTTPException(status_code=403, detail='You are not a participant of this event')
        participant_row = perm_result.data
        if not participant_row.get('can_invite'):
            raise HTTPException(status_code=403, detail='You do not have permission to invite')

    # Look up invitee by email_address
    profile_result = (
        service_client.table('profiles')
        .select('id')
        .eq('email_address', email)
        .maybe_single()
        .execute()
    )
    invitee_id = profile_result.data['id'] if (profile_result and profile_result.data) else None

    if invitee_id:
        # Check not already a participant
        already_participant = (
            db.table('event_participants')
            .select('user_id')
            .eq('event_id', event_id)
            .eq('user_id', invitee_id)
            .maybe_single()
            .execute()
        )
        if already_participant and already_participant.data:
            raise HTTPException(status_code=409, detail='User is already a participant')

        # Check not already invited
        existing_invite = (
            service_client.table('event_invitations')
            .select('id, status')
            .eq('event_id', event_id)
            .eq('invitee_id', invitee_id)
            .eq('status', 'pending')
            .maybe_single()
            .execute()
        )
        if existing_invite and existing_invite.data:
            raise HTTPException(status_code=409, detail='User already has a pending invitation')
    else:
        # Check not already invited by email
        existing_email_invite = (
            service_client.table('event_invitations')
            .select('id, status')
            .eq('event_id', event_id)
            .eq('invitee_email', email)
            .eq('status', 'pending')
            .maybe_single()
            .execute()
        )
        if existing_email_invite and existing_email_invite.data:
            raise HTTPException(status_code=409, detail='This email already has a pending invitation')

    # Insert invitation
    invite_data = {
        'event_id': event_id,
        'inviter_id': current_user.id,
        'invitee_email': email,
        'status': 'pending',
    }
    if invitee_id:
        invite_data['invitee_id'] = invitee_id

    invite_result = service_client.table('event_invitations').insert(invite_data).execute()
    if not invite_result.data:
        raise HTTPException(status_code=500, detail='Failed to create invitation')

    # Notify existing user
    if invitee_id:
        service_client.table('notifications').insert({
            'user_id': invitee_id,
            'event_id': event_id,
            'notification_type': 'event_invitation',
            'title': 'You have been invited',
            'message': f'You have been invited to {event_name}.',
            'metadata': {'event_id': event_id, 'inviter_id': current_user.id, 'invitation_id': invite_result.data[0]['id']},
        }).execute()

    return _row_to_response(invite_result.data[0])


def respond_to_invitation(invitation_id: str, current_user: User, action: str) -> None:
    db = get_authed_client(current_user.token)

    result = (
        service_client.table('event_invitations')
        .select('*')
        .eq('id', invitation_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=404, detail='Invitation not found')

    invite = result.data

    if invite.get('invitee_id') != current_user.id:
        raise HTTPException(status_code=403, detail='This invitation is not for you')

    if invite['status'] != 'pending':
        raise HTTPException(status_code=409, detail='Invitation is no longer pending')

    if action == 'accept':
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        # Require at least one connected calendar source before accepting
        # calendar_sources links via account_id → calendar_accounts.user_id
        calendar_check = (
            service_client.table('calendar_sources')
            .select('id, calendar_accounts!inner(user_id)')
            .eq('calendar_accounts.user_id', current_user.id)
            .limit(1)
            .execute()
        )
        if not calendar_check.data:
            raise HTTPException(status_code=422, detail='calendar_required')

        # Add to event_participants
        service_client.table('event_participants').insert({
            'event_id': invite['event_id'],
            'user_id': current_user.id,
            'status': 'accepted',
            'rsvp_status': 'going',
            'can_invite': False,
            'joined_at': now,
        }).execute()

        # Update invitation status
        service_client.table('event_invitations').update({'status': 'accepted'}).eq('id', invitation_id).execute()

        # Notify coordinator and return event uid
        event_result = db.table('events').select('coordinator_id, name, uid').eq('id', invite['event_id']).maybe_single().execute()
        if event_result and event_result.data:
            event = event_result.data
            coordinator_id = event['coordinator_id']
            if coordinator_id != current_user.id:
                service_client.table('notifications').insert({
                    'user_id': coordinator_id,
                    'event_id': invite['event_id'],
                    'notification_type': 'invite_accepted',
                    'title': 'Invitation accepted',
                    'message': f'{current_user.full_name or current_user.email_address} accepted the invitation to {event["name"]}.',
                    'metadata': {'invitee_id': current_user.id, 'invitation_id': invitation_id},
                }).execute()
            return event.get('uid')

    elif action == 'decline':
        service_client.table('event_invitations').update({'status': 'declined'}).eq('id', invitation_id).execute()

    return None
