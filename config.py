import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent


def load_env() -> None:
    load_dotenv(ROOT / ".env")
    missing = [k for k in ("ANTHROPIC_API_KEY",) if not os.getenv(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in the values."
        )
    mcp_mode = os.getenv("MCP_MODE", "mock")
    if mcp_mode not in {"mock", "live"}:
        import warnings
        warnings.warn(f"MCP_MODE='{mcp_mode}' is invalid — defaulting to 'mock'")
        os.environ["MCP_MODE"] = "mock"


# Canonical default values for all session keys.
# Import this dict wherever you need key names — never use string literals.
SESSION_KEYS: dict = {
    "chat_history":    [],         # list of {content, response}
    "mcp_queue":       [],         # list of MCP action dicts
    "weekly_pulse":    None,       # str — ≤250 word pulse
    "top_theme":       None,       # str — top theme from M2
    "top_3_themes":    [],         # list of str
    "fee_bullets":     [],         # list of str
    "fee_sources":     [],         # list of str
    "pulse_generated": False,      # bool — gates "Start Call" button
    "booking_code":    None,       # str — NL-A742 format
    "booking_detail":  None,       # dict — topic, slot, date, time, tz
    "call_completed":  False,      # bool — set on BOOKED state
}

# Convenience exports
CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", str(ROOT / "data" / "chroma"))
MCP_MODE: str           = os.getenv("MCP_MODE", "mock")
MCP_SERVER_URL: str     = os.getenv("MCP_SERVER_URL", "http://localhost:3000")
PRODUCT_NAME: str       = os.getenv("PRODUCT_NAME", "INDMoney Advisor Suite")
SECURE_BASE_URL: str    = os.getenv("SECURE_BASE_URL", "https://app.example.com")
ROUTER_MODE: str        = os.getenv("ROUTER_MODE", "keyword")
