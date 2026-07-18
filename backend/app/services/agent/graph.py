"""Compiled-graph accessor. STUB — replaced by the real LangGraph build in the
agent package. chat_service depends only on this interface."""


def build_graph(llm):  # returns object with .invoke(state: dict) -> dict
    raise NotImplementedError("agent graph not yet wired")


def get_compiled_graph():  # module-cached in the real impl
    raise NotImplementedError("agent graph not yet wired")
