"""Flaky-test signal detection and outcome classification."""
from __future__ import annotations

from typing import Dict, Optional

ENVIRONMENT_KEYWORDS = ("timed out", "timeout", "connection", "cluster", "handshake", "network")
AUTOMATION_KEYWORDS = ("fixture", "harness", "selector", "payload missing", "keyerror")


def detect_alternation(history: list[str], window: int = 6, min_flips: int = 3) -> bool:
    """True when recent outcomes flip pass/fail repeatedly."""
    recent = [o for o in (history or [])[-window:] if o in ("pass", "fail")]
    flips = sum(1 for a, b in zip(recent, recent[1:]) if a != b)
    return flips >= min_flips


def classify(
    first_outcome: str,
    final_outcome: str,
    history: list[str],
    message: str = "",
    retried: bool = False,
) -> Dict[str, object]:
    """Classify a suspicious outcome into product_defect|automation_defect|environment|flaky_test|unknown."""
    lowered = (message or "").lower()
    signals: Dict[str, object] = {
        "first_outcome": first_outcome,
        "final_outcome": final_outcome,
        "retried": retried,
        "alternating_history": detect_alternation(history),
    }
    classification: Optional[str] = None
    confidence = 0.4
    if retried and final_outcome == "passed":
        classification = "flaky_test"
        confidence = 0.92
    elif signals["alternating_history"] and final_outcome == "failed":
        classification = "flaky_test"
        confidence = 0.85
    elif any(k in lowered for k in ENVIRONMENT_KEYWORDS):
        classification = "environment"
        confidence = 0.75
    elif any(k in lowered for k in AUTOMATION_KEYWORDS):
        classification = "automation_defect"
        confidence = 0.7
    elif first_outcome == "failed" and final_outcome == "failed":
        classification = "product_defect"
        confidence = 0.82
    return {
        "classification": classification or "unknown",
        "confidence": confidence,
        "signals": signals,
    }
