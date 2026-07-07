"""Proposal notes service tests.

Verifies that ensure_proposed_time_in_event raises an explicit 404 (not a bare
Exception / 500) when the proposed_time does not belong to the given event.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.services.proposal_notes_service import ensure_proposed_time_in_event


def _make_service_client(row):
    """Build a service_client mock whose proposed_times select returns `row`."""
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=row
    )
    return db


@patch("app.services.proposal_notes_service.service_client")
def test_ensure_proposed_time_in_event_404_when_not_in_event(mock_svc):
    """No matching row -> HTTPException 404, not a bare Exception / 500."""
    mock_svc.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=None
    )

    with pytest.raises(HTTPException) as exc_info:
        ensure_proposed_time_in_event("missing-pt-id", "event-db-id-1")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@patch("app.services.proposal_notes_service.service_client")
def test_ensure_proposed_time_in_event_ok_when_in_event(mock_svc):
    """Matching row -> no exception raised."""
    mock_svc.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={"id": "pt-id-1"}
    )

    assert ensure_proposed_time_in_event("pt-id-1", "event-db-id-1") is None
