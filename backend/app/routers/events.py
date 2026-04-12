from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models.event import EventCreate, EventUpdate, EventResponse
from app.models.slot import AvailabilitySegment
from app.models.user import User
from app.services import availability_service, event_service

router = APIRouter(prefix='/api/events', tags=['events'])


@router.get('', response_model=list[EventResponse])
def list_events(current_user: User = Depends(get_current_user)):
    return event_service.get_events_for_user(current_user)


@router.post('', response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(data: EventCreate, current_user: User = Depends(get_current_user)):
    result = event_service.create_event(data, current_user)
    if result is None:
        raise HTTPException(status_code=500, detail='Failed to create event')
    return result


@router.get('/{uid}', response_model=EventResponse)
def get_event(uid: str, current_user: User = Depends(get_current_user)):
    return event_service.get_event_by_uid(uid, current_user)


@router.patch('/{uid}', response_model=EventResponse)
def update_event(uid: str, data: EventUpdate, current_user: User = Depends(get_current_user)):
    return event_service.update_event(uid, data, current_user)


@router.delete('/{uid}', status_code=status.HTTP_204_NO_CONTENT)
def delete_event(uid: str, current_user: User = Depends(get_current_user)):
    event_service.delete_event(uid, current_user)


@router.get('/{uid}/availability-segments', response_model=list[AvailabilitySegment])
def get_availability_segments(uid: str, current_user: User = Depends(get_current_user)):
    """Return pre-computed availability segments for the event grid."""
    return availability_service.compute_availability_segments(uid, current_user.id)
