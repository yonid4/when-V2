from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.slot import PreferredSlotCreate, PreferredSlotResponse
from app.models.user import User
from app.services import preferred_slots_service

router = APIRouter(tags=["preferred-slots"])


@router.post(
    "/api/events/{uid}/preferred-slots",
    response_model=PreferredSlotResponse,
    status_code=201,
)
def create_preferred_slot(
    uid: str,
    data: PreferredSlotCreate,
    current_user: User = Depends(get_current_user),
):
    return preferred_slots_service.create_preferred_slot(uid, current_user.id, data)


@router.get(
    "/api/events/{uid}/preferred-slots",
    response_model=list[PreferredSlotResponse],
)
def get_preferred_slots(
    uid: str,
    current_user: User = Depends(get_current_user),
):
    return preferred_slots_service.get_preferred_slots(uid, current_user.id)


@router.delete(
    "/api/events/{uid}/preferred-slots/{slot_id}",
    status_code=204,
)
def delete_preferred_slot(
    uid: str,
    slot_id: str,
    current_user: User = Depends(get_current_user),
):
    preferred_slots_service.delete_preferred_slot(uid, slot_id, current_user.id)
