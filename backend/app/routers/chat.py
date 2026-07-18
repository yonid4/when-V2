from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user
from app.models.chat import (
    ChatMessageResponse,
    ChatThreadResponse,
    ChatTurnRequest,
    ChatTurnResponse,
)
from app.models.user import User
from app.services import chat_service

router = APIRouter(prefix='/api/chat', tags=['chat'])


@router.post('/threads', response_model=ChatThreadResponse, status_code=status.HTTP_201_CREATED)
def create_thread(current_user: User = Depends(get_current_user)):
    return chat_service.create_thread(current_user)


@router.get('/threads', response_model=list[ChatThreadResponse])
def list_threads(current_user: User = Depends(get_current_user)):
    return chat_service.list_threads(current_user)


@router.get('/threads/{thread_id}/messages', response_model=list[ChatMessageResponse])
def get_thread_messages(thread_id: str, current_user: User = Depends(get_current_user)):
    return chat_service.get_thread_messages(thread_id, current_user)


@router.delete('/threads/{thread_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(thread_id: str, current_user: User = Depends(get_current_user)):
    chat_service.delete_thread(thread_id, current_user)


@router.post('/threads/{thread_id}/turn', response_model=ChatTurnResponse)
def run_turn(
    thread_id: str,
    request: ChatTurnRequest,
    current_user: User = Depends(get_current_user),
):
    # Capture the request instant here (transport concern) and inject it so the
    # agent graph stays deterministic and never reads the wall clock.
    reference_time_utc = datetime.now(timezone.utc)
    return chat_service.run_turn(thread_id, request, reference_time_utc, current_user)
