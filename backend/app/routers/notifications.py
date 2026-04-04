from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.notification import NotificationResponse, NotificationActionRequest
from app.models.user import User
from app.services import notification_service

router = APIRouter(prefix='/api/notifications', tags=['notifications'])


@router.get('', response_model=list[NotificationResponse])
def get_notifications(current_user: User = Depends(get_current_user)):
    return notification_service.get_notifications(current_user)


@router.post('/read-all', status_code=204)
def mark_all_read(current_user: User = Depends(get_current_user)):
    notification_service.mark_all_read(current_user)


@router.post('/{id}/read', response_model=NotificationResponse)
def mark_read(id: str, current_user: User = Depends(get_current_user)):
    return notification_service.mark_read(id, current_user)


@router.post('/{id}/action', response_model=NotificationResponse)
def take_action(id: str, data: NotificationActionRequest, current_user: User = Depends(get_current_user)):
    return notification_service.take_action(id, current_user, data.action)
