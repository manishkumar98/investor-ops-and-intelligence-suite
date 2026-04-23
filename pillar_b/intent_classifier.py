import os
import anthropic

INTENTS = {
    "book_new":      ["book", "schedule", "appointment", "want a call", "meet", "new booking"],
    "reschedule":    ["reschedule", "change time", "move", "shift"],
    "cancel":        ["cancel", "abort", "don't need", "remove booking"],
    "what_to_prepare": ["prepare", "bring", "documents needed", "what should i"],
    "check_availability": ["available", "availability", "when can", "open slots", "free slots"],
}

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def classify(utterance: str) -> str:
    """Return one of the 5 intent strings. Keyword-first, LLM fallback."""
    lower = utterance.lower()

    for intent, keywords in INTENTS.items():
        if any(kw in lower for kw in keywords):
            return intent

    # LLM fallback
    prompt = (
        f"Classify this user utterance into exactly one of these intents:\n"
        f"{list(INTENTS.keys())}\n\n"
        f"Utterance: {utterance}\n\n"
        f"Reply with only the intent name, nothing else."
    )
    msg = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}],
    )
    result = msg.content[0].text.strip().lower()

    for intent in INTENTS:
        if intent in result:
            return intent

    return "book_new"
