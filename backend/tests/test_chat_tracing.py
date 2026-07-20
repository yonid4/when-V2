"""Chat agent — per-turn latency tracing (agent_service/tracing.py).

The trace is diagnostic-only, so the invariants that matter are: it never
changes behavior (values pass through, exceptions propagate), it is inert when
no turn is open, and it still reports when the turn fails.
"""

import logging

import pytest

from agent_service import tracing


def test_span_outside_a_turn_is_inert():
    """No open trace → span is a pass-through and records nothing."""
    with tracing.span('orphan'):
        pass
    assert tracing._spans.get() is None


def test_turn_trace_records_spans_in_execution_order():
    with tracing.turn_trace(thread='t1') as spans:
        with tracing.span('first'):
            pass
        with tracing.span('second'):
            pass

    assert [s['name'] for s in spans] == ['first', 'second']
    assert all(s['depth'] == 0 for s in spans)
    assert all(s['ms'] >= 0 for s in spans)


def test_nested_spans_record_depth():
    """A child span opened inside a parent is recorded one level deeper."""
    with tracing.turn_trace(thread='t1') as spans:
        with tracing.span('compute_slots'):
            with tracing.span('busy_sync'):
                pass

    assert [(s['name'], s['depth']) for s in spans] == [
        ('compute_slots', 0), ('busy_sync', 1),
    ]
    # Parent is recorded at span START, so it precedes the child it contains.
    assert spans[0]['ms'] >= spans[1]['ms']


def test_span_propagates_exceptions_and_still_records():
    """Tracing never swallows: the error escapes, the timing is still captured."""
    with pytest.raises(RuntimeError):
        with tracing.turn_trace(thread='t1') as spans:
            with tracing.span('boom'):
                raise RuntimeError('kaboom')

    assert [s['name'] for s in spans] == ['boom']


def test_turn_trace_logs_summary_on_failure(caplog):
    """A turn that raises still emits its breakdown before propagating."""
    with caplog.at_level(logging.INFO, logger='agent_service.tracing'):
        with pytest.raises(RuntimeError):
            with tracing.turn_trace(thread='t-abc'):
                with tracing.span('graph.invoke'):
                    raise RuntimeError('kaboom')

    assert 'thread=t-abc' in caplog.text
    assert 'graph.invoke' in caplog.text


def test_slow_turn_logs_at_warning(caplog, monkeypatch):
    """Turns over the slow threshold escalate so they surface at WARNING."""
    monkeypatch.setattr(tracing, 'SLOW_TURN_MS', 0.0)
    with caplog.at_level(logging.INFO, logger='agent_service.tracing'):
        with tracing.turn_trace(thread='t1'):
            pass

    assert [r.levelno for r in caplog.records] == [logging.WARNING]


def test_context_is_reset_after_a_turn():
    """The recorder must not leak past the turn that opened it."""
    with tracing.turn_trace(thread='t1'):
        assert tracing._spans.get() is not None
    assert tracing._spans.get() is None
    assert tracing._depth.get() == 0


def test_format_spans_renders_nesting():
    spans = [
        {'name': 'compute_slots', 'depth': 0, 'ms': 2298.4},
        {'name': 'busy_sync', 'depth': 1, 'ms': 2251.1},
    ]
    assert tracing.format_spans(spans) == 'compute_slots=2298ms, >busy_sync=2251ms'
