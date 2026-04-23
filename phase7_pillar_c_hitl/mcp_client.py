import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MCP_STATE_PATH = Path("data/mcp_state.json")


@dataclass
class MCPResult:
    success: bool
    ref_id:  str
    mode:    str


def enqueue_action(session: dict, type: str, payload: dict, source: str) -> str:
    """Append a standardised pending action to session["mcp_queue"].

    This is the ONLY way to add items to the queue — never construct action
    dicts inline elsewhere in the codebase.
    """
    action = {
        "action_id":  str(uuid.uuid4()),
        "type":       type,       # calendar_hold | notes_append | email_draft
        "status":     "pending",
        "created_at": datetime.utcnow().isoformat(),
        "source":     source,     # m2_pipeline | m3_voice
        "payload":    payload,
    }
    if "mcp_queue" not in session:
        session["mcp_queue"] = []
    session["mcp_queue"].append(action)
    return action["action_id"]


class MCPClient:
    def __init__(self, mode: str = "mock"):
        self.mode = mode
        self._mock_store: dict = {}

    def execute(self, action: dict) -> MCPResult:
        """Execute an approved action.

        mock mode: stores in self._mock_store, no HTTP calls.
        live mode: POSTs to MCP_SERVER_URL.
        """
        if self.mode == "mock":
            ref_id = str(uuid.uuid4())
            self._mock_store[action["action_id"]] = {**action, "ref_id": ref_id}
            return MCPResult(success=True, ref_id=ref_id, mode="mock")

        # Live mode
        import httpx
        endpoint_map = {
            "calendar_hold": "calendar/hold",
            "notes_append":  "docs/append",
            "email_draft":   "gmail/draft",
        }
        base_url = os.getenv("MCP_SERVER_URL", "http://localhost:3000")
        endpoint = endpoint_map.get(action["type"], "actions")
        url = f"{base_url}/{endpoint}"

        try:
            resp = httpx.post(url, json=action["payload"], timeout=10)
            resp.raise_for_status()
            ref_id = resp.json().get("ref_id", str(uuid.uuid4()))
            return MCPResult(success=True, ref_id=ref_id, mode="live")
        except httpx.RequestError as exc:
            action["status"] = "error"
            action["error_msg"] = str(exc)
            return MCPResult(success=False, ref_id="", mode="live")

    def save_state(self, session: dict) -> None:
        MCP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        MCP_STATE_PATH.write_text(
            json.dumps(session.get("mcp_queue", []), indent=2)
        )
