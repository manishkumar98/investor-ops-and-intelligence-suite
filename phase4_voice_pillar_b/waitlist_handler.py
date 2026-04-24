"""Waitlist entry management — ported from M3 phase1/src/booking/waitlist_handler.py."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pytz

from .booking_engine import generate_waitlist_code

IST = pytz.timezone("Asia/Kolkata")
VALID_STATUSES = {"ACTIVE", "FULFILLED", "EXPIRED", "CANCELLED"}


@dataclass
class WaitlistEntry:
    waitlist_code: str
    topic: str
    day_preference: str
    time_preference: str
    created_at: datetime
    status: str = "ACTIVE"
    email: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "waitlist_code":   self.waitlist_code,
            "topic":           self.topic,
            "day_preference":  self.day_preference,
            "time_preference": self.time_preference,
            "created_at":      self.created_at.isoformat(),
            "status":          self.status,
            "email":           self.email,
            "name":            self.name,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WaitlistEntry":
        created = datetime.fromisoformat(d["created_at"])
        if created.tzinfo is None:
            created = IST.localize(created)
        return cls(
            waitlist_code=d["waitlist_code"],
            topic=d["topic"],
            day_preference=d["day_preference"],
            time_preference=d["time_preference"],
            created_at=created,
            status=d.get("status", "ACTIVE"),
            email=d.get("email"),
            name=d.get("name"),
        )

    def summary(self) -> str:
        return (
            f"Waitlist {self.waitlist_code}: {self.topic} — "
            f"{self.day_preference} {self.time_preference} (status: {self.status})"
        )


def create_waitlist_entry(
    topic: str,
    day_preference: str,
    time_preference: str,
    existing_codes: set[str] | None = None,
    reference_time: datetime | None = None,
) -> WaitlistEntry:
    if not topic or not topic.strip():
        raise ValueError("topic must be non-empty")
    if not day_preference or not day_preference.strip():
        raise ValueError("day_preference must be non-empty")
    if not time_preference or not time_preference.strip():
        raise ValueError("time_preference must be non-empty")

    code = generate_waitlist_code(existing_codes or set())

    if reference_time is None:
        reference_time = datetime.now(IST)
    elif reference_time.tzinfo is None:
        reference_time = IST.localize(reference_time)

    return WaitlistEntry(
        waitlist_code=code,
        topic=topic,
        day_preference=day_preference,
        time_preference=time_preference,
        created_at=reference_time,
        status="ACTIVE",
    )
