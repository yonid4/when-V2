"""Agent graph state (Package 5).

``AgentState`` is the single TypedDict threaded through the LangGraph graph. It is
``total=False`` so nodes return sparse partial updates (LangGraph merges each
returned key with last-write-wins). Three groups of keys:

* **Per-turn injected** by ``chat_service.run_turn`` — request-scoped facts the
  graph never mutates for its own sake (``user_*``, ``reference_time_utc``,
  ``user_message`` / ``action`` / ``page_context``).
* **Rehydrated thread state** — the workflow snapshot loaded from the
  ``chat_threads`` row (``status``, ``workflow``, ``draft`` …). Written back
  verbatim by ``run_turn`` after the turn.
* **Turn outputs** — what the turn produced (``assistant_text``, ``card``,
  ``buttons``, ``result_event_uid``) plus internal routing/scratch keys
  (``intent``, ``extracted``, ``reply``, ``route``, ``error_code``) that
  ``run_turn`` simply ignores (they are not persisted).

Only plain JSON-serializable values live in the persisted keys (``draft`` and
``card``/``buttons`` become jsonb). ``extracted`` (a Pydantic object) and
``reply`` are internal scratch and never persisted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # ── Per-turn injected (request-scoped) ──────────────────────────────────
    user_id: str
    user_token: str
    user_email: str
    user_full_name: str | None
    user_timezone: str | None
    reference_time_utc: datetime
    user_message: str | None
    action: dict | None
    page_context: dict | None

    # ── Rehydrated thread state (persisted between turns) ────────────────────
    status: str | None
    workflow: str | None
    draft: dict | None
    participants: list | None
    pending_person: dict | None
    candidate_slots: list | None
    booking_mode: str | None

    # ── Turn outputs (persisted where run_turn reads them) ───────────────────
    assistant_text: str
    card: dict | None
    buttons: list
    result_event_uid: str | None

    # ── Internal scratch (never persisted) ───────────────────────────────────
    intent: str | None
    extracted: Any
    reply: dict | None
    route: str
    error_code: str | None
