from .safety_filter import is_safe
from .query_router import route
from .retriever import retrieve
from .llm_fusion import fuse, FaqResponse


def query(user_input: str, session: dict) -> FaqResponse:
    """Full FAQ pipeline: safety → route → retrieve → fuse.

    Appends the exchange to session["chat_history"] and returns FaqResponse.
    """
    # Safety gate — runs before any LLM call
    safe, refusal_msg = is_safe(user_input)
    if not safe:
        from .llm_fusion import FaqResponse
        from datetime import date
        response = FaqResponse(
            refused=True,
            refusal_msg=refusal_msg,
            last_updated=str(date.today()),
        )
        _append_history(session, user_input, response)
        return response

    # Route
    query_type = route(user_input)

    # Retrieve
    chunks = retrieve(user_input, query_type)

    # Fuse
    response = fuse(user_input, chunks, query_type)

    _append_history(session, user_input, response)
    return response


def _append_history(session: dict, content: str, response: FaqResponse) -> None:
    if "chat_history" not in session:
        session["chat_history"] = []
    session["chat_history"].append({"content": content, "response": response})
