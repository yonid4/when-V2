from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.invitation import InviteRequest, InvitationResponse, InvitationRespondRequest
from app.models.user import User
from app.services import invitation_service

router = APIRouter(tags=['invitations'])


@router.post('/api/events/{uid}/invite', response_model=InvitationResponse, status_code=201)
def invite_by_email(uid: str, data: InviteRequest, current_user: User = Depends(get_current_user)):
    return invitation_service.invite_by_email(uid, current_user, data.email)


@router.put('/api/invitations/{id}/respond', status_code=204)
def respond_to_invitation(id: str, data: InvitationRespondRequest, current_user: User = Depends(get_current_user)):
    invitation_service.respond_to_invitation(id, current_user, data.action)
