"""LLM helpers for the chat agent.

The model object is always INJECTED into the graph/people layer (a parameter
implementing ``.with_structured_output(schema).invoke(...)`` for structured calls
and ``.invoke(prompt).content`` for free-text replies). This module never imports
any LLM SDK at import time — ``get_chat_model`` performs a LAZY import of
``langchain_google_genai`` so importing ``llm.py`` (and, transitively,
``people.py`` and the tests) stays cheap and SDK-free.

Contents:

* ``ExtractedTurn`` + ``build_extraction_prompt`` — the single structured
  intent-classification/field-extraction call. Name↔email pairing is folded into
  this one call (the extraction model attributes emails to the people it lists),
  so there is no separate pairing round-trip.
* ``get_chat_model`` — the concrete Gemini chat model factory (lazy).

The LLM is used ONLY for intent classification + field extraction (a single
call). It NEVER words replies (those are deterministic templates), NEVER selects
slots, and never drives control flow — that is 100% deterministic Python in the
graph.
"""

from typing import Literal

from pydantic import BaseModel, Field


def get_chat_model():
    """Build the concrete Gemini chat model (temperature 0 for determinism).

    ``thinking_budget=0`` disables Gemini 2.5 Flash's default dynamic thinking —
    the agent's call is a simple extraction task that gains nothing from it, and
    thinking adds seconds of latency per call. (Gemini 2.5 Pro cannot disable
    thinking; keep ``GEMINI_MODEL`` on a Flash-tier model.)

    The ``langchain_google_genai`` SDK is imported HERE, lazily, so that merely
    importing this module never loads the SDK. Callers inject the returned object
    into the graph; tests inject a fake instead and never call this.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    from app.config import settings

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
        thinking_budget=0,
    )


# ── Intent classification + field extraction ────────────────────────────────

class PersonMention(BaseModel):
    """One person the user referred to in THIS message.

    Carries the person's name and/or their email. When the message gives both a
    name and an email that belong to the SAME person, they go on ONE mention (the
    model attributes the email to the name — no separate pairing step). An email
    appears with no name only when its owner is genuinely unclear.
    """

    name: str | None = Field(default=None, description="The person's name as written, if any.")
    email: str | None = Field(
        default=None,
        description="This person's email, if the message gives one that belongs to them.",
    )


class ExtractedTurn(BaseModel):
    """One structured read of the user's turn: intent + intent-specific fields.

    A single schema carries both create-fields and edit-fields; only the block
    matching ``intent`` is filled. Dates/times are LOCAL strings the graph parses
    (``YYYY-MM-DD`` / ``HH:MM``) — the model NEVER emits UTC. On a revision the
    model fills only the fields the user actually changed (the rest stay ``None``
    and the graph merges them onto the current draft). ``people`` lists only
    people newly mentioned in this message (already-added people are not
    repeated). Extract SEARCH WINDOWS only, never a specific meeting time.
    """

    intent: Literal['create_event', 'edit_event', 'other'] = Field(
        description="'create_event' to schedule a new event, 'edit_event' to change an existing one, else 'other'.",
    )

    # create-event fields
    title: str | None = Field(default=None, description="Event title/name.")
    event_type: Literal['meeting', 'social', 'birthday', 'other'] | None = Field(
        default=None, description="Best-fit category for the event.",
    )
    start_date: str | None = Field(default=None, description="Window start date, local, YYYY-MM-DD.")
    end_date: str | None = Field(default=None, description="Window end date, local, YYYY-MM-DD.")
    start_time: str | None = Field(default=None, description="Daily window start time, local, HH:MM (24h).")
    end_time: str | None = Field(default=None, description="Daily window end time, local, HH:MM (24h).")
    duration_minutes: int | None = Field(default=None, description="Meeting length in minutes.")
    location: str | None = Field(default=None, description="Location, if stated.")
    people: list[PersonMention] = Field(
        default_factory=list, description="People newly mentioned this turn (name and/or email).",
    )

    # edit-event fields (only the fields the user asked to change)
    edit_name: str | None = Field(default=None, description="New event name.")
    edit_description: str | None = Field(default=None, description="New description.")
    edit_location: str | None = Field(default=None, description="New location.")
    edit_video_call_link: str | None = Field(default=None, description="New video-call link (http/https).")
    edit_duration_minutes: int | None = Field(default=None, description="New duration in minutes.")
    edit_start_date: str | None = Field(default=None, description="New window start date, local, YYYY-MM-DD.")
    edit_end_date: str | None = Field(default=None, description="New window end date, local, YYYY-MM-DD.")
    edit_start_time: str | None = Field(default=None, description="New window start time, local, HH:MM (24h).")
    edit_end_time: str | None = Field(default=None, description="New window end time, local, HH:MM (24h).")


def build_extraction_prompt(
    *,
    user_message: str,
    current_draft: dict | None,
    participants: list | None,
    page_context: dict | None,
    workflow: str | None,
    today_str: str,
    weekday: str,
    tz_name: str | None,
    history: list | None = None,
) -> str:
    """Assemble the extraction prompt (pure string; unit-testable).

    Feeds the model the local calendar anchor (today + weekday + tz), the daypart
    defaults, the current draft (so revisions merge), the already-added people (so
    they are not repeated), the recent conversation (so a terse follow-up keeps
    the intent of what came before), and any page context (so "this event" → an
    edit of that specific event). Field semantics match :class:`ExtractedTurn`.

    ``history`` is a chronological (oldest-first) list of ``{'role', 'content'}``
    turns EXCLUDING the current message, capped by the caller.
    """
    lines: list[str] = [
        "You are the extraction step of When., a scheduling assistant. Read the "
        "user's latest message and output structured fields ONLY — you do not "
        "reply, schedule, or pick times.",
        "",
        f"Today is {weekday}, {today_str} in the user's timezone ({tz_name or 'UTC'}). "
        "Resolve relative dates (\"next Tuesday\", \"this weekend\") against that.",
        "",
        "Rules:",
        "- Classify intent: 'create_event' (schedule something new), 'edit_event' "
        "(change an existing event), or 'other' (anything else).",
        "- Output LOCAL dates (YYYY-MM-DD) and times (HH:MM, 24h). Never output UTC.",
        "- Extract a SEARCH WINDOW (earliest/latest the event could happen), never a "
        "single chosen meeting time.",
        "- Daypart defaults when a part of day is named: morning 08:00-12:00, "
        "afternoon 12:00-17:00, evening 17:00-21:00. Default duration 60 minutes.",
        "- When the event is a meal or activity that implies a time of day but no "
        "explicit time is given, set start_time/end_time to a LOCAL window that "
        "fits it rather than the whole business day: breakfast 08:00-10:00, brunch "
        "10:00-12:00, lunch 12:00-14:00, coffee 09:00-17:00, drinks/happy hour "
        "17:00-20:00, dinner 18:00-21:00, late night 21:00-23:30. For any other "
        "activity, infer the window people would normally do it in.",
        "- On a revision, fill ONLY the fields the user changed this message; leave "
        "everything else null (the app keeps prior values).",
        "- In 'people', list ONLY people newly mentioned in this message. Do not "
        "repeat people already added (shown below).",
        "- Attribute emails: when the message gives a person's name AND an email "
        "that belongs to them (e.g. \"invite Sarah, sarah@acme.com\"), put the name "
        "and the email on the SAME person entry. List an email with no name only "
        "when you genuinely cannot tell whose it is. Never list the same email twice.",
    ]

    if history:
        lines += [
            "- Read the latest message IN THE CONTEXT of the conversation below. A "
            "short reply that answers the assistant's last question continues that "
            "same intent — e.g. a bare date answering \"when should this happen?\" "
            "is still 'create_event', not 'other'. Do not re-extract people or "
            "details from earlier messages; the app already kept those.",
        ]

    if workflow == 'edit_event' or (page_context and page_context.get('uid')):
        lines += [
            "- An event is currently in focus (below). If the user asks to change it "
            "(\"this event\", \"the meeting\", \"move it\", \"rename it\"), use "
            "intent='edit_event' and fill only edit_* fields for what changed.",
        ]

    if page_context and page_context.get('uid'):
        lines += [
            "",
            "Event in focus (page context):",
            f"  name: {page_context.get('name')!r}",
            f"  status: {page_context.get('status')}",
            f"  window (UTC): {page_context.get('earliest_datetime_utc')} → {page_context.get('latest_datetime_utc')}",
            f"  duration_minutes: {page_context.get('duration_minutes')}",
        ]

    if current_draft:
        summary = {
            k: current_draft.get(k)
            for k in ('title', 'event_type', 'duration_minutes', 'location', 'local', 'event_name')
            if current_draft.get(k) is not None
        }
        if summary:
            lines += ["", f"Current draft so far: {summary}"]

    if participants:
        names = [p.get('full_name') or p.get('email') for p in participants]
        lines += ["", f"People already added (do not repeat): {names}"]

    if history:
        lines += ["", "Conversation so far (oldest first, background context only):"]
        lines += [f"  {turn.get('role')}: {turn.get('content')!r}" for turn in history]

    # The latest message goes last so it is the most recent thing the model reads.
    lines += ["", f"Latest user message: {user_message!r}"]
    return "\n".join(lines)
