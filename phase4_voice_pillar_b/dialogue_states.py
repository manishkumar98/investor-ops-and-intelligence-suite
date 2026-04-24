"""Dialogue state types — ported from M3 phase2/src/dialogue/states.py.

DialogueState enum, DialogueContext slot-fill tracker, LLMResponse dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import pytz

IST = pytz.timezone("Asia/Kolkata")

TOPIC_LABELS: dict[str, str] = {
    "kyc_onboarding":  "KYC and Onboarding",
    "sip_mandates":    "SIP and Mandates",
    "statements_tax":  "Statements and Tax Documents",
    "withdrawals":     "Withdrawals and Timelines",
    "account_changes": "Account Changes and Nominee",
}
VALID_TOPICS: set[str] = set(TOPIC_LABELS.keys())

VALID_INTENTS: set[str] = {
    "book_new", "reschedule", "cancel", "what_to_prepare",
    "check_availability", "refuse_advice", "refuse_pii",
    "timezone_query", "out_of_scope", "end_call",
}
COMPLIANCE_FLAGS: set[str | None] = {None, "refuse_advice", "refuse_pii", "out_of_scope"}


class DialogueState(Enum):
    IDLE                      = "S0"
    GREETED                   = "S1"
    DISCLAIMER_CONFIRMED      = "S2"
    INTENT_IDENTIFIED         = "S3"
    TOPIC_COLLECTED           = "S4"
    TIME_PREFERENCE_COLLECTED = "S5"
    SLOTS_OFFERED             = "S6"
    SLOT_CONFIRMED            = "S7"
    MCP_DISPATCHED            = "S8"
    BOOKING_COMPLETE          = "S9"
    WAITLIST_OFFERED          = "S10"
    WAITLIST_CONFIRMED        = "S11"
    RESCHEDULE_CODE_COLLECTED = "S12"
    CANCEL_CODE_COLLECTED     = "S13"
    ERROR                     = "S14"
    END                       = "S15"
    CANCEL_CONFIRM            = "S16"

    def is_terminal(self) -> bool:
        return self in (DialogueState.END, DialogueState.ERROR)

    def label(self) -> str:
        return f"{self.value} {self.name}"


@dataclass
class DialogueContext:
    call_id: str
    session_start_ist: datetime
    current_state: DialogueState = DialogueState.IDLE

    intent: str | None = None
    topic: str | None = None
    day_preference: str | None = None
    time_preference: str | None = None
    resolved_slot: dict | None = None
    offered_slots: list[dict] = field(default_factory=list)
    booking_code: str | None = None
    secure_url: str | None = None
    existing_booking_code: str | None = None
    waitlist_code: str | None = None

    turn_count: int = 0
    no_input_count: int = 0
    topic_retry_count: int = 0
    code_retry_count: int = 0
    prepare_shown: bool = False

    calendar_hold_created: bool = False
    notes_appended: bool = False
    email_drafted: bool = False

    def slots_filled(self) -> dict:
        return {k: v for k, v in {
            "topic": self.topic,
            "day_preference": self.day_preference,
            "time_preference": self.time_preference,
            "existing_booking_code": self.existing_booking_code,
        }.items() if v is not None}

    def missing_booking_slots(self) -> list[str]:
        missing = []
        if not self.topic:
            missing.append("topic")
        if not self.day_preference:
            missing.append("day_preference")
        if not self.time_preference:
            missing.append("time_preference")
        return missing

    def is_booking_ready(self) -> bool:
        return (
            self.topic is not None
            and self.day_preference is not None
            and self.time_preference is not None
            and self.resolved_slot is not None
        )

    def apply_slots(self, slots: dict) -> None:
        if slots.get("topic") and slots["topic"] in VALID_TOPICS:
            self.topic = slots["topic"]
        if slots.get("day_preference"):
            self.day_preference = slots["day_preference"]
        if slots.get("time_preference"):
            self.time_preference = slots["time_preference"]
        if slots.get("existing_booking_code"):
            self.existing_booking_code = slots["existing_booking_code"]


@dataclass
class LLMResponse:
    intent: str
    slots: dict = field(default_factory=dict)
    speech: str = ""
    compliance_flag: str | None = None
    raw_response: str = ""

    def is_compliant(self) -> bool:
        return self.compliance_flag is None

    def is_refusal(self) -> bool:
        return self.compliance_flag in ("refuse_advice", "refuse_pii", "out_of_scope")

    def validate(self) -> list[str]:
        errors = []
        if self.intent not in VALID_INTENTS:
            errors.append(f"Unknown intent: '{self.intent}'")
        if self.compliance_flag not in COMPLIANCE_FLAGS:
            errors.append(f"Unknown compliance_flag: '{self.compliance_flag}'")
        if not self.speech:
            errors.append("speech must be non-empty")
        return errors
