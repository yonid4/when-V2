"""User-driven account deletion."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user
from app.models.user import User
from app.services import account_service
from app.utils.google_auth import TokenRevocationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/account", tags=["account"])


@router.delete("", status_code=204)
def delete_my_account(current_user: User = Depends(get_current_user)):
    """Delete the authenticated user's account and all owned data.

    Returns 204 on success, 502 if a Google token revocation could not be
    confirmed (in which case nothing is deleted and the user can retry).
    """
    try:
        account_service.delete_account(current_user.id)
    except TokenRevocationError as exc:
        logger.warning("Aborting account deletion for %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=502,
            detail="Could not revoke a Google token — please try again in a moment.",
        )
