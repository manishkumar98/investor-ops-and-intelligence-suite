"""Post-LLM compliance checker — ported from M3 phase2/src/dialogue/compliance_guard.py.

Scans the agent's output text BEFORE it is shown/spoken.
If a violation is found, returns a safe refusal response instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_ADVICE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(should|must|recommend|advise)\s+(you\s+)?(buy|sell|invest|hold|exit|redeem)", re.I),
    re.compile(r"\b(good|great|best|better|top)\s+(investment|fund|stock|option|choice|pick)\b", re.I),
    re.compile(r"\bexpected\s+returns?\b", re.I),
    re.compile(r"\b\d+(\.\d+)?\s*%\s+(return|gain|growth|yield|interest)\b", re.I),
    re.compile(r"\b(market|stocks?|equit(y|ies)|mutual\s+fund|nifty|sensex)\s+(will|is\s+going\s+to|might)\b", re.I),
    re.compile(r"\b(outperform|underperform|alpha|beta|sharpe)\b", re.I),
    re.compile(r"\b(diversif(y|ication)|rebalance|asset\s+allocation)\b", re.I),
]

_PII_LEAK_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b[6-9]\d{8,9}\b"),
    re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.I),
    re.compile(r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)"),
]

_SAFE_ADVICE = (
    "I'm not able to provide investment advice. "
    "I can help you book a consultation with an advisor. "
    "Would you like to schedule one?"
)
_SAFE_PII = (
    "Please don't share personal details on this call. "
    "You'll receive a secure link after booking to submit your contact information."
)
_SAFE_SCOPE = "I'm only able to help with advisor appointment scheduling today."


@dataclass
class ComplianceResult:
    is_compliant: bool
    flag: str | None
    safe_speech: str
    reason: str = ""

    def effective_speech(self, original: str) -> str:
        return original if self.is_compliant else self.safe_speech


class ComplianceGuard:
    """Scans LLM output for investment advice, PII leakage, and out-of-scope content."""

    def check(self, llm_output: str) -> ComplianceResult:
        if not llm_output or not llm_output.strip():
            return ComplianceResult(is_compliant=True, flag=None, safe_speech="")

        for pattern in _ADVICE_PATTERNS:
            m = pattern.search(llm_output)
            if m:
                return ComplianceResult(
                    is_compliant=False, flag="refuse_advice", safe_speech=_SAFE_ADVICE,
                    reason=f"Investment advice detected: '{m.group(0)}'",
                )

        for pattern in _PII_LEAK_PATTERNS:
            m = pattern.search(llm_output)
            if m:
                return ComplianceResult(
                    is_compliant=False, flag="refuse_pii", safe_speech=_SAFE_PII,
                    reason=f"PII leak detected: '{m.group(0)[:20]}'",
                )

        return ComplianceResult(is_compliant=True, flag=None, safe_speech=llm_output)

    def check_and_gate(self, llm_output: str) -> str:
        result = self.check(llm_output)
        return result.effective_speech(llm_output)
