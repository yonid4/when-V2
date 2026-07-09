"""FinalizeRequest model validation tests.

FinalizeRequest is built only by FastAPI from the request body, so these anti
fan-out guards (valid emails + a recipient cap) are enforced entirely by
Pydantic before the finalize service ever runs.
"""

import pytest
from pydantic import ValidationError

from app.models.slot import MAX_FINALIZE_RECIPIENTS, FinalizeRequest


def _base(**overrides) -> dict:
    body = {"proposed_time_id": "pt-1", "name": "Team Lunch"}
    body.update(overrides)
    return body


def test_valid_extra_emails_parse():
    req = FinalizeRequest(**_base(extra_emails=["a@example.com", "b@partner.co"]))
    assert req.extra_emails == ["a@example.com", "b@partner.co"]


def test_invalid_extra_email_rejected():
    with pytest.raises(ValidationError):
        FinalizeRequest(**_base(extra_emails=["not-an-email"]))


def test_too_many_extra_emails_rejected():
    emails = [f"user{i}@example.com" for i in range(MAX_FINALIZE_RECIPIENTS + 1)]
    with pytest.raises(ValidationError):
        FinalizeRequest(**_base(extra_emails=emails))


def test_max_extra_emails_allowed():
    emails = [f"user{i}@example.com" for i in range(MAX_FINALIZE_RECIPIENTS)]
    req = FinalizeRequest(**_base(extra_emails=emails))
    assert len(req.extra_emails) == MAX_FINALIZE_RECIPIENTS


def test_too_many_excluded_user_ids_rejected():
    ids = [f"user-{i}" for i in range(MAX_FINALIZE_RECIPIENTS + 1)]
    with pytest.raises(ValidationError):
        FinalizeRequest(**_base(excluded_user_ids=ids))
