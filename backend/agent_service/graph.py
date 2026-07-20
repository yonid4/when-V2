"""The chat agent graph (Package 5).

A LangGraph ``StateGraph(AgentState)`` whose routing is 100% deterministic Python.
The injected ``llm`` reaches only ONE node — ``classify_and_extract``, the single
intent/field-extraction call (which also attributes emails to the people it
lists) — via a node factory that closes over it; every other node, including
``resolve_people`` and the terminal ``compose_reply`` (deterministic reply
templates), is pure deterministic logic and every conditional edge is a trivial
``state['route']`` lookup.

The entry router is the single security boundary for write paths: an event is
only ever created / finalized / edited when the router dispatches a STRUCTURED
action (``confirm_draft`` / ``book_direct`` / ``use_in_app`` / ``cancel``) from a
recognized waiting state. Free text can never reach ``book_direct_node`` /
``create_in_app_node`` / ``apply_edit_node`` — it always routes to
``classify_and_extract`` first.

``chat_service`` depends only on ``get_compiled_graph`` (module-cached) and
``build_graph`` (for tests, which inject a fake LLM). Both names are kept stable
because ``chat_service`` imports this module and the test-suite patches
``get_compiled_graph`` at this import site.
"""

import re

from langgraph.graph import END, START, StateGraph

from agent_service import editing
from agent_service import llm as llm_mod
from agent_service import nodes, tracing
from agent_service.state import AgentState

_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')


def _traced(name: str, fn):
    """Wrap a node so its wall-clock time lands in the active turn trace.

    Purely diagnostic: the wrapper forwards ``state`` through and returns the
    node's partial update untouched. A single ``state`` parameter is declared so
    LangGraph's signature inspection sees the same shape as the bare node.
    """

    def traced_node(state):
        with tracing.span(name):
            return fn(state)

    traced_node.__name__ = name
    return traced_node


# ─── Entry rehydration router (conditional edge from START) ───────────────────

def entry_router(state: AgentState) -> str:
    """Deterministic dispatch on ``(status, workflow, action)``.

    Structured actions in a matching waiting state go straight to their handler;
    everything else — free-text revisions in any state, plus ``idle`` /
    ``collecting`` — goes to ``classify_and_extract``. This is what guarantees the
    write nodes are unreachable from free text.
    """
    action = state.get('action') or {}
    atype = action.get('type')
    status = state.get('status')
    workflow = state.get('workflow')

    if atype == 'cancel':
        return 'cancel_node'

    if status == 'awaiting_email':
        if atype in ('provide_email', 'pick_person'):
            return 'apply_email'
        if not atype and _EMAIL_RE.search(state.get('user_message') or ''):
            return 'apply_email'

    if status == 'awaiting_choice':
        if atype == 'book_direct':
            return 'compute_slots'
        if atype == 'use_in_app':
            return 'prepare_confirmation'

    if status == 'awaiting_confirmation' and atype == 'confirm_draft':
        if workflow == 'edit_event':
            return 'apply_edit_node'
        if state.get('booking_mode') == 'direct':
            return 'book_direct_node'
        return 'create_in_app_node'

    return 'classify_and_extract'


def _by_route(state: AgentState) -> str:
    """Shared router for internal conditional edges (node sets ``route``)."""
    return state['route']


# ─── Graph construction ───────────────────────────────────────────────────────

def build_graph(llm):
    """Compile the agent graph with ``llm`` injected into the LLM nodes.

    ``llm`` must implement ``.with_structured_output(schema).invoke(prompt)`` (for
    classification/extraction and name↔email pairing). Tests pass a fake.
    """
    g = StateGraph(AgentState)

    # Every node is registered through _traced so a turn trace gets a per-node
    # breakdown; the wrapper is a pass-through when no trace is open.
    def add(name: str, fn):
        g.add_node(name, _traced(name, fn))

    # LLM-backed node (closure over the injected model). The single LLM call.
    add('classify_and_extract', nodes.make_classify_and_extract(llm))

    # Deterministic nodes.
    add('resolve_people', nodes.resolve_people)
    add('compose_reply', nodes.compose_reply)
    add('validate_intent', nodes.validate_intent)
    add('validate_edit', editing.validate_edit)
    add('ask_email', nodes.ask_email)
    add('apply_email', nodes.apply_email)
    add('prepare_choice', nodes.prepare_choice)
    add('compute_slots', nodes.compute_slots)
    add('prepare_confirmation', nodes.prepare_confirmation)
    add('book_direct_node', nodes.book_direct_node)
    add('create_in_app_node', nodes.create_in_app_node)
    add('apply_edit_node', editing.apply_edit_node)
    add('cancel_node', nodes.cancel_node)

    # Entry dispatch.
    g.add_conditional_edges(START, entry_router, [
        'cancel_node', 'apply_email', 'compute_slots', 'prepare_confirmation',
        'book_direct_node', 'create_in_app_node', 'apply_edit_node', 'classify_and_extract',
    ])

    # Internal branches (each source node sets state['route']).
    g.add_conditional_edges('classify_and_extract', _by_route,
                            ['validate_intent', 'validate_edit', 'compose_reply'])
    g.add_conditional_edges('validate_intent', _by_route, ['resolve_people', 'compose_reply'])
    g.add_conditional_edges('validate_edit', _by_route, ['prepare_confirmation', 'compose_reply'])
    g.add_conditional_edges('resolve_people', _by_route, ['ask_email', 'prepare_choice'])
    g.add_conditional_edges('apply_email', _by_route, ['resolve_people', 'compose_reply'])
    g.add_conditional_edges('prepare_choice', _by_route, ['prepare_confirmation', 'compose_reply'])
    g.add_conditional_edges('compute_slots', _by_route, ['prepare_confirmation', 'compose_reply'])

    # Terminal fan-in: every business branch composes a reply, then ends.
    g.add_edge('ask_email', 'compose_reply')
    g.add_edge('prepare_confirmation', 'compose_reply')
    g.add_edge('book_direct_node', 'compose_reply')
    g.add_edge('create_in_app_node', 'compose_reply')
    g.add_edge('apply_edit_node', 'compose_reply')
    g.add_edge('cancel_node', 'compose_reply')
    g.add_edge('compose_reply', END)

    return g.compile()


# ─── Module-cached compiled graph ─────────────────────────────────────────────

_compiled = None


def get_compiled_graph():
    """Return the process-wide compiled graph, building it once with the real
    Gemini model. ``chat_service`` calls this per turn; the tests patch it."""
    global _compiled
    if _compiled is None:
        _compiled = build_graph(llm_mod.get_chat_model())
    return _compiled
