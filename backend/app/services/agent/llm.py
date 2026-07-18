"""LLM helpers for the chat agent.

MINIMAL for this package: only the ``EmailPairing`` structured-output schema and
the ``judge_email_pairing`` helper that ``people.py`` uses. The model object is
always INJECTED by the caller (a parameter implementing
``.with_structured_output(schema).invoke(...)``) — this module never imports
langchain/google libraries so it stays cheap to import and easy to test.

A later package adds ``get_chat_model()`` and the remaining structured-output
schemas here. Leave clear room for them below.
"""

from pydantic import BaseModel, Field


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


# --- Reserved for a later package -------------------------------------------
# get_chat_model() and the remaining structured-output schemas (intent
# extraction, etc.) will be added here. Keep them out of this minimal module.
