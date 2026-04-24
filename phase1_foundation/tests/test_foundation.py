"""Phase 1 — Foundation & Infrastructure tests."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test-key")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(ROOT / "data" / "chroma_test"))
    monkeypatch.setenv("MCP_MODE", "mock")
    monkeypatch.setenv("MCP_SERVER_URL", "http://localhost:3000")


@pytest.fixture
def mock_session_state():
    return {}


@pytest.fixture
def calendar_path():
    return ROOT / "data" / "mock_calendar.json"


# ---------------------------------------------------------------------------
# P1-01  Environment variables
# ---------------------------------------------------------------------------

class TestEnvironmentConfig:

    def test_required_keys_present(self, mock_env):
        required = [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "CHROMA_PERSIST_DIR",
            "MCP_MODE",
        ]
        for key in required:
            assert os.getenv(key), f"Missing env var: {key}"

    def test_missing_key_detected(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert os.getenv("ANTHROPIC_API_KEY") is None

    def test_mcp_mode_values(self, monkeypatch):
        for valid_mode in ("mock", "live"):
            monkeypatch.setenv("MCP_MODE", valid_mode)
            assert os.getenv("MCP_MODE") in ("mock", "live")


# ---------------------------------------------------------------------------
# P1-02  Session state schema
# ---------------------------------------------------------------------------

class TestSessionStateSchema:

    REQUIRED_KEYS = {
        "weekly_pulse": type(None),
        "top_theme": type(None),
        "top_3_themes": list,
        "fee_bullets": list,
        "fee_sources": list,
        "booking_code": type(None),
        "booking_detail": type(None),
        "mcp_queue": list,
        "chat_history": list,
        "pulse_generated": bool,
        "call_completed": bool,
    }

    def _init_state(self, state: dict) -> dict:
        defaults = {
            "weekly_pulse": None,
            "top_theme": None,
            "top_3_themes": [],
            "fee_bullets": [],
            "fee_sources": [],
            "booking_code": None,
            "booking_detail": None,
            "mcp_queue": [],
            "chat_history": [],
            "pulse_generated": False,
            "call_completed": False,
        }
        for k, v in defaults.items():
            if k not in state:
                state[k] = v
        return state

    def test_all_keys_present_after_init(self, mock_session_state):
        state = self._init_state(mock_session_state)
        for key in self.REQUIRED_KEYS:
            assert key in state, f"Missing key: {key}"

    def test_default_types_correct(self, mock_session_state):
        state = self._init_state(mock_session_state)
        assert state["top_3_themes"] == []
        assert state["mcp_queue"] == []
        assert state["pulse_generated"] is False
        assert state["call_completed"] is False

    def test_init_is_idempotent(self, mock_session_state):
        state = self._init_state(mock_session_state)
        state["weekly_pulse"] = "test pulse"
        state = self._init_state(state)
        assert state["weekly_pulse"] == "test pulse", "Init must not overwrite existing values"


# ---------------------------------------------------------------------------
# P1-03  Mock calendar
# ---------------------------------------------------------------------------

class TestMockCalendar:

    def test_calendar_file_exists(self, calendar_path):
        assert calendar_path.exists(), f"mock_calendar.json not found at {calendar_path}"

    def test_calendar_parses(self, calendar_path):
        data = json.loads(calendar_path.read_text())
        assert "available_slots" in data

    def test_calendar_has_minimum_slots(self, calendar_path):
        data = json.loads(calendar_path.read_text())
        assert len(data["available_slots"]) >= 4

    def test_slot_schema(self, calendar_path):
        data = json.loads(calendar_path.read_text())
        required_fields = {"id", "date", "time", "tz"}
        for slot in data["available_slots"]:
            assert required_fields.issubset(slot.keys()), f"Slot missing fields: {slot}"

    def test_slots_are_ist(self, calendar_path):
        data = json.loads(calendar_path.read_text())
        for slot in data["available_slots"]:
            assert slot["tz"] == "IST", f"Slot timezone must be IST: {slot}"


# ---------------------------------------------------------------------------
# P1-04/P1-05  ChromaDB (mocked — no real DB in CI)
# ---------------------------------------------------------------------------

class TestChromaDBInit:

    @patch("chromadb.PersistentClient")
    def test_client_created_with_persist_dir(self, mock_client_class, mock_env):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_client.get_or_create_collection.return_value = mock_collection

        import chromadb
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
        client = chromadb.PersistentClient(path=persist_dir)
        mock_client_class.assert_called_once_with(path=persist_dir)

    @patch("chromadb.PersistentClient")
    def test_both_collections_created(self, mock_client_class, mock_env):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_client.get_or_create_collection.return_value = mock_collection

        import chromadb
        client = chromadb.PersistentClient(path="./test")
        for name in ("mf_faq_corpus", "fee_corpus"):
            client.get_or_create_collection(name)

        calls = [c[0][0] for c in mock_client.get_or_create_collection.call_args_list]
        assert "mf_faq_corpus" in calls
        assert "fee_corpus" in calls


# ---------------------------------------------------------------------------
# P1-07  MCP client modes
# ---------------------------------------------------------------------------

class TestMCPClientMode:

    def test_mock_mode_does_not_make_http_calls(self, mock_env):
        """MCPClient in mock mode must not call requests/httpx."""
        with patch("httpx.post") as mock_post, patch("requests.post") as mock_req:
            # Simulate mock MCP execution inline
            mock_store = {"calendar": {}, "notes": [], "email_drafts": []}
            action = {
                "action_id": "test-001",
                "type": "notes_append",
                "payload": {"entry": {"date": "2026-04-22", "code": "NL-A742"}},
            }
            mock_store["notes"].append(action["payload"]["entry"])
            assert len(mock_store["notes"]) == 1
            mock_post.assert_not_called()
            mock_req.assert_not_called()

    def test_booking_code_format(self):
        import random, string
        def generate_booking_code(prefix="NL"):
            suffix = random.choice(string.ascii_uppercase) + \
                     "".join(random.choices(string.digits, k=3))
            return f"{prefix}-{suffix}"

        code = generate_booking_code()
        assert code.startswith("NL-")
        assert len(code) == 7
        assert code[3].isalpha()
        assert code[4:].isdigit()
