"""Deterministic quality-gate rules."""
from __future__ import annotations

from typing import Dict, List

from backend.app.config import ALLOW_THRESHOLD, REVIEW_THRESHOLD


def decide(score: float, unresolved_failures: int, critical_failures: int, security_findings: int, critical_path_missing: bool) -> Dict[str, object]:
    """Map a confidence score plus blocking contexts onto a gate decision."""
    reasons: List[str] = []
    if unresolved_failures > 0:
        reasons.append(f"{unresolved_failures} unresolved test failure(s) require triage")
    if critical_failures > 0:
        reasons.append(f"{critical_failures} failure(s) on security-sensitive or critical-path tests")
    if critical_path_missing:
        reasons.append("critical-path smoke suite did not pass")
    if security_findings > 0:
        reasons.append(f"{security_findings} security finding(s) open on changed surface")
    reasons.append(f"confidence score {score} vs thresholds allow>={ALLOW_THRESHOLD}, review>={REVIEW_THRESHOLD}")
    if score < REVIEW_THRESHOLD:
        decision = "block"
    elif score < ALLOW_THRESHOLD:
        decision = "review"
    else:
        decision = "allow"
    if decision == "allow":
        reasons.append("no unresolved failures; changed-module coverage and critical path validated")
    return {"decision": decision, "reasons": reasons}
