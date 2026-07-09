from fastapi import HTTPException, status

from app.utils.supabase import service_client


def ensure_proposed_time_in_event(proposed_time_id: str, event_id: str) -> None:
    result = (
        service_client.table("proposed_times")
        .select("id")
        .eq("id", proposed_time_id)
        .eq("event_id", event_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proposed time not found"
        )


def get_notes(proposed_time_id: str) -> list[dict]:
    result = (
        service_client.table("proposed_time_notes")
        .select("*")
        .eq("proposed_time_id", proposed_time_id)
        .order("created_at")
        .execute()
    )
    return result.data or []


def create_note(proposed_time_id: str, user_id: str, content: str, event_uid: str) -> dict:
    result = (
        service_client.table("proposed_time_notes")
        .insert({
            "proposed_time_id": proposed_time_id,
            "user_id": user_id,
            "content": content,
            "event_uid": event_uid,
        })
        .execute()
    )
    return result.data[0]


def delete_note(note_id: str, user_id: str) -> None:
    result = (
        service_client.table("proposed_time_notes")
        .delete()
        .eq("id", note_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
