import logging

from app.services.sync_service import sync_all_users

logger = logging.getLogger(__name__)


def sync_all_users_job() -> None:
    """Scheduled job: sync busy slots for every user with a connected calendar."""
    logger.info("Starting scheduled busy-slot sync for all users")
    try:
        results = sync_all_users()
        total = sum(results.values())
        logger.info("Scheduled sync complete: %d slots upserted across %d users", total, len(results))
    except Exception as exc:
        logger.error("Scheduled sync failed: %s", exc)
