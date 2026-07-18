"""LLM helpers for the chat agent.

The model object is always INJECTED into the graph/people layer (a parameter
implementing ``.with_structured_output(schema).invoke(...)`` for structured calls
and ``.invoke(prompt).content`` for free-text replies). This module never imports
any LLM SDK at import time — ``get_chat_model`` performs a LAZY import of
``langchain_google_genai`` so importing ``llm.py`` (and, transitively,
``people.py`` and the tests) stays cheap and SDK-free.

Contents:

* ``EmailPairing`` + ``judge_email_pairing`` — the name↔email pairing judgment.
* ``ExtractedTurn`` + ``build_extraction_prompt`` — the single structured
  intent-classification/field-extraction call.
* ``build_reply_prompt`` — the wording-only prompt for the terminal reply node.
* ``get_chat_model`` — the concrete Gemini chat model factory (lazy).

The LLM is used ONLY for intent classification + field extraction, name↔email
pairing, and composing reply wording. It NEVER selects slots or drives control
flow — that is 100% deterministic Python in the graph.
"""

from typing import Literal

from pydantic import BaseModel, Field


def get_chat_model():
    """Build the concrete Gemini chat model (temperature 0 for determinism).

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
    )


class EmailPairing(BaseModel):
    """Judgment: does an unattributed email belong to a named person?

    Used for the one place the chat agent needs an LLM — pairing a bare name with
    a loose email in the same message. It is NOT part of deterministic slot
    selection.
    """

    same_person: bool = Field(
        description="True if the email address belongs to the named person, else False.",
    )


def judge_email_pairing(llm, name: str, email: str, message: str) -> bool:
    """Ask the injected ``llm`` whether ``email`` belongs to ``name``.

    ``llm`` must implement ``.with_structured_output(schema).invoke(prompt)`` and
    return an :class:`EmailPairing`. The model is injected so this module never
    depends on any LLM SDK. Returns the boolean ``same_person`` verdict.
    """
    prompt = _build_pairing_prompt(name, email, message)
    result = llm.with_structured_output(EmailPairing).invoke(prompt)
    return bool(result.same_person)


def _build_pairing_prompt(name: str, email: str, message: str) -> str:
    """Build the pairing prompt. Kept separate so it can be unit-tested/tuned."""
    return (
        "You are resolving who an email address belongs to in a scheduling "
        "request. Given the user's message, a named person mentioned in it, and "
        "an email address that was written without a clear owner, decide whether "
        "the email belongs to that named person.\n\n"
        f"Message: {message!r}\n"
        f"Named person: {name!r}\n"
        f"Unattributed email: {email!r}\n\n"
        "Respond with same_person=true only if the email clearly belongs to the "
        "named person; otherwise same_person=false."
    )


# ── Intent classification + field extraction ────────────────────────────────

class PersonMention(BaseModel):
    """One person the user referred to in THIS message (name and/or email)."""

    name: str | None = Field(default=None, description="The person's name as written, if any.")
    email: str | None = Field(default=None, description="An email address for the person, if given.")


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
) -> str:
    """Assemble the extraction prompt (pure string; unit-testable).

    Feeds the model the local calendar anchor (today + weekday + tz), the daypart
    defaults, the current draft (so revisions merge), the already-added people (so
    they are not repeated), and any page context (so "this event" → an edit of
    that specific event). Field semantics match :class:`ExtractedTurn`.
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
        "- On a revision, fill ONLY the fields the user changed this message; leave "
        "everything else null (the app keeps prior values).",
        "- In 'people', list ONLY people newly mentioned in this message. Do not "
        "repeat people already added (shown below).",
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

    lines += ["", f"User message: {user_message!r}"]
    return "\n".join(lines)


# ── Reply wording (terminal node) ────────────────────────────────────────────

def build_reply_prompt(reply: dict, baseline: str) -> str:
    """Build the wording-only prompt for the terminal reply node.

    The model rephrases ``baseline`` (a deterministic draft already built from
    structured facts) into natural, concise wording. It is explicitly forbidden
    from adding facts, times, or names — so an LLM outage degrades wording only,
    never correctness (the caller falls back to ``baseline`` verbatim).
    """
    kind = (reply or {}).get('kind', 'help')
    return (
        "You are When., a friendly, concise scheduling assistant. Rewrite the draft "
        "reply below so it reads naturally in 1-2 short sentences.\n"
        "Do NOT add or change any facts, dates, times, names, or promises — keep "
        "every specific value exactly as written. Return only the reply text.\n\n"
        f"Situation: {kind}\n"
        f"Draft reply: {baseline}"
    )
