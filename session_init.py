import copy
from config import SESSION_KEYS


def init_session_state(state: dict) -> dict:
    """Idempotent: only sets keys that are not already present."""
    for key, default in SESSION_KEYS.items():
        if key not in state:
            state[key] = copy.deepcopy(default)
    return state
