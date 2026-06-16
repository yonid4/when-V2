from datetime import datetime, timezone

from fastapi import HTTPException

from app.models.notification import NotificationResponse
from app.models.user import User
from app.services.invitation_service import respond_to_invitation
from app.utils.supabase import get_authed_client, service_client


def _row_to_response(row: dict) -> NotificationResponse:
    event_uid = None
    if row.get('event_id'):
        event_row = row.get('events')
        if isinstance(event_row, dict):
            event_uid = event_row.get('uid')
    return NotificationResponse(
        id=row['id'],
        user_id=row['user_id'],
        event_id=row.get('event_id'),
        event_uid=event_uid,
        notification_type=row['notification_type'],
        title=row['title'],
        message=row['message'],
        is_read=row['is_read'],
        action_taken=row['action_taken'],
        action_type=row.get('action_type'),
        metadata=row.get('metadata'),
        created_at=row['created_at'],
        read_at=row.get('read_at'),
        action_at=row.get('action_at'),
    )


def get_notifications(current_user: User) -> list[NotificationResponse]:
    db = get_authed_client(current_user.token)
    result = (
        db.table('notifications')
        .select('*, events(uid)')
        .eq('user_id', current_user.id)
        .order('created_at', desc=True)
        .execute()
    )
    return [_row_to_response(r) for r in (result.data or [])]


def mark_read(notification_id: str, current_user: User) -> NotificationResponse:
    db = get_authed_client(current_user.token)
    result = db.table('notifications').select('*').eq('id', notification_id).limit(1).execute()
    if not result or not result.data:
        raise HTTPException(status_code=404, detail='Notification not found')
    row = result.data[0]
    if row['user_id'] != current_user.id:
        raise HTTPException(status_code=403, detail='Access denied')

    now = datetime.now(timezone.utc).isoformat()
    updated = (
        service_client.table('notifications')
        .update({'is_read': True, 'read_at': now})
        .eq('id', notification_id)
        .execute()
    )
    return _row_to_response(updated.data[0])


def mark_all_read(current_user: User) -> None:
    now = datetime.now(timezone.utc).isoformat()
    service_client.table('notifications').update(
        {'is_read': True, 'read_at': now}
    ).eq('user_id', current_user.id).eq('is_read', False).execute()


def _resolve_invitation_action(invitation_id: str, fallback: str) -> str:
    """Map an already-responded invitation's status to a notification action_type."""
    result = (
        service_client.table('event_invitations')
        .select('status')
        .eq('id', invitation_id)
        .maybe_single()
        .execute()
    )
    status = result.data['status'] if (result and result.data) else None
    if status == 'accepted':
        return 'accept'
    if status == 'declined':
        return 'decline'
    return fallback


def take_action(notification_id: str, current_user: User, action: str) -> NotificationResponse:
    db = get_authed_client(current_user.token)
    result = db.table('notifications').select('*').eq('id', notification_id).limit(1).execute()
    if not result or not result.data:
        raise HTTPException(status_code=404, detail='Notification not found')

    notification = result.data[0]
    if notification['user_id'] != current_user.id:
        raise HTTPException(status_code=403, detail='Access denied')

    now = datetime.now(timezone.utc).isoformat()

    if notification['notification_type'] == 'event_invitation':
        metadata = notification.get('metadata') or {}
        invitation_id = metadata.get('invitation_id')
        if invitation_id:
            try:
                respond_to_invitation(invitation_id, current_user, action)
            except HTTPException as exc:
                # Invitation already responded to (e.g. via an older flow that did
                # not stamp the notification). Sync the notification to the
                # invitation's real status instead of failing, so it stops
                # offering accept/decline. Other errors (e.g. calendar_required)
                # propagate unchanged.
                if exc.status_code != 409:
                    raise
                action = _resolve_invitation_action(invitation_id, action)

    service_client.table('notifications').update(
        {'action_taken': True, 'action_type': action, 'action_at': now}
    ).eq('id', notification_id).execute()

    refreshed = (
        db.table('notifications')
        .select('*, events(uid)')
        .eq('id', notification_id)
        .limit(1)
        .execute()
    )
    return _row_to_response(refreshed.data[0])
