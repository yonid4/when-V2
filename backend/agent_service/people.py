"""People resolution for the chat-create workflow (deterministic + one LLM call).

Turns extracted mentions ``[{name?, email?}]`` into resolved participant items
and, when a bare name is ambiguous or unknown, a single ``pending_person`` the
graph surfaces to the coordinator. Resolution order per mention (plan §4):

1. Explicit email wins → ``profiles`` lookup by ``email_address`` (normalized),
   with nested ``calendar_accounts(id)`` for ``has_calendar``. Miss →
   ``in_system=False`` (the invitation flow covers non-users).
2. Bare name + an unattributed email in the same message → one LLM
   ``EmailPairing`` call; if it says same person, attach the email and treat it
   as an explicit email.
3. Bare name → co-participant directory: exact casefolded ``full_name`` match,
   else a unique first-token match. Two or more → ``ambiguous`` pending; none →
   ``no_match`` pending.

Only one pending person is returned at a time (the first encountered); the graph
resolves it and calls again. ``MAX_CHAT_PEOPLE`` caps how many mentions are
processed per request.

Resolved participant item shape (stored in the thread's jsonb)::

    {user_id?, full_name, email, in_system, has_calendar,
     source: 'explicit_email' | 'coparticipant' | 'user_provided'}

The LLM object is INJECTED (``llm`` param); this module never imports any LLM
SDK. Deterministic logic (directory matching) never uses the LLM.
"""

import logging

from agent_service import tracing
from agent_service.llm import judge_email_pairing
from app.utils.email import normalize_email
from app.utils.supabase import service_client

logger = logging.getLogger(__name__)

MAX_CHAT_PEOPLE = 10

_PROFILE_COLUMNS = "id, full_name, email_address, calendar_accounts(id)"


# ─── Public API ───────────────────────────────────────────────────────────────

def resolve_mentions(
    mentions: list[dict],
    *,
    coordinator_id: str,
    message: str = "",
    llm=None,
    db=None,
) -> tuple[list[dict], dict | None]:
    """Resolve a list of ``{name?, email?}`` mentions to participants.

    Returns ``(participants, pending_person | None)``. Mentions are processed in
    order and capped at ``MAX_CHAT_PEOPLE``. Everything that resolves cleanly is
    collected into ``participants``; the FIRST bare name that is ambiguous or has
    no directory match stops processing and is returned as ``pending_person``
    (one at a time — the graph resolves it and re-invokes with the rest).

    ``llm`` is optional; when provided it is used only to pair a bare name with an
    unattributed email in the same message. ``db`` defaults to ``service_client``.
    """
    client = db if db is not None else service_client
    working = [dict(m) for m in list(mentions)[:MAX_CHAT_PEOPLE]]

    consumed_emails = _pair_names_with_loose_emails(working, message, llm)

    participants: list[dict] = []
    directory: list[dict] | None = None

    for mention in working:
        name = _clean(mention.get("name"))
        email = _clean(mention.get("email"))

        # An email-only mention that a name already claimed via LLM pairing.
        if email and not name and email in consumed_emails:
            continue

        # Steps 1 & 2: any mention carrying an email resolves through the profiles
        # lookup (explicit-email path). Miss → non-user participant.
        if email:
            participants.append(_resolve_email(email, name, "explicit_email", client))
            continue

        if not name:
            continue

        # Step 3: bare name → co-participant directory (lazily loaded once).
        if directory is None:
            directory = _coparticipant_directory(coordinator_id, client)

        status, data = _match_name(name, directory)
        if status == "match":
            participants.append(_profile_to_participant(data, "coparticipant"))
        elif status == "ambiguous":
            pending = {
                "name": name,
                "reason": "ambiguous",
                "options": [_directory_option(p) for p in data],
            }
            return participants, pending
        else:  # no_match
            return participants, {"name": name, "reason": "no_match"}

    return participants, None


def resolve_provided_email(email: str, *, name: str | None = None, db=None) -> dict:
    """Resolve a single email the user typed (the awaiting_email loop).

    Same profiles lookup as the explicit-email path, but ``source`` is
    ``'user_provided'``. Hit → in-system participant; miss → non-user participant.
    """
    client = db if db is not None else service_client
    return _resolve_email(email, name, "user_provided", client)


