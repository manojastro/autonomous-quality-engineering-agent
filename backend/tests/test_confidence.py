"""Deterministic confidence scoring vectors."""
import math

from backend.app.config import CONFIDENCE_WEIGHTS
from backend.app.services.confidence_math import compute_confidence


def test_perfect_run_scores_100() -> None:
    score, breakdown = compute_confidence(1.0, 1.0, True, 0, 0.0, 0.0)
    assert score == 100.0
    assert all(v == 0 for k, v in breakdown.items() if k.startswith("deduction_"))
    assert breakdown["total"] == 100.0


def test_bug_scenario_block_vector() -> None:
    score, _ = compute_confidence(passed_ratio=8 / 18, coverage_ratio=1.0, critical_path_validated=True, unresolved_failures=9, flakiness_penalty_factor=0.0, security_penalty_factor=0.0)
    expected = round(100 - CONFIDENCE_WEIGHTS["passed_results"] * (10 / 18) - CONFIDENCE_WEIGHTS["unresolved_failures_penalty"], 1)
    assert score == expected
    assert score < 60.0


def test_single_unresolved_failure_lands_in_review() -> None:
    score, _ = compute_confidence(0.9, 1.0, True, 1, 0.0, 0.0)
    assert score == 71.5
    assert 60.0 <= score < 85.0


def test_rescued_flake_costs_quarter_of_flaky_weight() -> None:
    base, _ = compute_confidence(1.0, 1.0, True, 0, 0.0, 0.0)
    rescued, _ = compute_confidence(1.0, 1.0, True, 0, 0.25, 0.0)
    assert math.isclose(base - rescued, CONFIDENCE_WEIGHTS["flakiness_penalty"] * 0.25)


def test_missing_critical_path_deducts_full_weight() -> None:
    score, _ = compute_confidence(1.0, 1.0, False, 0, 0.0, 0.0)
    assert score == 100.0 - CONFIDENCE_WEIGHTS["critical_path_validation"]


def test_security_penalty_scales_and_saturates() -> None:
    one, _ = compute_confidence(1.0, 1.0, True, 0, 0.0, 0.5)
    many, _ = compute_confidence(1.0, 1.0, True, 0, 0.0, 2.0)
    assert one == 95.0
    assert many == 90.0


def test_score_clamped_to_zero_and_monotone() -> None:
    worst, _ = compute_confidence(0.0, 0.0, False, 5, 1.0, 1.0)
    assert worst == 0.0
    previous = 101.0
    for ratio in (1.0, 0.75, 0.5, 0.25, 0.0):
        score, _ = compute_confidence(ratio, 1.0, True, 0 if ratio == 1.0 else 1, 0.0, 0.0)
        assert score <= previous
        previous = score


def test_weights_constant_published() -> None:
    assert CONFIDENCE_WEIGHTS == {
        "passed_results": 35.0,
        "changed_module_coverage": 20.0,
        "critical_path_validation": 15.0,
        "unresolved_failures_penalty": 25.0,
        "flakiness_penalty": 10.0,
        "security_findings_penalty": 10.0,
    }
