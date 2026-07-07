from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.slot import ProposalResponse
from app.models.user import User
from app.services.proposal_service import (
    generate_proposals,
    get_cached_proposals,
    get_event_and_check_access,
)

router = APIRouter(tags=["proposals"])


@router.post(
    "/api/events/{uid}/proposals",
    response_model=list[ProposalResponse],
)
def get_or_generate_proposals(
    uid: str,
    current_user: User = Depends(get_current_user),
):
    """Return cached proposals if fresh, otherwise generate new ones."""
    event = get_event_and_check_access(uid, current_user.id)

    if not event["proposals_needs_regeneration"]:
        cached = get_cached_proposals(event["id"])
        if cached:
            return cached

    # Capture the request instant here (transport concern) and inject it so the
    # scheduling service stays deterministic and never reads the wall clock.
    reference_time_utc = datetime.now(timezone.utc)
    return generate_proposals(event["id"], reference_time_utc=reference_time_utc)


@router.post(
    "/api/events/{uid}/proposals/refresh",
    response_model=list[ProposalResponse],
)
def refresh_proposals(
    uid: str,
    current_user: User = Depends(get_current_user),
):
    """Force regenerate proposals regardless of cache state."""
    event = get_event_and_check_access(uid, current_user.id, coordinator_only=True)
    # Capture the request instant here (transport concern) and inject it so the
    # scheduling service stays deterministic and never reads the wall clock.
    reference_time_utc = datetime.now(timezone.utc)
    return generate_proposals(event["id"], reference_time_utc=reference_time_utc)
