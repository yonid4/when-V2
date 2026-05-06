import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    account,
    auth,
    busy_slots,
    calendar_accounts,
    calendar_sources,
    events,
    finalize,
    invitations,
    notifications,
    participants,
    preferred_slots,
    proposal_notes,
    proposals,
)
from app.scheduler.jobs import sync_all_users_job

# Allow OAuth over HTTP for local development
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    # Sync all users' busy slots every hour
    scheduler.add_job(sync_all_users_job, "interval", hours=1, id="sync_all_users")
    scheduler.start()
    logger.info("APScheduler started — busy-slot sync every 1 hour")
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")


app = FastAPI(title="When. v2", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(participants.router)
app.include_router(invitations.router)
app.include_router(notifications.router)
app.include_router(calendar_accounts.router)
app.include_router(calendar_sources.router)
app.include_router(busy_slots.router)
app.include_router(preferred_slots.router)
app.include_router(proposals.router)
app.include_router(proposal_notes.router)
app.include_router(finalize.router)
app.include_router(account.router)
