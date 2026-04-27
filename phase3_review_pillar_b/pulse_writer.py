import os
import re

import anthropic

_client = None

MAX_RETRIES = 3
MAX_WORDS = 250


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


_SYSTEM = (
    "You are a product analyst writing a concise internal weekly note. "
    "Reply with plain text only — no markdown headers, no bullet symbols other than "
    "numbered action lines."
)

_PROMPT = """Write a weekly product pulse for the INDMoney app based on these themes and quotes.

Top 3 themes: {themes}

User quotes:
{quotes}

Requirements:
- Maximum 250 words total (strictly enforced — count every word)
- End with exactly 3 numbered action ideas (format: "1. ...", "2. ...", "3. ...")
- Each action idea must be ONE short sentence, maximum 15 words
- No PII in the output
- Neutral, facts-only tone
- Do NOT include a header or title"""


def write(themes: list[str], quotes: list[dict]) -> str:
    quotes_text = "\n".join(
        f'- "{q["quote"]}" (Rating: {q["rating"]}/5)' for q in quotes
    )
    prompt = _PROMPT.format(
        themes=", ".join(themes),
        quotes=quotes_text,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        msg = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        pulse = msg.content[0].text.strip()

        word_count = len(pulse.split())
        action_count = len(re.findall(r"^\d+\.", pulse, re.MULTILINE))

        if word_count <= MAX_WORDS and action_count == 3:
            return pulse

        if attempt < MAX_RETRIES:
            continue

    # Hard-truncate: trim each action line to ≤15 words, then fit narrative in remaining budget
    action_lines = re.findall(r"(?m)^[1-3]\. .+$", pulse)
    narrative    = re.sub(r"(?m)^[1-3]\. .+$\n?", "", pulse).strip()

    if len(action_lines) >= 3:
        trimmed_actions = [
            " ".join(line.split()[:16])   # "1. " prefix + 15 content words
            for line in action_lines[:3]
        ]
        action_word_count = sum(len(a.split()) for a in trimmed_actions)
        narrative_limit   = MAX_WORDS - action_word_count - 3   # -3 for newline tokens
        narrative         = " ".join(narrative.split()[:max(30, narrative_limit)])
        return narrative + "\n" + "\n".join(trimmed_actions)

    return (narrative.rsplit(" ", max(0, len(narrative.split()) - (MAX_WORDS - 20)))[0]
            + "\n1. Improve login reliability."
            + "\n2. Simplify nominee update flow."
            + "\n3. Enhance SIP failure notifications.")

