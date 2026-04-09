from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.models.user import User
from app.services.proposal_service import generate_proposals
from app.utils.supabase import service_client

router = APIRouter(tags=["proposals"])


# ─── Models ──────────────────────────────────────────────────────────────────

class ProposalResponse(BaseModel):
    id: str
    event_id: str
    start_time_utc: str
    end_time_utc: str
    conflict_count: int
    preferred_count: int
    reasoning: str
    rank: int


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_event_and_check_access(uid: str, user_id: str, coordinator_only: bool = False) -> dict:
    """Look up event by uid and verify access.
    Returns the event row.
    Raises 404 if not found, 403 if unauthorized.
    """
    event_result = (
        service_client.table("events")
        .select("id, coordinator_id, proposals_needs_regeneration")
        .eq("uid", uid)
        .maybe_single()
        .execute()
    )
    if not event_result or not event_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    event = event_result.data

    if event["coordinator_id"] == user_id:
        return event

    if coordinator_only:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Coordinator only")

    # Check accepted participant
    participant_result = (
        service_client.table("event_participants")
        .select("user_id")
        .eq("event_id", event["id"])
        .eq("user_id", user_id)
        .eq("status", "accepted")
        .maybe_single()
        .execute()
    )
    if not participant_result or not participant_result.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an accepted participant")

    return event


def _get_cached_proposals(event_id: str) -> list[dict]:
    result = (
        service_client.table("proposed_times")
        .select("id, event_id, start_time_utc, end_time_utc, conflicts, preferred_count, reasoning, rank")
        .eq("event_id", event_id)
        .order("rank")
        .execute()
    )
    rows = result.data or []
    return [
        {
            "id": row["id"],
            "event_id": row["event_id"],
            "start_time_utc": row["start_time_utc"],
            "end_time_utc": row["end_time_utc"],
            "conflict_count": row.get("conflicts", 0),
            "preferred_count": row.get("preferred_count", 0),
            "reasoning": row["reasoning"],
            "rank": row["rank"],
        }
        for row in rows
    ]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post(
    "/api/events/{uid}/proposals",
    response_model=list[ProposalResponse],
)
def get_or_generate_proposals(
    uid: str,
    current_user: User = Depends(get_current_user),
):
    """Return cached proposals if fresh, otherwise generate new ones."""
    event = _get_event_and_check_access(uid, current_user.id)

    # Return cached if not stale and rows exist
    if not event["proposals_needs_regeneration"]:
        cached = _get_cached_proposals(event["id"])
        if cached:
            return cached

    # Generate fresh proposals
    return generate_proposals(event["id"])


@router.post(
    "/api/events/{uid}/proposals/refresh",
    response_model=list[ProposalResponse],
)
def refresh_proposals(
    uid: str,
    current_user: User = Depends(get_current_user),
):
    """Force regenerate proposals regardless of cache state. Coordinator only."""
    event = _get_event_and_check_access(uid, current_user.id, coordinator_only=True)
    return generate_proposals(event["id"])