def resolve_provided_user_id(user_id: str, *, db=None) -> dict | None:
    """Resolve a participant the user picked from ambiguous options, by user_id.

    Returns a ``coparticipant`` participant item, or ``None`` if the id no longer
    resolves to a profile.
    """
    client = db if db is not None else service_client
    result = (
        client.table("profiles")
        .select(_PROFILE_COLUMNS)
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    profile = result.data if result else None
    if not profile:
        return None
    return _profile_to_participant(profile, "coparticipant")


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _clean(value) -> str | None:
    """Trim a mention field to a non-empty string, or None."""
    if not value:
        return None
    value = str(value).strip()
    return value or None


def _pair_names_with_loose_emails(working: list[dict], message: str, llm) -> set[str]:
    """LLM step: attach unattributed emails to bare names in the same message.

    Mutates ``working`` in place (sets ``email`` on a paired name mention) and
    returns the set of emails that were consumed so their standalone mentions are
    skipped later. No-op when there is no ``llm`` or no unattributed email.
    """
    if llm is None:
        return set()

    # An unattributed email is one whose mention carries no name of its own.
    loose_emails = [
        _clean(m.get("email"))
        for m in working
        if _clean(m.get("email")) and not _clean(m.get("name"))
    ]
    if not loose_emails:
        return set()

    consumed: set[str] = set()
    for mention in working:
        name = _clean(mention.get("name"))
        if not name or _clean(mention.get("email")):
            continue
        for email in loose_emails:
            if email in consumed:
                continue
            # Degrade, never crash: an LLM failure here must not abort the turn
            # (chat_service has already persisted the user message, so a raise
            # would leave it with no assistant reply and an unadvanced thread).
            # Skipping the pairing just falls through to the bare-name directory
            # match, which surfaces the normal ask-email prompt instead.
            try:
                with tracing.span("llm.pair_email"):
                    paired = judge_email_pairing(llm, name, email, message)
            except Exception:
                logger.exception("chat agent email-pairing LLM call failed")
                return consumed
            if paired:
                mention["email"] = email
                consumed.add(email)
                break
    return consumed


def _resolve_email(email: str, name: str | None, source: str, db) -> dict:
    """Look up an email in ``profiles``; build an in-system or non-user item."""
    normalized = normalize_email(email)
    result = (
        db.table("profiles")
        .select(_PROFILE_COLUMNS)
        .eq("email_address", normalized)
        .maybe_single()
        .execute()
    )
    profile = result.data if result else None
    if profile:
        return _profile_to_participant(profile, source)
    return {
        "full_name": name,
        "email": normalized,
        "in_system": False,
        "has_calendar": False,
        "source": source,
    }


def _profile_to_participant(profile: dict, source: str) -> dict:
    """Build an in-system participant item from a profiles row.

    ``has_calendar`` is True when the nested ``calendar_accounts(id)`` has ≥1 row.
    """
    accounts = profile.get("calendar_accounts") or []
    return {
        "user_id": profile["id"],
        "full_name": profile.get("full_name"),
        "email": profile.get("email_address"),
        "in_system": True,
        "has_calendar": len(accounts) >= 1,
        "source": source,
    }


def _coparticipant_directory(coordinator_id: str, db) -> list[dict]:
    """Return profile rows for every peer the coordinator shares an event with.

    my event ids (event_participants by coordinator) → peer user_ids across those
    events → profiles (with nested calendar_accounts) for those ids. The
    coordinator themselves is excluded.
    """
    my_events = (
        db.table("event_participants")
        .select("event_id")
        .eq("user_id", coordinator_id)
        .execute()
    )
    event_ids = [r["event_id"] for r in (my_events.data or [])]
    if not event_ids:
        return []

    peers = (
        db.table("event_participants")
        .select("user_id")
        .in_("event_id", event_ids)
        .execute()
    )
    peer_ids = [r["user_id"] for r in (peers.data or []) if r["user_id"] != coordinator_id]
    # Deduplicate while preserving order.
    peer_ids = list(dict.fromkeys(peer_ids))
    if not peer_ids:
        return []

    profiles = (
        db.table("profiles")
        .select(_PROFILE_COLUMNS)
        .in_("id", peer_ids)
        .execute()
    )
    return profiles.data or []


def _match_name(name: str, directory: list[dict]) -> tuple[str, object]:
    """Match ``name`` against directory profiles.

    Returns ``("match", profile)``, ``("ambiguous", [profiles])`` or
    ``("no_match", [])``. Exact casefolded ``full_name`` match wins; with no exact
    match, a unique first-token match ("Sarah" → "Sarah Chen" iff exactly one) is
    used. Two or more candidates at the winning stage → ambiguous.
    """
    target = name.casefold()

    exact = [p for p in directory if (p.get("full_name") or "").casefold() == target]
    if len(exact) == 1:
        return "match", exact[0]
    if len(exact) >= 2:
        return "ambiguous", exact

    first_token = [
        p for p in directory
        if (p.get("full_name") or "").split()
        and p["full_name"].split()[0].casefold() == target
    ]
    if len(first_token) == 1:
        return "match", first_token[0]
    if len(first_token) >= 2:
        return "ambiguous", first_token

    return "no_match", []


def _directory_option(profile: dict) -> dict:
    """Shape a directory profile as a pending-person option."""
    return {
        "user_id": profile["id"],
        "full_name": profile.get("full_name"),
        "email": profile.get("email_address"),
    }
