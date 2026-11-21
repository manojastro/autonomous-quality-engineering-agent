"""Deterministic release-confidence scoring."""
from __future__ import annotations

from typing import Dict, Tuple

from backend.app.config import CONFIDENCE_WEIGHTS


def compute_confidence(
    passed_ratio: float,
    coverage_ratio: float,
    critical_path_validated: bool,
    unresolved_failures: int,
    flakiness_penalty_factor: float,
    security_penalty_factor: float,
) -> Tuple[float, Dict[str, float]]:
    """Weighted deduction model: baseline trust 100 minus weight x (1 - attainment).

    Any unresolved failure saturates its full 25-point penalty because a single
    unexplained production-boundary failure disqualifies autonomous approval.
    """
    w = CONFIDENCE_WEIGHTS
    pr = min(max(passed_ratio, 0.0), 1.0)
    cov = min(max(coverage_ratio, 0.0), 1.0)
    crit_deduction = 0.0 if critical_path_validated else w["critical_path_validation"]
    unresolved_deduction = w["unresolved_failures_penalty"] if unresolved_failures > 0 else 0.0
    flakiness_deduction = w["flakiness_penalty"] * min(max(flakiness_penalty_factor, 0.0), 1.0)
    security_deduction = w["security_findings_penalty"] * min(max(security_penalty_factor, 0.0), 1.0)
    raw = (
        100.0
        - w["passed_results"] * (1.0 - pr)
        - w["changed_module_coverage"] * (1.0 - cov)
        - crit_deduction
        - unresolved_deduction
        - flakiness_deduction
        - security_deduction
    )
    score = round(min(max(raw, 0.0), 100.0), 1)
    breakdown: Dict[str, float] = {
        "passed_results_ratio": round(pr, 4),
        "changed_module_coverage": round(cov, 4),
        "critical_path_validated": 1.0 if critical_path_validated else 0.0,
        "unresolved_failures": float(unresolved_failures),
        "deduction_failed_results": round(w["passed_results"] * (1.0 - pr), 2),
        "deduction_coverage_gap": round(w["changed_module_coverage"] * (1.0 - cov), 2),
        "deduction_critical_path": round(crit_deduction, 2),
        "deduction_unresolved_failures": round(unresolved_deduction, 2),
        "deduction_flakiness": round(flakiness_deduction, 2),
        "deduction_security": round(security_deduction, 2),
        "total": score,
    }
    return score, breakdown
