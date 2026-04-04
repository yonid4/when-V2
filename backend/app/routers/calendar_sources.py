from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.calendar import CalendarSourceResponse, CalendarSourceUpdate
from app.models.user import User
from app.services import calendar_service

router = APIRouter(prefix="/api/calendar-sources", tags=["calendar-sources"])


@router.patch("/{source_id}", response_model=CalendarSourceResponse)
def update_source(
    source_id: str,
    data: CalendarSourceUpdate,
    current_user: User = Depends(get_current_user),
):
    return calendar_service.update_calendar_source(source_id, current_user.id, data)
