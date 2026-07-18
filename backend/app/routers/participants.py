from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user
from app.models.participant import (
    ParticipantResponse,
    RsvpUpdate,
    PermissionUpdate,
    DirectInviteResponse,
)
from app.models.user import User
from app.services import participant_service

router = APIRouter(prefix='/api/events', tags=['participants'])


@router.get('/{uid}/participants', response_model=list[ParticipantResponse])
def get_participants(uid: str, current_user: User = Depends(get_current_user)):
    return participant_service.get_participants(uid, current_user)


@router.put('/{uid}/participants/{user_id}/rsvp', response_model=ParticipantResponse)
def update_rsvp(uid: str, user_id: str, data: RsvpUpdate, current_user: User = Depends(get_current_user)):
    return participant_service.update_rsvp(uid, user_id, current_user, data.rsvp_status)


@router.put('/{uid}/participants/{user_id}/permissions', response_model=ParticipantResponse)
def update_permissions(uid: str, user_id: str, data: PermissionUpdate, current_user: User = Depends(get_current_user)):
    return participant_service.update_permissions(uid, user_id, current_user, data.can_invite)


@router.put('/{uid}/participants/me/response', response_model=ParticipantResponse)
def respond_to_direct_invite(uid: str, data: DirectInviteResponse, current_user: User = Depends(get_current_user)):
    return participant_service.respond_to_direct_invite(uid, current_user, data.action)


@router.delete('/{uid}/participants/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_participant(uid: str, user_id: str, current_user: User = Depends(get_current_user)):
    participant_service.remove_participant(uid, user_id, current_user)
