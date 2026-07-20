"""Per-turn latency tracing for the chat agent (diagnostic only).

Answers "where did this turn's seconds actually go?" without guessing: a turn
opens one :func:`turn_trace`, every interesting operation inside it opens a
:func:`span`, and on exit a single structured line is logged with the ordered,
nested breakdown::

    chat.turn thread=abc123 total=3204ms [classify_and_extract=812ms,
      llm.extract=806ms, compute_slots=2298ms, busy_sync=2251ms, rank_slots=41ms]

Design notes:

* **Zero behavior change.** Spans only measure; they never swallow exceptions,
  alter return values, or change control flow.
* **Off by default outside a turn.** ``span`` is a no-op when no ``turn_trace``
  is open (so unit tests and non-chat callers pay nothing), which is why the
  recorder is a ``ContextVar`` rather than a module global — concurrent
  requests each get their own list, and nothing leaks between them.
* **Slow turns escalate.** A turn over :data:`SLOW_TURN_MS` logs at WARNING so
  it surfaces even under a default (WARNING-level) logging config.

Timings come from ``time.perf_counter`` (monotonic); they measure wall-clock
elapsed time, which is what matters for a blocking call to Gemini or a calendar
provider.
"""

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# A turn slower than this logs at WARNING instead of INFO.
SLOW_TURN_MS = 3000.0

# Recorder for the turn in flight; ``None`` means "no trace open" → spans no-op.
_spans: ContextVar[list[dict] | None] = ContextVar("chat_trace_spans", default=None)
_depth: ContextVar[int] = ContextVar("chat_trace_depth", default=0)


@contextmanager
def span(name: str):
    """Time a named operation, recording it into the active turn trace.

    A no-op (beyond the yield) when no :func:`turn_trace` is open. Entries are
    appended at span START so the rendered breakdown reads in execution order
    with children nested under their parent.
    """
    spans = _spans.get()
    if spans is None:
        yield
        return

    depth = _depth.get()
    entry = {"name": name, "depth": depth, "ms": 0.0}
    spans.append(entry)
    token = _depth.set(depth + 1)
    start = time.perf_counter()
    try:
        yield
    finally:
        _depth.reset(token)
        entry["ms"] = (time.perf_counter() - start) * 1000


@contextmanager
def turn_trace(**context):
    """Open a per-turn trace; emit one structured summary line on exit.

    ``context`` is rendered as ``key=value`` pairs on the log line (e.g.
    ``thread=<id>``). The line is emitted even when the turn raises, so a failed
    turn still reports where its time went before it died.
    """
    spans: list[dict] = []
    token = _spans.set(spans)
    depth_token = _depth.set(0)
    start = time.perf_counter()
    try:
        yield spans
    finally:
        _spans.reset(token)
        _depth.reset(depth_token)
        total_ms = (time.perf_counter() - start) * 1000
        logger.log(
            logging.WARNING if total_ms >= SLOW_TURN_MS else logging.INFO,
            "chat.turn %s total=%.0fms [%s]",
            " ".join(f"{k}={v}" for k, v in context.items()),
            total_ms,
            format_spans(spans),
        )


def format_spans(spans: list[dict]) -> str:
    """Render recorded spans as a flat, greppable, indentation-nested string."""
    return ", ".join(
        f"{'>' * s['depth']}{s['name']}={s['ms']:.0f}ms" for s in spans
    )
